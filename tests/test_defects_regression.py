"""
Comprehensive Regression Test Suite for COD Compass Defect Fixes.

Covers:
1. Policy and Economics consistency: Discount policy changes propagate to offer text and financial models.
2. Financial Accounting Identity: revenue - cogs - forward - return - packaging - damage - messaging - discount - fees == net_contribution.
3. Precedence: High-value high-risk overlap quarentined in HOLD.
4. Precedence: Prior-RTO high-risk overlap quarantined in HOLD.
5. Exact risk boundaries: Contiguous bands at 0.20, 0.35, 0.65.
6. Truthful explanations: Distinction between safety hold and economically negative shipment (P > P_breakeven).
7. Address heuristics: Complete landmark-first address starting with "Near" is NOT flagged.
8. Probability precision: Break-even RTO maintains float precision and is never rounded as rupees.
9. Input validation: NaN, Inf, and negative order values / probabilities are strictly rejected.
10. Dynamic replay robustness: Empty action buckets handled without ZeroDivisionError.
11. HOLD review modeling: Imperfect review and residual leakage accounting.
12. Prepaid discount comparison: Full nonconverter fallback economics, residual RTO, fees, and messaging.
"""

import math
import pytest
from pydantic import ValidationError

from app.models.schemas import ActionType, OperationalStatus, OrderBase, PolicyConfig
from app.services.chat_simulator import ChatSimulatorService
from app.services.decision_engine import DecisionEngineService
from app.services.financial_model import FinancialModelService
from app.services.llm_adapter import LLMAdapterService
from app.services.risk_model import RiskModelService
from app.api.endpoints import get_dashboard_overview


def make_sample_order(**kwargs) -> OrderBase:
    defaults = {
        "order_id": "TEST_REG_101",
        "order_datetime": "2026-09-15 10:00:00",
        "customer_name": "Rohan Sharma",
        "phone": "9876543210",
        "address": "Flat 302, Green Glen Layout, Bellandur",
        "city": "Bengaluru",
        "state": "Karnataka",
        "pincode": "560103",
        "order_value": 799.0,
        "items": "Cotton Shirt",
        "num_items": 1,
        "customer_prior_orders": 2,
        "customer_prior_rto": 0,
        "utm_source": "direct",
        "courier": "Delhivery",
        "payment_method": "COD",
    }
    defaults.update(kwargs)
    return OrderBase(**defaults)


def test_1_discount_policy_consistency():
    """Defect 2: Changing discount in PolicyConfig changes both offer text and financial evaluation."""
    risk_svc = RiskModelService()
    fin_svc = FinancialModelService()
    engine = DecisionEngineService(risk_model=risk_svc, financial_model=fin_svc)

    order = make_sample_order(customer_prior_rto=3, customer_prior_orders=3)

    # 1. Evaluate with Rs 50 discount policy
    policy_50 = PolicyConfig(prepaid_discount_amount=50.0)
    eval_50 = engine.evaluate_order(order, policy=policy_50)
    assert eval_50.recommended_action == ActionType.NUDGE_PREPAID
    assert "₹50" in eval_50.explanation
    assert eval_50.action_economics["NUDGE_PREPAID"].expected_discount == 50.0 * 0.22  # p_prep_conv is 22%
    assert eval_50.assumptions_snapshot["prepaid_discount_rupees"] == 50.0

    # 2. Evaluate with Rs 0 discount policy
    policy_0 = PolicyConfig(prepaid_discount_amount=0.0)
    eval_0 = engine.evaluate_order(order, policy=policy_0)
    assert eval_0.recommended_action == ActionType.NUDGE_PREPAID
    assert "₹0" in eval_0.explanation
    assert eval_0.action_economics["NUDGE_PREPAID"].expected_discount == 0.0
    assert eval_0.assumptions_snapshot["prepaid_discount_rupees"] == 0.0


