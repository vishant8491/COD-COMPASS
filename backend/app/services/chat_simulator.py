"""WhatsApp interactive chat simulator and payment gateway state machine.

Provides:
1. Deterministic conversational state machine for COD order confirmation & prepaid nudge.
2. Simulated clock advancement (+1h, +24h timeout).
3. Mock payment links and idempotent payment webhook simulation.
4. Full message history persistence in SQLite.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.db.database import get_db_connection
from app.models.schemas import ActionType, MessageDirection, OperationalStatus, WhatsAppMessageOut
from app.services.llm_adapter import LLMAdapterService

MOCK_PAYMENT_URL_PREFIX = "https://pay.codcompass.demo/pay/"


class ChatSimulatorService:
    """Manages WhatsApp messages, customer interaction simulation, and payment callbacks."""

    def __init__(self, llm_adapter: Optional[LLMAdapterService] = None):
        self.llm_adapter = llm_adapter or LLMAdapterService()

    def initiate_conversation(
        self,
        order_id: str,
        action: ActionType,
        customer_name: str,
        order_value: float,
        discount_amount: float = 25.0,
        connection: Optional[Any] = None,
    ) -> WhatsAppMessageOut:
        """Starts a WhatsApp conversation when an order is flagged for CONFIRM or NUDGE_PREPAID."""
        now_dt = datetime.utcnow()
        now_iso = now_dt.isoformat()
        net_value = max(0.0, order_value - discount_amount)
        pay_link = f"{MOCK_PAYMENT_URL_PREFIX}{order_id}"

        if action == ActionType.NUDGE_PREPAID:
            content = (
                f"Hi {customer_name}! 🌿 Thank you for your order #{order_id} (₹{order_value:.0f}). "
                f"Pay online right now via UPI/Card to get an INSTANT ₹{discount_amount:.0f} DISCOUNT "
                f"and priority dispatch! Pay only ₹{net_value:.0f}: {pay_link}"
            )
            msg_type = "NUDGE_OFFER"
            quick_replies = [f"Pay ₹{net_value:.0f} Online", "Keep as Cash on Delivery", "Cancel Order"]
        else:
            # ActionType.CONFIRM
            content = (
                f"Hi {customer_name}! 🌿 Thank you for ordering with us (#{order_id}, ₹{order_value:.0f} COD). "
                "Please confirm your order for quick dispatch. Reply YES to confirm or CANCEL if placed by mistake."
            )
            msg_type = "CONFIRM_REQUEST"
            quick_replies = ["Yes, Confirm My Order", "Cancel Order", "Change Address"]

        def _execute(conn: Any) -> int:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversations (
                    order_id, direction, content, message_type, quick_replies_json, payment_link, sent_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                order_id,
                MessageDirection.OUTBOUND.value,
                content,
                msg_type,
                json.dumps(quick_replies),
                pay_link if action == ActionType.NUDGE_PREPAID else None,
                now_iso,
            ))
            msg_id = cursor.lastrowid

            step = "AWAITING_PAYMENT" if action == ActionType.NUDGE_PREPAID else "AWAITING_CONFIRMATION"
            cursor.execute("""
                INSERT INTO simulations (order_id, step, payment_status, payment_link, discount_applied, simulated_clock_time, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(order_id) DO UPDATE SET
                    step = excluded.step,
                    payment_link = excluded.payment_link,
                    discount_applied = excluded.discount_applied,
                    simulated_clock_time = excluded.simulated_clock_time,
                    updated_at = excluded.updated_at;
            """, (
                order_id,
                step,
                "UNPAID",
                pay_link if action == ActionType.NUDGE_PREPAID else None,
                discount_amount if action == ActionType.NUDGE_PREPAID else 0.0,
                now_iso,
                now_iso,
            ))

            op_status = (
                OperationalStatus.AWAITING_PAYMENT.value
                if action == ActionType.NUDGE_PREPAID
                else OperationalStatus.AWAITING_CONFIRMATION.value
            )
            cursor.execute("""
                UPDATE orders SET operational_status = ?, updated_at = ? WHERE order_id = ?;
            """, (op_status, now_iso, order_id))

            cursor.execute("""
                INSERT INTO audit_log (order_id, event_type, old_state, new_state, reason, metadata_json, timestamp)
                VALUES (?, 'WHATSAPP_INITIATED', 'NEW', ?, 'Automated pre-shipment action initiated', ?, ?);
            """, (
                order_id,
                op_status,
                json.dumps({"action": action.value, "discount": discount_amount}),
                now_iso,
            ))
            return msg_id

        if connection is not None:
            msg_id = _execute(connection)
        else:
            with get_db_connection() as conn:
                msg_id = _execute(conn)

        return WhatsAppMessageOut(
            id=msg_id,
            order_id=order_id,
            direction=MessageDirection.OUTBOUND,
            content=content,
            message_type=msg_type,
            quick_replies=quick_replies,
            payment_link=pay_link if action == ActionType.NUDGE_PREPAID else None,
            sent_at=now_dt,
        )

    def process_customer_reply(self, order_id: str, reply_text: str) -> Dict[str, Any]:
        """Processes an incoming customer reply, determines intent, and transitions states safely.
        
        Guarantees:
        - Raises ValueError if order_id does not exist.
        - Terminal states (CANCELLED, DELIVERED, RETURNED) cannot be reopened by customer messages.
        - Records real current_status as old_state in audit logs.
        - Atomic updates.
        """
        now_iso = datetime.utcnow().isoformat()

        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Verify order existence and current status
            cursor.execute("SELECT operational_status, order_value FROM orders WHERE order_id = ?;", (order_id,))
            order_row = cursor.fetchone()
            if not order_row:
                raise ValueError(f"Order {order_id} not found.")

            current_status = order_row["operational_status"]

            # Terminal state safeguard: prevent customer messages from silently reopening cancelled/delivered orders
            terminal_states = {
                OperationalStatus.CANCELLED.value,
                OperationalStatus.DELIVERED.value,
                OperationalStatus.RTO.value,
            }

            # Step 1: NLP analysis of reply
            analysis = self.llm_adapter.parse_customer_whatsapp_reply(reply_text, order_id=order_id)
            intent = analysis["intent"]
            bot_reply = analysis["bot_response"]

            # Record customer's inbound message
            cursor.execute("""
                INSERT INTO conversations (order_id, direction, content, message_type, quick_replies_json, payment_link, sent_at)
                VALUES (?, ?, ?, 'CUSTOMER_REPLY', '[]', NULL, ?);
            """, (order_id, MessageDirection.INBOUND.value, reply_text, now_iso))

            if current_status in terminal_states:
                bot_reply = (
                    f"Notice: Order #{order_id} is already in terminal state '{current_status}'. "
                    "Customer replies cannot automatically reopen terminal orders. Please contact customer support for assistance."
                )
                new_op_status = current_status
                new_step = current_status
                audit_reason = f"Customer message received on terminal order ({current_status}); state reopening blocked."

            else:
                # Determine state transition for active order
                if intent == "CONFIRM_ORDER":
                    new_op_status = OperationalStatus.CONFIRMED.value
                    new_step = "CONFIRMED"
                    audit_reason = "Customer explicitly confirmed order via WhatsApp."
                elif intent == "CANCEL_ORDER":
                    new_op_status = OperationalStatus.CANCELLED.value
                    new_step = "CANCELLED"
                    audit_reason = "Customer requested order cancellation via WhatsApp."
                elif intent == "ASK_DISCOUNT_OR_PAYMENT":
                    new_op_status = OperationalStatus.AWAITING_PAYMENT.value
                    new_step = "AWAITING_PAYMENT"
                    audit_reason = "Customer expressed interest in prepaid payment."
                else:
                    # Ambiguous or address change -> Hold for review
                    new_op_status = OperationalStatus.HELD_FOR_REVIEW.value
                    new_step = "HELD_FOR_REVIEW"
                    audit_reason = f"Customer message ambiguous or requested changes: '{reply_text}'."

                # Update orders table
                cursor.execute("""
                    UPDATE orders SET operational_status = ?, updated_at = ? WHERE order_id = ?;
                """, (new_op_status, now_iso, order_id))

                # Update simulation table
                cursor.execute("""
                    UPDATE simulations SET step = ?, updated_at = ? WHERE order_id = ?;
                """, (new_step, now_iso, order_id))

            # Record bot's automatic response
            cursor.execute("""
                INSERT INTO conversations (order_id, direction, content, message_type, quick_replies_json, payment_link, sent_at)
                VALUES (?, ?, ?, 'BOT_RESPONSE', '[]', NULL, ?);
            """, (order_id, MessageDirection.OUTBOUND.value, bot_reply, now_iso))

            # Audit log recording real old_state
            cursor.execute("""
                INSERT INTO audit_log (order_id, event_type, old_state, new_state, reason, metadata_json, timestamp)
                VALUES (?, 'CUSTOMER_REPLY_PROCESSED', ?, ?, ?, ?, ?);
            """, (
                order_id,
                current_status,
                new_op_status,
                audit_reason,
                json.dumps({"intent": intent, "reply_text": reply_text}),
                now_iso,
            ))

        return {
            "order_id": order_id,
            "intent": intent,
            "bot_reply": bot_reply,
            "operational_status": new_op_status,
            "step": new_step,
            "is_fallback": analysis.get("is_fallback", True),
        }

    def simulate_payment_webhook(
        self,
        order_id: str,
        status: str,  # SUCCESS or FAILED
        transaction_id: Optional[str] = None,
        discount_availed: float = 25.0,
    ) -> Dict[str, Any]:
        """Simulates payment gateway webhook callback with IDEMPOTENCY and cross-order protection."""
        tx_id = transaction_id or f"pay_tx_{order_id}_{int(datetime.utcnow().timestamp())}"
        now_iso = datetime.utcnow().isoformat()

        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Verify order existence
            cursor.execute("SELECT operational_status, payment_method, order_value FROM orders WHERE order_id = ?;", (order_id,))
            order_row = cursor.fetchone()
            if not order_row:
                raise ValueError(f"Order {order_id} not found.")

            current_status = order_row["operational_status"]
            order_val = float(order_row["order_value"]) if order_row["order_value"] is not None else 649.0
            net_amount = max(0.0, order_val - discount_availed)

            # Check payment_transactions table for transaction_id uniqueness and idempotency
            cursor.execute("SELECT order_id, status FROM payment_transactions WHERE transaction_id = ?;", (tx_id,))
            existing_tx = cursor.fetchone()
            if existing_tx:
                if existing_tx["order_id"] != order_id:
                    raise ValueError(
                        f"Transaction ID '{tx_id}' was already registered for another order '{existing_tx['order_id']}'. "
                        "Cross-order transaction reuse is prohibited."
                    )
                # Idempotent response for same transaction on same order
                return {
                    "order_id": order_id,
                    "status": "ALREADY_PROCESSED",
                    "payment_status": existing_tx["status"],
                    "operational_status": current_status,
                    "transaction_id": tx_id,
                    "message": "Payment webhook was already recorded; idempotent response returned.",
                }

            # Check if order was already prepaid converted
            if current_status == OperationalStatus.PREPAID_CONVERTED.value and status == "SUCCESS":
                cursor.execute("""
                    INSERT OR IGNORE INTO payment_transactions (transaction_id, order_id, amount, status, metadata_json, created_at)
                    VALUES (?, ?, ?, 'PAID', ?, ?);
                """, (tx_id, order_id, net_amount, json.dumps({"note": "duplicate payment on converted order"}), now_iso))
                return {
                    "order_id": order_id,
                    "status": "ALREADY_PROCESSED",
                    "payment_status": "PAID",
                    "operational_status": current_status,
                    "transaction_id": tx_id,
                    "message": "Payment was already recorded; idempotent response returned.",
                }

            # Safety handling: payment received after order was already cancelled
            if current_status == OperationalStatus.CANCELLED.value:
                new_op_status = OperationalStatus.HELD_FOR_REVIEW.value
                sim_step = "PAYMENT_AFTER_CANCELLATION"
                payment_status = "HELD_FOR_REVIEW"
                bot_msg = (
                    f"⚠️ We received payment of ₹{net_amount:.2f} (Txn ID: {tx_id}), but order #{order_id} was already cancelled. "
                    "The order has been placed on HOLD for supervisor review to initiate an immediate refund or authorize dispatch."
                )

                cursor.execute("""
                    INSERT INTO payment_transactions (transaction_id, order_id, amount, status, metadata_json, created_at)
                    VALUES (?, ?, ?, 'HELD_FOR_REVIEW', ?, ?);
                """, (tx_id, order_id, net_amount, json.dumps({"note": "payment after cancellation"}), now_iso))

                cursor.execute("""
                    UPDATE orders SET operational_status = ?, updated_at = ? WHERE order_id = ?;
                """, (new_op_status, now_iso, order_id))

                audit_reason = "Payment received after order cancellation; held for refund/supervisor authorization."

            elif status == "SUCCESS":
                new_op_status = OperationalStatus.PREPAID_CONVERTED.value
                sim_step = "PAID"
                payment_status = "PAID"
                bot_msg = (
                    f"🎉 Payment of ₹{net_amount:.2f} (discount ₹{discount_availed:.0f} applied) successful! (Txn ID: {tx_id}). "
                    f"Order #{order_id} is now confirmed as PREPAID. Priority packaging in progress!"
                )

                cursor.execute("""
                    INSERT INTO payment_transactions (transaction_id, order_id, amount, status, metadata_json, created_at)
                    VALUES (?, ?, ?, 'PAID', ?, ?);
                """, (tx_id, order_id, net_amount, json.dumps({"discount_applied": discount_availed}), now_iso))

                cursor.execute("""
                    UPDATE orders
                    SET operational_status = ?, payment_method = 'PREPAID', updated_at = ?
                    WHERE order_id = ?;
                """, (new_op_status, now_iso, order_id))

                audit_reason = f"Payment webhook SUCCESS: converted to PREPAID with ₹{discount_availed:.0f} discount."

            else:
                new_op_status = OperationalStatus.AWAITING_CONFIRMATION.value
                sim_step = "PAYMENT_FAILED_FALLBACK_COD"
                payment_status = "FAILED"
                bot_msg = (
                    "Your online payment attempt could not be completed. No problem! "
                    "Would you like us to ship this order as standard Cash on Delivery instead? Reply YES to confirm."
                )

                cursor.execute("""
                    INSERT INTO payment_transactions (transaction_id, order_id, amount, status, metadata_json, created_at)
                    VALUES (?, ?, ?, 'FAILED', ?, ?);
                """, (tx_id, order_id, net_amount, json.dumps({"status": "failed"}), now_iso))

                cursor.execute("""
                    UPDATE orders SET operational_status = ?, updated_at = ? WHERE order_id = ?;
                """, (new_op_status, now_iso, order_id))

                audit_reason = "Payment webhook FAILED: fallback to COD confirmation."

            # Update simulation table
            cursor.execute("""
                UPDATE simulations
                SET step = ?, payment_status = ?, discount_applied = ?, updated_at = ?
                WHERE order_id = ?;
            """, (sim_step, payment_status, discount_availed if status == "SUCCESS" else 0.0, now_iso, order_id))

            # Add outbound notification
            cursor.execute("""
                INSERT INTO conversations (order_id, direction, content, message_type, quick_replies_json, payment_link, sent_at)
                VALUES (?, ?, ?, 'PAYMENT_EVENT', '[]', NULL, ?);
            """, (order_id, MessageDirection.OUTBOUND.value, bot_msg, now_iso))

            # Audit log recording real current_status
            cursor.execute("""
                INSERT INTO audit_log (order_id, event_type, old_state, new_state, reason, metadata_json, timestamp)
                VALUES (?, 'PAYMENT_WEBHOOK', ?, ?, ?, ?, ?);
            """, (
                order_id,
                current_status,
                new_op_status,
                audit_reason,
                json.dumps({"transaction_id": tx_id, "discount": discount_availed}),
                now_iso,
            ))

        return {
            "order_id": order_id,
            "status": "PROCESSED",
            "payment_status": payment_status,
            "operational_status": new_op_status,
            "transaction_id": tx_id,
            "message": bot_msg,
        }

    def advance_simulation_clock(self, order_id: str, advance_hours: int = 1) -> Dict[str, Any]:
        """Advances the simulated clock for an order and triggers timeout events if > 24 hours
        from the outbound interaction initiation.
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM simulations WHERE order_id = ?;", (order_id,))
            sim_row = cursor.fetchone()
            if not sim_row:
                raise ValueError(f"Simulation record for {order_id} not found.")

            curr_sim_time = datetime.fromisoformat(sim_row["simulated_clock_time"])
            new_sim_time = curr_sim_time + timedelta(hours=advance_hours)
            new_sim_time_iso = new_sim_time.isoformat()

            cursor.execute("SELECT * FROM orders WHERE order_id = ?;", (order_id,))
            order_row = cursor.fetchone()
            if not order_row:
                raise ValueError(f"Order {order_id} not found.")

            # Measure timeout from the latest outbound interaction time, NOT historical order_datetime
            cursor.execute("""
                SELECT MAX(sent_at) as last_sent FROM conversations
                WHERE order_id = ? AND direction = 'OUTBOUND';
            """, (order_id,))
            conv_row = cursor.fetchone()
            if conv_row and conv_row["last_sent"]:
                outbound_time = datetime.fromisoformat(conv_row["last_sent"])
            else:
                outbound_time = curr_sim_time

            elapsed_hours = (new_sim_time - outbound_time).total_seconds() / 3600.0

            step = sim_row["step"]
            op_status = order_row["operational_status"]
            timeout_triggered = False

            # If pending confirmation or payment for > 24 hours without response
            if elapsed_hours >= 24.0 and op_status in [
                OperationalStatus.AWAITING_CONFIRMATION.value,
                OperationalStatus.AWAITING_PAYMENT.value,
            ]:
                timeout_triggered = True
                new_op_status = OperationalStatus.HELD_FOR_REVIEW.value
                new_step = "TIMEOUT_HELD_FOR_REVIEW"
                timeout_msg = (
                    "⚠️ [SYSTEM NOTICE]: 24 hours elapsed without customer response. "
                    "Order automatically held for manual operations review before dispatch."
                )

                cursor.execute("""
                    UPDATE orders SET operational_status = ?, updated_at = ? WHERE order_id = ?;
                """, (new_op_status, new_sim_time_iso, order_id))

                cursor.execute("""
                    UPDATE simulations SET step = ?, simulated_clock_time = ?, updated_at = ? WHERE order_id = ?;
                """, (new_step, new_sim_time_iso, new_sim_time_iso, order_id))

                cursor.execute("""
                    INSERT INTO conversations (order_id, direction, content, message_type, quick_replies_json, payment_link, sent_at)
                    VALUES (?, 'SYSTEM', ?, 'TIMEOUT_ALERT', '[]', NULL, ?);
                """, (order_id, timeout_msg, new_sim_time_iso))

                cursor.execute("""
                    INSERT INTO audit_log (order_id, event_type, old_state, new_state, reason, metadata_json, timestamp)
                    VALUES (?, 'SIMULATOR_TIMEOUT', ?, ?, '24h elapsed without response', ?, ?);
                """, (
                    order_id,
                    op_status,
                    new_op_status,
                    json.dumps({"elapsed_hours": elapsed_hours}),
                    new_sim_time_iso,
                ))

                op_status = new_op_status
                step = new_step
            else:
                cursor.execute("""
                    UPDATE simulations SET simulated_clock_time = ?, updated_at = ? WHERE order_id = ?;
                """, (new_sim_time_iso, new_sim_time_iso, order_id))

        return {
            "order_id": order_id,
            "previous_time": curr_sim_time.isoformat(),
            "new_simulated_time": new_sim_time_iso,
            "elapsed_hours": round(elapsed_hours, 1),
            "timeout_triggered": timeout_triggered,
            "operational_status": op_status,
            "step": step,
        }

    def get_conversation_history(self, order_id: str) -> List[Dict[str, Any]]:
        """Returns all messages in the conversation for a given order."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM conversations WHERE order_id = ? ORDER BY id ASC;",
                (order_id,),
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": r["id"],
                    "order_id": r["order_id"],
                    "direction": r["direction"],
                    "content": r["content"],
                    "message_type": r["message_type"],
                    "quick_replies": json.loads(r["quick_replies_json"] or "[]"),
                    "payment_link": r["payment_link"],
                    "sent_at": r["sent_at"],
                }
                for r in rows
            ]
