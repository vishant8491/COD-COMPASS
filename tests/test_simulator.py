"""Unit tests for the WhatsApp conversation simulator and payment webhook state machine."""

from datetime import datetime
import pytest
from app.db.database import get_db_connection, init_db
from app.models.schemas import ActionType, OperationalStatus
from app.services.chat_simulator import ChatSimulatorService
from app.services.llm_adapter import LLMAdapterService


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    # Insert test order
    now_iso = datetime.utcnow().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM conversations WHERE order_id = 'SIM_TEST_01';")
        cursor.execute("DELETE FROM simulations WHERE order_id = 'SIM_TEST_01';")
        cursor.execute("DELETE FROM decisions WHERE order_id = 'SIM_TEST_01';")
        cursor.execute("DELETE FROM orders WHERE order_id = 'SIM_TEST_01';")
        cursor.execute("""
            INSERT INTO orders (
                order_id, order_datetime, customer_name, phone, address, city, state, pincode,
                order_value, items, num_items, customer_prior_orders, customer_prior_rto,
                utm_source, courier, payment_method, final_status, operational_status,
                created_at, updated_at
            ) VALUES (
                'SIM_TEST_01', ?, 'Rohit Sharma', '9876543210', 'Flat 101, Marine Drive', 'Mumbai', 'Maharashtra', '400020',
                649.0, 'Hair Serum', 1, 0, 0,
                'instagram', NULL, 'COD', 'DELIVERED', 'NEW',
                ?, ?
            );
        """, (now_iso, now_iso, now_iso))
    yield
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM conversations WHERE order_id = 'SIM_TEST_01';")
        cursor.execute("DELETE FROM simulations WHERE order_id = 'SIM_TEST_01';")
        cursor.execute("DELETE FROM decisions WHERE order_id = 'SIM_TEST_01';")
        cursor.execute("DELETE FROM orders WHERE order_id = 'SIM_TEST_01';")


def test_initiate_conversation():
    sim = ChatSimulatorService(LLMAdapterService())
    msg = sim.initiate_conversation(
        order_id="SIM_TEST_01",
        action=ActionType.CONFIRM,
        customer_name="Rohit Sharma",
        order_value=649.0,
    )
    assert msg.order_id == "SIM_TEST_01"
    assert "Please confirm your order" in msg.content
    assert msg.direction.value == "OUTBOUND"


def test_customer_confirmation_reply():
    sim = ChatSimulatorService(LLMAdapterService())
    sim.initiate_conversation("SIM_TEST_01", ActionType.CONFIRM, "Rohit Sharma", 649.0)

    # Customer confirms in Hinglish
    res = sim.process_customer_reply("SIM_TEST_01", "haan bhai bhej do, confirm hai")
    assert res["intent"] == "CONFIRM_ORDER"
    assert res["operational_status"] == OperationalStatus.CONFIRMED.value


def test_customer_cancellation_reply():
    sim = ChatSimulatorService(LLMAdapterService())
    sim.initiate_conversation("SIM_TEST_01", ActionType.CONFIRM, "Rohit Sharma", 649.0)

    # Customer cancels
    res = sim.process_customer_reply("SIM_TEST_01", "cancel kar do please, nahi chahiye")
    assert res["intent"] == "CANCEL_ORDER"
    assert res["operational_status"] == OperationalStatus.CANCELLED.value


def test_simulation_clock_24h_timeout():
    sim = ChatSimulatorService(LLMAdapterService())
    sim.initiate_conversation("SIM_TEST_01", ActionType.CONFIRM, "Rohit Sharma", 649.0)

    # Advance clock by 25 hours
    res = sim.advance_simulation_clock("SIM_TEST_01", advance_hours=25)
    assert res["timeout_triggered"] is True
    assert res["operational_status"] == OperationalStatus.HELD_FOR_REVIEW.value


def test_payment_webhook_and_idempotency():
    sim = ChatSimulatorService(LLMAdapterService())
    sim.initiate_conversation("SIM_TEST_01", ActionType.NUDGE_PREPAID, "Rohit Sharma", 649.0, discount_amount=25.0)

    # First payment webhook
    res1 = sim.simulate_payment_webhook("SIM_TEST_01", status="SUCCESS", transaction_id="tx_12345", discount_availed=25.0)
    assert res1["status"] == "PROCESSED"
    assert res1["operational_status"] == OperationalStatus.PREPAID_CONVERTED.value

    # Verify order is marked PREPAID
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT payment_method, operational_status FROM orders WHERE order_id = 'SIM_TEST_01';")
        row = cursor.fetchone()
        assert row["payment_method"] == "PREPAID"
        assert row["operational_status"] == OperationalStatus.PREPAID_CONVERTED.value

    # Duplicate call should be IDEMPOTENT
    res2 = sim.simulate_payment_webhook("SIM_TEST_01", status="SUCCESS", transaction_id="tx_12345", discount_availed=25.0)
    assert res2["status"] == "ALREADY_PROCESSED"