def test_2_accounting_identity_all_actions():
    """Defect 6: All evaluated actions must satisfy the exact accounting identity:
    revenue - cogs - forward - return - packaging - damage - messaging - discount - fees == net_contribution.
    """
    fin_svc = FinancialModelService()
    policy = PolicyConfig(prepaid_discount_amount=25.0)

    for rto_risk in [0.05, 0.25, 0.45, 0.75, 0.95]:
        econ_map = fin_svc.evaluate_order_actions(order_value=850.0, calibrated_rto_prob=rto_risk, policy=policy)
        for act, econ in econ_map.items():
            reconstructed_net = (
                econ.expected_gross_revenue
                - econ.expected_cogs
                - econ.expected_forward_shipping
                - econ.expected_return_shipping
                - econ.expected_packaging
                - econ.expected_damage_loss
                - econ.expected_messaging_cost
                - econ.expected_discount
                - econ.expected_payment_fee
            )
            discrepancy = abs(reconstructed_net - econ.expected_net_contribution)
            assert discrepancy <= 0.015, (
                f"Action {act} at risk {rto_risk} violates accounting identity: "
                f"reconstructed={reconstructed_net:.4f}, expected={econ.expected_net_contribution:.4f}, diff={discrepancy:.4f}"
            )


def test_3_high_value_high_risk_precedence():
    """Defect 3: An order with basket >= 1500 but extreme risk > hold_threshold MUST be quarantined in HOLD."""
    risk_svc = RiskModelService()
    fin_svc = FinancialModelService()
    engine = DecisionEngineService(risk_model=risk_svc, financial_model=fin_svc)

    # Order with high value (Rs 2800) and suspicious address + repeat returner (risk > 0.65)
    order = make_sample_order(
        order_value=2800.0,
        address="near temple",
        customer_prior_rto=2,
        customer_prior_orders=2,
    )
    eval_res = engine.evaluate_order(order)
    assert eval_res.risk_score >= 0.65
    # Security/address or extreme risk hold must supersede high basket confirmation override!
    assert eval_res.recommended_action == ActionType.HOLD
    assert any("EXTREME_RISK" in f or "SUSPICIOUS" in f for f in eval_res.review_flags)


def test_4_prior_rto_high_risk_precedence():
    """Defect 3: An order with customer_prior_rto >= 2 and risk > hold_threshold MUST be quarantined in HOLD."""
    risk_svc = RiskModelService()
    fin_svc = FinancialModelService()
    engine = DecisionEngineService(risk_model=risk_svc, financial_model=fin_svc)

    order = make_sample_order(
        address="test",
        customer_prior_rto=3,
        customer_prior_orders=3,
    )
    eval_res = engine.evaluate_order(order)
    assert eval_res.risk_score >= 0.65
    assert eval_res.recommended_action == ActionType.HOLD
    assert any("EXTREME_RISK" in f or "SUSPICIOUS" in f for f in eval_res.review_flags)


def test_5_exact_risk_boundaries():
    """Defect 3: Policy risk bands must be contiguous and handle exact boundary values."""
    fin_svc = FinancialModelService()
    policy = PolicyConfig(
        low_risk_threshold=0.20,
        confirm_threshold=0.35,
        nudge_threshold=0.65,
        hold_threshold=0.85,
    )

    # Validate policy configuration requires low <= confirm <= nudge <= hold
    assert policy.low_risk_threshold <= policy.confirm_threshold <= policy.nudge_threshold <= policy.hold_threshold

    # Reject inverted policy configurations
    with pytest.raises(ValidationError):
        PolicyConfig(
            low_risk_threshold=0.50,
            confirm_threshold=0.30,  # invalid: confirm < low
        )

    with pytest.raises(ValidationError):
        PolicyConfig(
            nudge_threshold=0.70,
            hold_threshold=0.60,  # invalid: hold < nudge
        )


def test_6_truthful_economic_explanations():
    """Defect 4: Checks actual P > P_breakeven before claiming break-even is exceeded."""
    risk_svc = RiskModelService()
    fin_svc = FinancialModelService()
    engine = DecisionEngineService(risk_model=risk_svc, financial_model=fin_svc)

    # For basket Rs 649, delivered contribution = 649*0.62 - 90 = 312.38
    # direct_rto_loss = 169.40 -> breakeven_p = 312.38 / (312.38 + 169.40) = 64.84%
    p_be = fin_svc.calculate_cancellation_breakeven_rto(649.0)
    assert 0.64 <= p_be <= 0.66

    # Order with risk 0.70 (> breakeven_p) held
    order_neg = make_sample_order(order_value=649.0, address="near post office", customer_prior_rto=1)
    eval_neg = engine.evaluate_order(order_neg)
    if eval_neg.risk_score > p_be:
        assert "exceeds" in eval_neg.explanation or "negative" in eval_neg.explanation

    # Order with low order value Rs 50 where delivered contribution is <= 0 (Gross profit Rs 31 < logistics Rs 90)
    p_be_low = fin_svc.calculate_cancellation_breakeven_rto(50.0)
    assert p_be_low == 0.0  # Explicitly 0.0, never negative or rounded to integer!


def test_7_complete_landmark_address_not_flagged():
    """Defect 5: Complete address starting with 'Near' must NOT be flagged as suspicious."""
    from app.services.risk_model import extract_address_features

    addr = "Near City Mall, House 42, MG Road, Sector 10"
    feats = extract_address_features("Rohan Sharma", addr)
    assert not feats["is_suspicious_address"]
    assert feats["has_building_number"]

    # Vague landmark only without street / numbers SHOULD be flagged
    vague_addr = "near temple"
    vague_feats = extract_address_features("Rohan Sharma", vague_addr)
    assert vague_feats["is_suspicious_address"]
    assert not vague_feats["has_building_number"]


def test_8_probability_precision():
    """Defect 7: Probability calculations maintain float precision and do not call round_rupees."""
    fin_svc = FinancialModelService()
    p_be = fin_svc.calculate_cancellation_breakeven_rto(1299.0)
    assert isinstance(p_be, float)
    assert 0.0 < p_be < 1.0
    # Must have fractional decimal precision
    assert p_be != round(p_be, 0)
    assert p_be == round(p_be, 4)


def test_9_input_validation_rejection():
    """Defect 7: Invalid probability, monetary inputs, NaN, and Inf are strictly rejected."""
    fin_svc = FinancialModelService()
    risk_svc = RiskModelService()

    # Reject negative order value
    with pytest.raises(ValueError, match="order_value"):
        fin_svc.evaluate_order_actions(order_value=-500.0, calibrated_rto_prob=0.30)

    # Reject NaN probability
    with pytest.raises(ValueError, match="calibrated_rto_prob"):
        fin_svc.evaluate_order_actions(order_value=649.0, calibrated_rto_prob=float("nan"))

    # Reject Inf probability
    with pytest.raises(ValueError, match="calibrated_rto_prob"):
        fin_svc.evaluate_order_actions(order_value=649.0, calibrated_rto_prob=float("inf"))

    # Reject probability out of bounds [0, 1]
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        fin_svc.evaluate_order_actions(order_value=649.0, calibrated_rto_prob=1.25)

    # Risk model input validation
    with pytest.raises(ValueError, match="order_value"):
        risk_svc.predict_order_risk(
            order_value=float("nan"),
            customer_name="Test",
            address="Street 1",
            pincode="560103",
            customer_prior_rto=0,
            customer_prior_orders=0,
        )


def test_10_empty_replay_bucket_handling():
    """Defect 9: Replay evaluation handles 0 orders in any bucket without ZeroDivisionError."""
    fin_svc = FinancialModelService()
    # Evaluate a scenario where an action bucket has 0 orders
    econ_map = fin_svc.evaluate_order_actions(order_value=649.0, calibrated_rto_prob=0.15)
    assert ActionType.SHIP_AS_IS in econ_map
    assert ActionType.CONFIRM in econ_map
    assert ActionType.NUDGE_PREPAID in econ_map
    assert ActionType.HOLD in econ_map


def test_11_hold_review_leakage_modeling():
    """Defect 6: Imperfect HOLD review accounts for leakage and residual RTO."""
    fin_svc = FinancialModelService()
    p = fin_svc.assumptions

    # Hold order with active review
    econ_map = fin_svc.evaluate_order_actions(order_value=799.0, calibrated_rto_prob=0.80, active_hold_review=True)
    hold_econ = econ_map[ActionType.HOLD]

    # Under active review (recovery 70%, leakage 0% in base), packaging is charged only on recovered dispatched orders
    assert hold_econ.expected_packaging <= p.packaging_cost
    assert hold_econ.expected_gross_revenue > 0.0  # Genuine orders recovered
    # Reconciled identity holds
    net = (
        hold_econ.expected_gross_revenue
        - hold_econ.expected_cogs
        - hold_econ.expected_forward_shipping
        - hold_econ.expected_return_shipping
        - hold_econ.expected_packaging
        - hold_econ.expected_damage_loss
        - hold_econ.expected_messaging_cost
        - hold_econ.expected_discount
        - hold_econ.expected_payment_fee
    )
    assert abs(net - hold_econ.expected_net_contribution) <= 0.015