def test_negated_confirmation_holds_order_and_requests_clarification():
    """Negated confirmation alone must return AMBIGUOUS_OR_UNRESOLVED and hold order without cancelling."""
    sim = ChatSimulatorService(LLMAdapterService())
    sim.initiate_conversation("SIM_TEST_01", ActionType.CONFIRM, "Rohit Sharma", 649.0)

    # Customer replies "do not confirm"
    res = sim.process_customer_reply("SIM_TEST_01", "do not confirm")
    assert res["intent"] == "AMBIGUOUS_OR_UNRESOLVED"
    assert res["operational_status"] == OperationalStatus.HELD_FOR_REVIEW.value
    assert "clarify" in res["bot_reply"].lower()

    # Verify in DB that order is HELD_FOR_REVIEW, strictly NOT CANCELLED
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT operational_status FROM orders WHERE order_id = 'SIM_TEST_01';")
        row = cursor.fetchone()
        assert row["operational_status"] == OperationalStatus.HELD_FOR_REVIEW.value


def test_explicit_cancel_with_negated_payment_cancels_order():
    """'no payment link, cancel it' has explicit cancel request and must cancel order."""
    sim = ChatSimulatorService(LLMAdapterService())
    sim.initiate_conversation("SIM_TEST_01", ActionType.CONFIRM, "Rohit Sharma", 649.0)

    res = sim.process_customer_reply("SIM_TEST_01", "no payment link, cancel it")
    assert res["intent"] == "CANCEL_ORDER"
    assert res["operational_status"] == OperationalStatus.CANCELLED.value

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT operational_status FROM orders WHERE order_id = 'SIM_TEST_01';")
        row = cursor.fetchone()
        assert row["operational_status"] == OperationalStatus.CANCELLED.value


def test_address_update_holds_order():
    """'please change address' must route to ADDRESS_UPDATE and hold order."""
    sim = ChatSimulatorService(LLMAdapterService())
    sim.initiate_conversation("SIM_TEST_01", ActionType.CONFIRM, "Rohit Sharma", 649.0)

    res = sim.process_customer_reply("SIM_TEST_01", "please change address to Flat 204 Green Heights")
    assert res["intent"] == "ADDRESS_UPDATE"
    assert res["operational_status"] == OperationalStatus.HELD_FOR_REVIEW.value


def test_discount_inquiry_awaits_payment():
    """'link bhejo' must route to ASK_DISCOUNT_OR_PAYMENT and await payment."""
    sim = ChatSimulatorService(LLMAdapterService())
    sim.initiate_conversation("SIM_TEST_01", ActionType.NUDGE_PREPAID, "Rohit Sharma", 649.0, discount_amount=25.0)

    res = sim.process_customer_reply("SIM_TEST_01", "link bhejo")
    assert res["intent"] == "ASK_DISCOUNT_OR_PAYMENT"
    assert res["operational_status"] == OperationalStatus.AWAITING_PAYMENT.value
    assert "https://pay.codcompass.demo/pay/SIM_TEST_01" in res["bot_reply"]


def test_cancelled_order_cannot_reopen_via_ordinary_reply():
    """Cancelled order cannot reopen through ordinary customer confirmation replies."""
    sim = ChatSimulatorService(LLMAdapterService())
    sim.initiate_conversation("SIM_TEST_01", ActionType.CONFIRM, "Rohit Sharma", 649.0)

    # First explicitly cancel the order
    cancel_res = sim.process_customer_reply("SIM_TEST_01", "cancel it please")
    assert cancel_res["intent"] == "CANCEL_ORDER"
    assert cancel_res["operational_status"] == OperationalStatus.CANCELLED.value

    # Subsequent customer confirmation reply must NOT reopen the cancelled order
    reopen_res = sim.process_customer_reply("SIM_TEST_01", "haan bhej do, confirm hai")
    assert reopen_res["operational_status"] == OperationalStatus.CANCELLED.value
    assert "already in terminal state" in reopen_res["bot_reply"]

    # Verify database state remained CANCELLED
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT operational_status FROM orders WHERE order_id = 'SIM_TEST_01';")
        row = cursor.fetchone()
        assert row["operational_status"] == OperationalStatus.CANCELLED.value