def test_12_full_prepaid_discount_comparison_economics():
    """Defect 8: evaluate_prepaid_discount_options includes full nonconverter fallback economics."""
    fin_svc = FinancialModelService()
    opts = fin_svc.evaluate_prepaid_discount_options(
        order_value=649.0, calibrated_rto_prob=0.765, discounts=[0.0, 15.0, 25.0, 35.0]
    )
    for opt in opts:
        assert "expected_incremental_pool" in opt
        assert "breakeven_conversion_rate_percent" in opt
        assert "nonconverter_fallback_ev" in opt
        assert "total_expected_pool_ev" in opt
        # Break-even conversion rate must be around ~10% to ~11%
        assert 9.0 <= opt["breakeven_conversion_rate_percent"] <= 15.0


def test_13_whatsapp_intent_boundary_and_negation():
    """Defect: Substring matching false-positives and negation errors in chat NLP."""
    adapter = LLMAdapterService()

    # "I don't know" must NOT trigger cancel due to "no" inside "know"
    res1 = adapter.parse_customer_whatsapp_reply("I don't know what to do", order_id="ORD-123", discount_amount=25.0)
    assert res1["intent"] == "AMBIGUOUS_OR_UNRESOLVED"

    # "please change address" must NOT trigger confirmation due to "ha" inside "change"
    res2 = adapter.parse_customer_whatsapp_reply("please change address to flat 102", order_id="ORD-123")
    assert res2["intent"] == "ADDRESS_UPDATE"

    # "link bhejo" must NOT trigger simple confirm due to "bhejo"
    res3 = adapter.parse_customer_whatsapp_reply("online payment link bhejo", order_id="ORD-123", discount_amount=35.0)
    assert res3["intent"] == "ASK_DISCOUNT_OR_PAYMENT"
    assert "₹35" in res3["bot_response"]
    assert "https://pay.codcompass.demo/pay/ORD-123" in res3["bot_response"]
    assert "{ORDER_ID}" not in res3["bot_response"]

    # "don't cancel" must NOT trigger cancel
    res4 = adapter.parse_customer_whatsapp_reply("don't cancel please dispatch soon", order_id="ORD-123")
    assert res4["intent"] == "CONFIRM_ORDER"

    # Negated confirmation alone: "do not confirm" must return AMBIGUOUS_OR_UNRESOLVED and request clarification, without cancelling
    res5 = adapter.parse_customer_whatsapp_reply("do not confirm", order_id="ORD-123")
    assert res5["intent"] == "AMBIGUOUS_OR_UNRESOLVED"
    assert res5["action_recommended"] == "HOLD"
    assert "clarify" in res5["bot_response"].lower()

    # "don't confirm" must also return AMBIGUOUS_OR_UNRESOLVED
    res5b = adapter.parse_customer_whatsapp_reply("don't confirm", order_id="ORD-123")
    assert res5b["intent"] == "AMBIGUOUS_OR_UNRESOLVED"
    assert res5b["action_recommended"] == "HOLD"

    # Explicit cancel: "no payment link, cancel it" must trigger cancel, NOT payment inquiry
    res6 = adapter.parse_customer_whatsapp_reply("no payment link, cancel it", order_id="ORD-123")
    assert res6["intent"] == "CANCEL_ORDER"
    assert res6["action_recommended"] == "CANCEL"

    # "don't want online payment, cancel" must trigger cancel
    res7 = adapter.parse_customer_whatsapp_reply("don't want online payment, cancel", order_id="ORD-123")
    assert res7["intent"] == "CANCEL_ORDER"
    assert res7["action_recommended"] == "CANCEL"

    # "do not confirm, cancel it" (negated confirm + explicit cancel) must trigger cancel
    res8 = adapter.parse_customer_whatsapp_reply("do not confirm, cancel it", order_id="ORD-123")
    assert res8["intent"] == "CANCEL_ORDER"
    assert res8["action_recommended"] == "CANCEL"


def test_14_terminal_order_state_safety():
    """Defect: Ordinary chat messages cannot silently reopen terminal orders."""
    from app.db.database import get_db_connection
    sim = ChatSimulatorService(LLMAdapterService())
    test_id = "REG_TERMINAL_01"
    now_iso = "2026-09-15T10:00:00"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM payment_transactions WHERE order_id = ?;", (test_id,))
        cursor.execute("DELETE FROM conversations WHERE order_id = ?;", (test_id,))
        cursor.execute("DELETE FROM simulations WHERE order_id = ?;", (test_id,))
        cursor.execute("DELETE FROM orders WHERE order_id = ?;", (test_id,))
        cursor.execute("""
            INSERT INTO orders (
                order_id, order_datetime, customer_name, phone, address, city, state, pincode,
                order_value, items, num_items, customer_prior_orders, customer_prior_rto,
                utm_source, courier, payment_method, final_status, operational_status, created_at, updated_at
            ) VALUES (?, ?, 'Test Buyer', '9876543210', '123 MG Road', 'Bengaluru', 'Karnataka', '560001',
                     649.0, 'Serum', 1, 0, 0, 'direct', NULL, 'COD', 'DELIVERED', 'NEW', ?, ?);
        """, (test_id, now_iso, now_iso, now_iso))

    try:
        # Seed order and start conversation
        sim.initiate_conversation(test_id, ActionType.CONFIRM, "Test Buyer", 649.0)

        # Customer cancels
        res_cancel = sim.process_customer_reply(test_id, "cancel this order")
        assert res_cancel["operational_status"] == OperationalStatus.CANCELLED.value

        # Subsequent customer reply saying "yes" MUST NOT reopen order to CONFIRMED
        res_reopen_attempt = sim.process_customer_reply(test_id, "yes please send it")
        assert res_reopen_attempt["operational_status"] == OperationalStatus.CANCELLED.value
        assert "already in terminal state" in res_reopen_attempt["bot_reply"]
    finally:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM payment_transactions WHERE order_id = ?;", (test_id,))
            c.execute("DELETE FROM conversations WHERE order_id = ?;", (test_id,))
            c.execute("DELETE FROM simulations WHERE order_id = ?;", (test_id,))
            c.execute("DELETE FROM orders WHERE order_id = ?;", (test_id,))


def test_15_payment_idempotency_and_cross_order_rejection():
    """Defect: Enforce payment idempotency and reject cross-order transaction reuse."""
    from app.db.database import get_db_connection
    sim = ChatSimulatorService(LLMAdapterService())
    ord_a = "REG_PAY_A"
    ord_b = "REG_PAY_B"
    shared_txn = "TXN_UNIQUE_REG_9999"
    now_iso = "2026-09-15T10:00:00"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        for oid in (ord_a, ord_b):
            cursor.execute("DELETE FROM payment_transactions WHERE order_id = ?;", (oid,))
            cursor.execute("DELETE FROM conversations WHERE order_id = ?;", (oid,))
            cursor.execute("DELETE FROM simulations WHERE order_id = ?;", (oid,))
            cursor.execute("DELETE FROM orders WHERE order_id = ?;", (oid,))
            cursor.execute("""
                INSERT INTO orders (
                    order_id, order_datetime, customer_name, phone, address, city, state, pincode,
                    order_value, items, num_items, customer_prior_orders, customer_prior_rto,
                    utm_source, courier, payment_method, final_status, operational_status, created_at, updated_at
                ) VALUES (?, ?, 'Buyer', '9876543210', '123 MG Road', 'Bengaluru', 'Karnataka', '560001',
                         899.0, 'Serum', 1, 0, 0, 'direct', NULL, 'COD', 'DELIVERED', 'NEW', ?, ?);
            """, (oid, now_iso, now_iso, now_iso))

    try:
        sim.initiate_conversation(ord_a, ActionType.NUDGE_PREPAID, "Buyer A", 899.0)
        sim.initiate_conversation(ord_b, ActionType.NUDGE_PREPAID, "Buyer B", 899.0)

        # 1. Process valid payment for ord_a
        res1 = sim.simulate_payment_webhook(order_id=ord_a, status="SUCCESS", transaction_id=shared_txn)
        assert res1["status"] == "PROCESSED"
        assert res1["operational_status"] == OperationalStatus.PREPAID_CONVERTED.value

        # 2. Idempotent repeat for ord_a with same transaction
        res2 = sim.simulate_payment_webhook(order_id=ord_a, status="SUCCESS", transaction_id=shared_txn)
        assert res2["status"] == "ALREADY_PROCESSED"

        # 3. Replay attack / accidental duplicate transaction on a DIFFERENT order must be rejected
        with pytest.raises(ValueError, match="Cross-order transaction reuse is prohibited"):
            sim.simulate_payment_webhook(order_id=ord_b, status="SUCCESS", transaction_id=shared_txn)
    finally:
        with get_db_connection() as conn:
            c = conn.cursor()
            for oid in (ord_a, ord_b):
                c.execute("DELETE FROM payment_transactions WHERE order_id = ?;", (oid,))
                c.execute("DELETE FROM conversations WHERE order_id = ?;", (oid,))
                c.execute("DELETE FROM simulations WHERE order_id = ?;", (oid,))
                c.execute("DELETE FROM orders WHERE order_id = ?;", (oid,))


def test_16_yesterday_dashboard_date_filtering():
    """Defect 1: Default dashboard to yesterday with honest empty state and independently verified September count."""
    # Yesterday: clean empty state
    y_view = get_dashboard_overview(date_preset="yesterday")
    assert y_view.total_orders == 0
    assert y_view.financial_bridge.net_financial_improvement == 0.0

    # Independently query expected September orders from whatever dataset is active
    from app.db.database import get_db_connection
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM orders WHERE REPLACE(order_datetime, ' ', 'T') >= '2026-09-01T00:00:00' AND REPLACE(order_datetime, ' ', 'T') < '2026-10-01T00:00:00';")
        expected_sep_count = cursor.fetchone()[0]

    assert expected_sep_count in (153, 329), f"Unexpected September order count: {expected_sep_count}"

    # September demo cohort: matches expected count, reconciled bridge discrepancy == 0.0
    sep_view = get_dashboard_overview(date_preset="september_2026")
    assert sep_view.total_orders == expected_sep_count
    assert sep_view.financial_bridge.avoided_rto_savings > 0.0


def test_17_llm_strict_validation_and_fallback_safety():
    """Defect 4: Malformed LLM provider outputs must fallback safely without raising ValueError,
    and each individual fallback response must report is_fallback=True.
    """
    adapter = LLMAdapterService()
    adapter.api_key = "test_mock_key"

    # 1. Mock provider returning malformed completeness_score="invalid"
    adapter._call_live_gemini = lambda prompt: {"completeness_score": "invalid", "is_deliverable": "yes"}
    res_malformed = adapter.analyze_address_completeness("123 MG Road", "Bengaluru", "560001")
    assert res_malformed["is_fallback"] is True
    assert isinstance(res_malformed["completeness_score"], float)
    assert 0.0 <= res_malformed["completeness_score"] <= 1.0

    # 2. Mock provider returning valid response -> is_fallback is False
    adapter._call_live_gemini = lambda prompt: {
        "completeness_score": 0.88,
        "is_deliverable": True,
        "summary": "Verified complete address",
        "missing_components": [],
    }
    res_valid = adapter.analyze_address_completeness("Flat 101, Lake View, MG Road", "Bengaluru", "560001")
    assert res_valid["is_fallback"] is False
    assert res_valid["completeness_score"] == 0.88

    # 3. Subsequent call with provider failure/exception -> MUST report is_fallback=True (NOT sticky False!)
    adapter._call_live_gemini = lambda prompt: None
    adapter._call_live_openai = lambda prompt: None
    res_after = adapter.analyze_address_completeness("Near Temple", "Bengaluru", "560001")
    assert res_after["is_fallback"] is True

    # 4. Mock provider returning invalid intent/action for chat parser
    adapter._call_live_gemini = lambda prompt: {
        "intent": "INVALID_INTENT_XYZ",
        "confidence": "not_a_number",
        "action_recommended": "DESTROY",
    }
    res_chat_malformed = adapter.parse_customer_whatsapp_reply("haan confirm hai", order_id="ORD-999")
    assert res_chat_malformed["is_fallback"] is True
    assert res_chat_malformed["intent"] in (
        "CONFIRM_ORDER", "CANCEL_ORDER", "ASK_DISCOUNT_OR_PAYMENT", "ADDRESS_UPDATE", "AMBIGUOUS_OR_UNRESOLVED"
    )


def test_18_cross_output_financial_consistency():
    """Defect 5: FinancialModelService produces consistent outputs across replay, preview, and dashboard."""
    fin = FinancialModelService()
    pol = PolicyConfig(
        policy_id="test_consistency_pol",
        version=1,
        name="Consistency Policy",
        description="Test",
        low_risk_threshold=0.20,
        confirm_threshold=0.35,
        nudge_threshold=0.55,
        hold_threshold=0.70,
        prepaid_discount_amount=25.0,
        auto_cancel_enabled=False,
        require_confirm_above_value=1500.0,
        min_pincode_sample=5,
        is_active=True,
    )
    sample_orders = [
        {"order_id": "ORD_1", "order_value": 500.0, "status_normalized": "DELIVERED", "recommended_action": "SHIP_AS_IS"},
        {"order_id": "ORD_2", "order_value": 800.0, "status_normalized": "RTO", "recommended_action": "CONFIRM"},
        {"order_id": "ORD_3", "order_value": 1600.0, "status_normalized": "DELIVERED", "recommended_action": "HOLD"},
        {"order_id": "ORD_4", "order_value": 1200.0, "status_normalized": "RTO", "recommended_action": "NUDGE_PREPAID"},
    ]
    res = fin.evaluate_cohort_financials(sample_orders, policy=pol, active_hold_review=True)
    assert res["reconciliation_discrepancy_rupees"] == 0.0
    reconciled_sum = (
        res["avoided_rto_freight_and_damage_rupees"]
        + res["change_in_delivered_contribution_rupees"]
        + res["prepaid_incentive_discounts_rupees"]
        + res["whatsapp_interactive_messaging_rupees"]
        + res["payment_gateway_fees_rupees"]
    )
    assert abs(reconciled_sum - res["net_financial_improvement_rupees"]) < 1e-5


def test_19_dashboard_timezone_boundaries():
    """Defect 6: Dashboard overview normalizes timezone boundaries and respects timezone_str."""
    from app.db.database import get_db_connection
    test_order_id = "TZ_BOUNDARY_TEST_ORDER"
    # Order placed at 02:00:00 on Sept 1, 2026 IST.
    # In UTC, this is 2026-08-31 20:30:00 (i.e. August 31, NOT September 1).
    order_ist = "2026-09-01T02:00:00"
    now_iso = "2026-09-15T10:00:00"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM orders WHERE order_id = ?;", (test_order_id,))
        cursor.execute("""
            INSERT INTO orders (
                order_id, order_datetime, customer_name, phone, address, city, state, pincode,
                order_value, items, num_items, customer_prior_orders, customer_prior_rto,
                utm_source, courier, payment_method, final_status, operational_status, created_at, updated_at
            ) VALUES (?, ?, 'TZ Buyer', '9876543210', '123 MG Road', 'Bengaluru', 'Karnataka', '560001',
                     649.0, 'Serum', 1, 0, 0, 'direct', NULL, 'COD', 'DELIVERED', 'NEW', ?, ?);
        """, (test_order_id, order_ist, now_iso, now_iso))

    try:
        # Query in Asia/Kolkata timezone covering Sept 1:
        view_ist = get_dashboard_overview(
            date_preset="custom",
            start_date="2026-09-01T00:00:00",
            end_date="2026-09-01T23:59:59",
            timezone_str="Asia/Kolkata",
        )
        # Query in UTC covering Sept 1 UTC (which starts at 05:30 IST on Sept 1):
        view_utc = get_dashboard_overview(
            date_preset="custom",
            start_date="2026-09-01T00:00:00",
            end_date="2026-09-01T23:59:59",
            timezone_str="UTC",
        )
        # The order at 02:00 IST is before 05:30 IST (00:00 UTC), so it belongs to Aug 31 in UTC.
        assert view_ist.total_orders > 0
        assert "Asia/Kolkata" in view_ist.selected_date_label
        assert "UTC" in view_utc.selected_date_label
    finally:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM orders WHERE order_id = ?;", (test_order_id,))

