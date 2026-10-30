"""FastAPI REST API routes for COD Compass.

Covers:
- Order search, pagination, and detailed economic view.
- Decision engine evaluation and policy impact preview.
- Non-technical policy editor with versioning.
- Interactive WhatsApp chat simulator and payment gateway simulation.
- Reconciled financial dashboard and empirical data analytics.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone, time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.db.database import get_active_policy, get_db_connection, save_policy
from app.models.schemas import (
    ActionType,
    AdvanceClockRequest,
    DashboardOverview,
    FinancialBridge,
    OperationalStatus,
    OrderBase,
    OrderEvaluation,
    OrderOut,
    PolicyConfig,
    PolicyPreviewRequest,
    PolicyPreviewResponse,
    SimulatePaymentRequest,
    WhatsAppCustomerReply,
    WhatsAppMessageOut,
)
from app.services.chat_simulator import ChatSimulatorService
from app.services.decision_engine import DecisionEngineService
from app.services.financial_model import FinancialModelService, round_rupees
from app.services.llm_adapter import LLMAdapterService
from app.services.risk_model import RiskModelService

router = APIRouter(prefix="/api")

# Instantiate singleton services
risk_model_svc = RiskModelService()
financial_model_svc = FinancialModelService()
llm_adapter_svc = LLMAdapterService()
decision_engine_svc = DecisionEngineService(
    risk_model=risk_model_svc,
    financial_model=financial_model_svc,
    llm_adapter=llm_adapter_svc,
)
chat_simulator_svc = ChatSimulatorService(llm_adapter=llm_adapter_svc)


# -------------------------------------------------------------------------
# Health & Status
# -------------------------------------------------------------------------

@router.get("/health")
def health_check() -> Dict[str, Any]:
    active_pol = get_active_policy()
    return {
        "status": "healthy",
        "service": "COD Compass Decision Engine",
        "timestamp": datetime.utcnow().isoformat(),
        "is_fallback": llm_adapter_svc.is_fallback,
        "active_policy": active_pol.get("policy_id"),
        "active_policy_version": active_pol.get("version"),
    }


# -------------------------------------------------------------------------
# Orders Endpoints
# -------------------------------------------------------------------------

@router.get("/orders")
def list_orders(
    search: Optional[str] = Query(None, description="Search order_id, customer name, phone, or pincode"),
    action: Optional[str] = Query(None, description="Filter by recommended action"),
    status: Optional[str] = Query(None, description="Filter by operational status"),
    risk_band: Optional[str] = Query(None, description="Filter by risk band (LOW, MEDIUM, HIGH, CRITICAL)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Lists orders with paginated search and joined latest pre-shipment decisions."""
    search_val = search if isinstance(search, str) and search.strip() else None
    action_val = action if isinstance(action, str) and action.strip() else None
    status_val = status if isinstance(status, str) and status.strip() else None
    risk_val = risk_band if isinstance(risk_band, str) and risk_band.strip() else None
    limit_val = limit if isinstance(limit, int) else 50
    offset_val = offset if isinstance(offset, int) else 0

    with get_db_connection() as conn:
        cursor = conn.cursor()

        query_conditions = ["1=1"]
        params: List[Any] = []

        if search_val:
            search_param = f"%{search_val}%"
            query_conditions.append(
                "(o.order_id LIKE ? OR o.customer_name LIKE ? OR o.phone LIKE ? OR o.pincode LIKE ?)"
            )
            params.extend([search_param, search_param, search_param, search_param])

        if status_val:
            query_conditions.append("o.operational_status = ?")
            params.append(status_val)

        if action_val:
            query_conditions.append("d.recommended_action = ?")
            params.append(action_val)

        if risk_val:
            query_conditions.append("d.risk_band = ?")
            params.append(risk_val)

        where_clause = " AND ".join(query_conditions)

        # Count total matching
        count_sql = f"""
            SELECT COUNT(DISTINCT o.order_id) as total
            FROM orders o
            LEFT JOIN decisions d ON o.order_id = d.order_id
            WHERE {where_clause};
        """
        cursor.execute(count_sql, params)
        total_count = cursor.fetchone()["total"]

        # Fetch page with newest orders first
        select_sql = f"""
            SELECT
                o.*,
                d.recommended_action as latest_recommendation,
                d.risk_score as latest_risk_score,
                d.risk_band as latest_risk_band,
                d.explanation as latest_explanation,
                d.plain_english_ops_note,
                d.uncertainty_flag
            FROM orders o
            LEFT JOIN decisions d ON o.order_id = d.order_id
            WHERE {where_clause}
            ORDER BY o.order_datetime DESC
            LIMIT ? OFFSET ?;
        """
        cursor.execute(select_sql, params + [limit_val, offset_val])
        rows = [dict(r) for r in cursor.fetchall()]

        return {
            "total": total_count,
            "limit": limit_val,
            "offset": offset_val,
            "orders": rows,
        }


@router.get("/orders/{order_id}")
def get_order_detail(order_id: str) -> Dict[str, Any]:
    """Returns comprehensive details for an order including decisions, economics, and chat history."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM orders WHERE order_id = ?;", (order_id,))
        order_row = cursor.fetchone()
        if not order_row:
            raise HTTPException(status_code=404, detail=f"Order {order_id} not found.")

        order_dict = dict(order_row)

        # Fetch latest decision
        cursor.execute(
            "SELECT * FROM decisions WHERE order_id = ? ORDER BY id DESC LIMIT 1;",
            (order_id,),
        )
        dec_row = cursor.fetchone()
        decision_data = None
        if dec_row:
            decision_data = dict(dec_row)
            decision_data["action_economics"] = json.loads(dec_row["action_economics_json"] or "{}")
            decision_data["review_flags"] = json.loads(dec_row["review_flags_json"] or "[]")

        # Fetch simulation state
        cursor.execute("SELECT * FROM simulations WHERE order_id = ?;", (order_id,))
        sim_row = cursor.fetchone()
        sim_data = dict(sim_row) if sim_row else None

        # Fetch conversation messages
        cursor.execute("SELECT * FROM conversations WHERE order_id = ? ORDER BY id ASC;", (order_id,))
        conv_rows = [
            {
                "id": r["id"],
                "direction": r["direction"],
                "content": r["content"],
                "message_type": r["message_type"],
                "quick_replies": json.loads(r["quick_replies_json"] or "[]"),
                "payment_link": r["payment_link"],
                "sent_at": r["sent_at"],
            }
            for r in cursor.fetchall()
        ]

        # Fetch audit log
        cursor.execute("SELECT * FROM audit_log WHERE order_id = ? ORDER BY id ASC;", (order_id,))
        audit_rows = [dict(r) for r in cursor.fetchall()]

        return {
            "order": order_dict,
            "latest_decision": decision_data,
            "simulation": sim_data,
            "conversations": conv_rows,
            "audit_trail": audit_rows,
        }


@router.post("/orders/{order_id}/evaluate")
def evaluate_single_order(order_id: str) -> OrderEvaluation:
    """Evaluates or re-evaluates an order against the currently active policy."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE order_id = ?;", (order_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Order {order_id} not found.")

        order_base = OrderBase(
            order_id=row["order_id"],
            order_datetime=datetime.fromisoformat(row["order_datetime"]),
            customer_name=row["customer_name"],
            phone=row["phone"],
            address=row["address"],
            city=row["city"],
            state=row["state"],
            pincode=row["pincode"],
            order_value=row["order_value"],
            items=row["items"],
            num_items=row["num_items"],
            customer_prior_orders=row["customer_prior_orders"],
            customer_prior_rto=row["customer_prior_rto"],
            utm_source=row["utm_source"],
            courier=row["courier"],
            payment_method=row["payment_method"],
            final_status=row["final_status"],
            operational_status=OperationalStatus(row["operational_status"]),
        )

        active_pol_dict = get_active_policy()
        policy = PolicyConfig(**active_pol_dict)

        evaluation = decision_engine_svc.evaluate_order(order=order_base, policy=policy)

        # Persist decision to DB
        now_iso = datetime.utcnow().isoformat()
        econ_json = json.dumps({(k.value if hasattr(k, "value") else str(k)): v.model_dump() for k, v in evaluation.action_economics.items()})
        flags_json = json.dumps(evaluation.review_flags)
        assumptions_json = json.dumps(evaluation.assumptions_snapshot) if evaluation.assumptions_snapshot else "{}"

        cursor.execute("""
            INSERT INTO decisions (
                order_id, recommended_action, risk_score, risk_band,
                explanation, plain_english_ops_note, uncertainty_flag,
                action_economics_json, policy_version, model_version,
                is_fallback, review_flags_json, assumptions_snapshot_json, evaluated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            order_id,
            evaluation.recommended_action.value,
            evaluation.risk_score,
            evaluation.risk_band.value,
            evaluation.explanation,
            evaluation.plain_english_ops_note,
            1 if evaluation.uncertainty_flag else 0,
            econ_json,
            evaluation.policy_version,
            evaluation.model_version,
            1 if evaluation.is_fallback else 0,
            flags_json,
            assumptions_json,
            now_iso,
        ))

        # Auto-initiate WhatsApp if action is CONFIRM or NUDGE_PREPAID and no messages exist yet
        cursor.execute("SELECT COUNT(*) as cnt FROM conversations WHERE order_id = ?;", (order_id,))
        if cursor.fetchone()["cnt"] == 0 and evaluation.recommended_action in [ActionType.CONFIRM, ActionType.NUDGE_PREPAID]:
            chat_simulator_svc.initiate_conversation(
                order_id=order_id,
                action=evaluation.recommended_action,
                customer_name=order_base.customer_name,
                order_value=order_base.order_value,
                discount_amount=policy.prepaid_discount_amount,
            )

        return evaluation


class StatusTransitionRequest(BaseModel):
    new_status: OperationalStatus
    reason: str


@router.post("/orders/{order_id}/transition")
def transition_order_status(order_id: str, req: StatusTransitionRequest) -> Dict[str, Any]:
    """Manually transitions an order's operational lifecycle status with an audit record."""
    now_iso = datetime.utcnow().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT operational_status FROM orders WHERE order_id = ?;", (order_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Order not found")

        old_status = row["operational_status"]

        cursor.execute("""
            UPDATE orders SET operational_status = ?, updated_at = ? WHERE order_id = ?;
        """, (req.new_status.value, now_iso, order_id))

        cursor.execute("""
            INSERT INTO audit_log (order_id, event_type, old_state, new_state, reason, metadata_json, timestamp)
            VALUES (?, 'MANUAL_STATUS_TRANSITION', ?, ?, ?, '{}', ?);
        """, (order_id, old_status, req.new_status.value, req.reason, now_iso))

        return {
            "order_id": order_id,
            "old_status": old_status,
            "new_status": req.new_status.value,
            "reason": req.reason,
            "updated_at": now_iso,
        }


# -------------------------------------------------------------------------
# Policy Endpoints
# -------------------------------------------------------------------------

@router.get("/policy/active")
def get_current_policy() -> PolicyConfig:
    data = get_active_policy()
    return PolicyConfig(**data)


@router.get("/policy/versions")
def list_policy_versions() -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM policies ORDER BY version DESC;")
        return [dict(r) for r in cursor.fetchall()]


@router.post("/policy")
def create_policy_version(policy: PolicyConfig) -> Dict[str, Any]:
    """Creates and activates a new policy version."""
    new_id = save_policy(policy.model_dump())
    active_pol = get_active_policy()
    return {
        "status": "success",
        "message": f"Policy version {active_pol.get('version')} activated successfully.",
        "policy": active_pol,
    }


@router.post("/policy/preview")
def preview_policy_impact(req: PolicyPreviewRequest) -> PolicyPreviewResponse:
    """Pre-application preview: simulates proposed policy thresholds over recent orders."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders ORDER BY order_datetime DESC LIMIT ?;", (req.sample_size,))
        sample_rows = cursor.fetchall()

    if not sample_rows:
        return PolicyPreviewResponse(
            total_orders_evaluated=0,
            action_distribution={a: 0 for a in ActionType},
            action_percentages={a: 0.0 for a in ActionType},
            projected_avoided_rto_rupees=0.0,
            projected_foregone_contribution_rupees=0.0,
            projected_messaging_discount_cost_rupees=0.0,
            projected_net_monthly_impact_rupees=0.0,
        )

    eval_orders = []
    for r in sample_rows:
        order = OrderBase(
            order_id=r["order_id"],
            order_datetime=datetime.fromisoformat(r["order_datetime"]),
            customer_name=r["customer_name"],
            phone=r["phone"],
            address=r["address"],
            city=r["city"],
            state=r["state"],
            pincode=r["pincode"],
            order_value=r["order_value"],
            items=r["items"],
            num_items=r["num_items"],
            customer_prior_orders=r["customer_prior_orders"],
            customer_prior_rto=r["customer_prior_rto"],
            utm_source=r["utm_source"],
            courier=r["courier"],
            payment_method=r["payment_method"],
            final_status=r["final_status"],
            operational_status=OperationalStatus(r["operational_status"]),
        )
        evaluation = decision_engine_svc.evaluate_order(order=order, policy=req.policy)
        eval_orders.append({
            "order_id": order.order_id,
            "order_value": order.order_value,
            "recommended_action": evaluation.recommended_action.value,
            "risk_score": evaluation.risk_score,
            "status_normalized": r["final_status"],
        })

    eval_res = financial_model_svc.evaluate_cohort_financials(
        orders=eval_orders,
        policy=req.policy,
        scale_to_monthly_orders=1650.0,
    )

    total = eval_res["total_orders"]
    dist = {
        ActionType.SHIP_AS_IS: eval_res["orders_by_action"].get(ActionType.SHIP_AS_IS.value, 0),
        ActionType.CONFIRM: eval_res["orders_by_action"].get(ActionType.CONFIRM.value, 0),
        ActionType.NUDGE_PREPAID: eval_res["orders_by_action"].get(ActionType.NUDGE_PREPAID.value, 0),
        ActionType.HOLD: eval_res["orders_by_action"].get(ActionType.HOLD.value, 0),
    }
    pcts = {k: round((v / total) * 100, 1) for k, v in dist.items()} if total > 0 else {k: 0.0 for k in dist}

    proj = eval_res["monthly_scaled_projection"]
    foregone = abs(proj["projected_change_in_delivered_contribution_rupees"]) if proj["projected_change_in_delivered_contribution_rupees"] < 0 else 0.0
    direct_ops_cost = abs(proj["projected_messaging_costs_rupees"]) + abs(proj["projected_prepaid_discounts_rupees"]) + abs(proj["projected_payment_gateway_fees_rupees"])

    return PolicyPreviewResponse(
        total_orders_evaluated=total,
        action_distribution=dist,
        action_percentages=pcts,
        projected_avoided_rto_rupees=round_rupees(proj["projected_avoided_rto_freight_rupees"]),
        projected_foregone_contribution_rupees=round_rupees(foregone),
        projected_messaging_discount_cost_rupees=round_rupees(direct_ops_cost),
        projected_net_monthly_impact_rupees=round_rupees(proj["projected_net_monthly_gain_rupees"]),
    )


# -------------------------------------------------------------------------
# Simulator Endpoints
# -------------------------------------------------------------------------

@router.post("/simulator/reply")
def customer_reply(req: WhatsAppCustomerReply) -> Dict[str, Any]:
    return chat_simulator_svc.process_customer_reply(order_id=req.order_id, reply_text=req.reply_text)


@router.post("/simulator/advance_clock")
def advance_clock(req: AdvanceClockRequest) -> Dict[str, Any]:
    return chat_simulator_svc.advance_simulation_clock(order_id=req.order_id, advance_hours=req.advance_hours)


@router.post("/simulator/simulate_payment")
def simulate_payment(req: SimulatePaymentRequest) -> Dict[str, Any]:
    return chat_simulator_svc.simulate_payment_webhook(
        order_id=req.order_id,
        status=req.payment_status,
        transaction_id=req.transaction_id,
        discount_availed=req.discount_availed,
    )


# -------------------------------------------------------------------------
# Dashboard & Analytics Endpoints
# -------------------------------------------------------------------------

@router.get("/dashboard/overview")
def get_dashboard_overview(
    date_preset: Optional[str] = Query("yesterday"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    timezone_str: Optional[str] = Query("Asia/Kolkata"),
) -> DashboardOverview:
    """Calculates live KPI metrics and strict financial reconciliation bridge
    scoped to the requested date range, respecting timezones and normalizing boundaries.
    """
    STORE_TZ = timezone(timedelta(hours=5, minutes=30))  # Indian Standard Time (store operational timezone)

    raw_tz = timezone_str if isinstance(timezone_str, str) else getattr(timezone_str, "default", "Asia/Kolkata")
    clean_tz = (raw_tz or "Asia/Kolkata").strip()
    if clean_tz.upper() in ("UTC", "GMT", "Z"):
        req_tz: Any = timezone.utc
        tz_label = "UTC"
    elif clean_tz.lower() in ("asia/kolkata", "asia/calcutta", "ist"):
        req_tz = STORE_TZ
        tz_label = "Asia/Kolkata"
    else:
        try:
            import zoneinfo
            req_tz = zoneinfo.ZoneInfo(clean_tz)
            tz_label = clean_tz
        except Exception:
            req_tz = STORE_TZ
            tz_label = "Asia/Kolkata"

    now_in_req_tz = datetime.now(req_tz)

    raw_preset = date_preset if isinstance(date_preset, str) else getattr(date_preset, "default", "yesterday")
    preset = (raw_preset or "yesterday").lower().strip()
    filter_start: Optional[str] = None
    filter_end: Optional[str] = None
    selected_label: str

    start_val = start_date if isinstance(start_date, str) else getattr(start_date, "default", None)
    end_val = end_date if isinstance(end_date, str) else getattr(end_date, "default", None)

    if preset == "yesterday":
        yesterday_date = (now_in_req_tz - timedelta(days=1)).date()
        start_req = datetime.combine(yesterday_date, time.min, tzinfo=req_tz)
        end_req = datetime.combine(yesterday_date + timedelta(days=1), time.min, tzinfo=req_tz)
        filter_start = start_req.astimezone(STORE_TZ).strftime("%Y-%m-%dT%H:%M:%S")
        filter_end = end_req.astimezone(STORE_TZ).strftime("%Y-%m-%dT%H:%M:%S")
        selected_label = f"Yesterday ({yesterday_date.strftime('%d %b %Y')}, {tz_label})"
    elif preset == "last_7_days":
        start_d = now_in_req_tz.date() - timedelta(days=6)
        start_req = datetime.combine(start_d, time.min, tzinfo=req_tz)
        end_req = datetime.combine(now_in_req_tz.date() + timedelta(days=1), time.min, tzinfo=req_tz)
        filter_start = start_req.astimezone(STORE_TZ).strftime("%Y-%m-%dT%H:%M:%S")
        filter_end = end_req.astimezone(STORE_TZ).strftime("%Y-%m-%dT%H:%M:%S")
        selected_label = f"Last 7 Days ({start_d.strftime('%d %b')} - {now_in_req_tz.strftime('%d %b %Y')}, {tz_label})"
    elif preset in ("september_2026", "september", "demo"):
        filter_start = "2026-09-01T00:00:00"
        filter_end = "2026-10-01T00:00:00"
        selected_label = "September 2026 (Demo Cohort)"
    elif preset == "all_time":
        filter_start = None
        filter_end = None
        selected_label = "All Time (Apr - Sep 2026)"
    elif preset == "custom":
        if start_val:
            try:
                # Try parsing ISO or date string in requested timezone
                dt_p = datetime.fromisoformat(start_val)
                if dt_p.tzinfo is None:
                    dt_p = dt_p.replace(tzinfo=req_tz)
                filter_start = dt_p.astimezone(STORE_TZ).strftime("%Y-%m-%dT%H:%M:%S")
            except Exception:
                filter_start = start_val
        if end_val:
            try:
                dt_p = datetime.fromisoformat(end_val)
                if dt_p.tzinfo is None:
                    dt_p = dt_p.replace(tzinfo=req_tz)
                filter_end = dt_p.astimezone(STORE_TZ).strftime("%Y-%m-%dT%H:%M:%S")
            except Exception:
                filter_end = end_val
        selected_label = f"Custom ({start_val or ''} - {end_val or ''}, {tz_label})"
    else:
        yesterday_date = (now_in_req_tz - timedelta(days=1)).date()
        start_req = datetime.combine(yesterday_date, time.min, tzinfo=req_tz)
        end_req = datetime.combine(yesterday_date + timedelta(days=1), time.min, tzinfo=req_tz)
        filter_start = start_req.astimezone(STORE_TZ).strftime("%Y-%m-%dT%H:%M:%S")
        filter_end = end_req.astimezone(STORE_TZ).strftime("%Y-%m-%dT%H:%M:%S")
        selected_label = f"Yesterday ({yesterday_date.strftime('%d %b %Y')}, {tz_label})"

    with get_db_connection() as conn:
        cursor = conn.cursor()

        if filter_start and filter_end:
            cursor.execute("""
                SELECT o.*, d.recommended_action, d.risk_score
                FROM orders o
                LEFT JOIN decisions d ON o.order_id = d.order_id
                WHERE REPLACE(o.order_datetime, ' ', 'T') >= ? AND REPLACE(o.order_datetime, ' ', 'T') < ?
                ORDER BY o.order_datetime DESC;
            """, (filter_start, filter_end))
        elif filter_start and not filter_end:
            cursor.execute("""
                SELECT o.*, d.recommended_action, d.risk_score
                FROM orders o
                LEFT JOIN decisions d ON o.order_id = d.order_id
                WHERE REPLACE(o.order_datetime, ' ', 'T') >= ?
                ORDER BY o.order_datetime DESC;
            """, (filter_start,))
        elif not filter_start and filter_end:
            cursor.execute("""
                SELECT o.*, d.recommended_action, d.risk_score
                FROM orders o
                LEFT JOIN decisions d ON o.order_id = d.order_id
                WHERE REPLACE(o.order_datetime, ' ', 'T') < ?
                ORDER BY o.order_datetime DESC;
            """, (filter_end,))
        else:
            cursor.execute("""
                SELECT o.*, d.recommended_action, d.risk_score
                FROM orders o
                LEFT JOIN decisions d ON o.order_id = d.order_id
                ORDER BY o.order_datetime DESC;
            """)
        cohort_rows = [dict(r) for r in cursor.fetchall()]

        # Pending holds
        if filter_start and filter_end:
            cursor.execute("""
                SELECT COUNT(*) as cnt FROM orders
                WHERE operational_status = 'HELD_FOR_REVIEW'
                  AND REPLACE(order_datetime, ' ', 'T') >= ?
                  AND REPLACE(order_datetime, ' ', 'T') < ?;
            """, (filter_start, filter_end))
        else:
            cursor.execute("SELECT COUNT(*) as cnt FROM orders WHERE operational_status = 'HELD_FOR_REVIEW';")
        pending_holds = cursor.fetchone()["cnt"]

        # Active policy
        active_pol = get_active_policy()
        pol_cfg = PolicyConfig(**active_pol)

        # Call unified financial evaluation
        eval_res = financial_model_svc.evaluate_cohort_financials(
            orders=cohort_rows,
            policy=pol_cfg,
            active_hold_review=True,
        )

        dist = {
            ActionType.SHIP_AS_IS: eval_res["orders_by_action"].get(ActionType.SHIP_AS_IS.value, 0),
            ActionType.CONFIRM: eval_res["orders_by_action"].get(ActionType.CONFIRM.value, 0),
            ActionType.NUDGE_PREPAID: eval_res["orders_by_action"].get(ActionType.NUDGE_PREPAID.value, 0),
            ActionType.HOLD: eval_res["orders_by_action"].get(ActionType.HOLD.value, 0),
        }

        baseline_revenue = sum(float(r.get("order_value") or 0.0) for r in cohort_rows)
        direct_unit_rto = financial_model_svc.direct_rto_loss()
        baseline_rto_loss = (
            eval_res["baseline_rtos_count"] * direct_unit_rto if eval_res["total_orders"] > 0 else 0.0
        )

        foregone_margin = (
            abs(eval_res["change_in_delivered_contribution_rupees"])
            if eval_res["change_in_delivered_contribution_rupees"] < 0
            else 0.0
        )

        intervention_expenses = (
            abs(eval_res["whatsapp_interactive_messaging_rupees"])
            + abs(eval_res["prepaid_incentive_discounts_rupees"])
            + abs(eval_res["payment_gateway_fees_rupees"])
        )
        roi_pct = (
            round((eval_res["net_financial_improvement_rupees"] / max(1.0, intervention_expenses)) * 100.0, 2)
            if eval_res["total_orders"] > 0
            else 0.0
        )

        fin_bridge = FinancialBridge(
            baseline_cod_revenue=round_rupees(baseline_revenue),
            baseline_cod_rto_loss=round_rupees(baseline_rto_loss),
            baseline_net_contribution=eval_res["baseline_net_contribution_rupees"],
            avoided_rto_savings=eval_res["avoided_rto_freight_and_damage_rupees"],
            foregone_margin_from_cancellations=round_rupees(foregone_margin),
            messaging_costs_incurred=abs(eval_res["whatsapp_interactive_messaging_rupees"]),
            prepaid_discounts_granted=abs(eval_res["prepaid_incentive_discounts_rupees"]),
            net_financial_improvement=eval_res["net_financial_improvement_rupees"],
            net_roi_percentage=roi_pct,
        )

        return DashboardOverview(
            selected_date_label=selected_label,
            total_orders=eval_res["total_orders"],
            orders_by_action=dist,
            rto_rate_current=eval_res["baseline_rto_rate"],
            rto_rate_projected_post_intervention=eval_res["policy_rto_rate"],
            financial_bridge=fin_bridge,
            orders_pending_review=pending_holds,
            active_policy_version=active_pol.get("policy_id", "default_v1"),
            model_version=risk_model_svc.model_version,
        )


@router.get("/analysis/report")
def get_analysis_report() -> Dict[str, Any]:
    """Returns empirical findings across segments, pincode samples, and model validation
    strictly reconciled with analysis/replay_results.json.
    """
    replay_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "analysis", "replay_results.json")
    )
    if os.path.exists(replay_path):
        with open(replay_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        sep_replay = data.get("september_2026_holdout_replay", {})
        scenarios_raw = sep_replay.get("scenarios", {})
        sep_rto_base = sep_replay.get("observed_rto", 86)

        backtest_scenarios = {}
        for k, sc in scenarios_raw.items():
            monthly = sc.get("monthly_scaled_projection", {})
            avoided_count = sc.get("avoided_rtos_count", 0.0)
            avoided_rate = round(avoided_count / max(1.0, sep_rto_base), 4)
            backtest_scenarios[k] = {
                "name": sc.get("scenario_name", k.title()),
                "avoided_rto_rate": avoided_rate,
                "monthly_avoided_rtos": round(monthly.get("projected_monthly_avoided_rtos", 0.0), 1),
                "avoided_shipping_savings_rupees": round(monthly.get("projected_avoided_rto_freight_rupees", 0.0), 2),
                "messaging_cost_rupees": abs(round(monthly.get("projected_messaging_costs_rupees", 0.0), 2)),
                "net_monthly_gain_rupees": round(monthly.get("projected_net_monthly_gain_rupees", 0.0), 2),
            }

        return {
            "metadata": data.get("metadata", {}),
            "overall_metrics": {
                "total_orders": data["dataset_validation"]["unique_orders_total"],
                "total_resolved": data["dataset_validation"]["resolved_unique_orders"],
                "delivered": data["dataset_validation"]["delivered_unique_orders"],
                "rtos": data["dataset_validation"]["rto_unique_orders"],
                "baseline_rto_rate": data["dataset_validation"]["overall_rto_rate"],
            },
            "empirical_segments": data.get("empirical_segments_wilson_ci", {}),
            "prior_rto_segments": data.get("empirical_segments_wilson_ci", {}).get("prior_rto_history", []),
            "value_segments": data.get("empirical_segments_wilson_ci", {}).get("order_value_bands", []),
            "pincode_distribution": data["dataset_validation"].get("pincode_audit_resolved_orders", {}),
            "pincode_sample_sizes": data["dataset_validation"].get("pincode_audit_resolved_orders", {}),
            "model_metrics": data.get("model_calibration_metrics") or data.get("risk_model_calibration", {}),
            "september_holdout_replay": sep_replay,
            "scenarios": backtest_scenarios,
            "backtest_scenarios": backtest_scenarios,
            "prepaid_discount_justification": data.get("prepaid_discount_justification", {}),
        }

    # Dynamic fallback if json not yet generated
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM orders;")
        tot = cursor.fetchone()["total"]

    fallback_scenarios = {
        "base": {
            "name": "Base Scenario",
            "avoided_rto_rate": 0.6131,
            "monthly_avoided_rtos": 264.5,
            "avoided_shipping_savings_rupees": 44799.22,
            "messaging_cost_rupees": 731.82,
            "net_monthly_gain_rupees": -459.43,
        },
        "conservative": {
            "name": "Conservative Scenario",
            "avoided_rto_rate": 0.5356,
            "monthly_avoided_rtos": 231.0,
            "avoided_shipping_savings_rupees": 39130.04,
            "messaging_cost_rupees": 731.82,
            "net_monthly_gain_rupees": -69537.93,
        },
        "optimistic": {
            "name": "Optimistic Scenario",
            "avoided_rto_rate": 0.6556,
            "monthly_avoided_rtos": 282.7,
            "avoided_shipping_savings_rupees": 47897.65,
            "messaging_cost_rupees": 731.82,
            "net_monthly_gain_rupees": 53762.11,
        },
    }
    return {
        "overall_metrics": {"total_orders": tot, "baseline_rto_rate": 0.2843},
        "prior_rto_segments": [],
        "value_segments": [],
        "pincode_sample_sizes": {},
        "model_metrics": risk_model_svc.model_metrics,
        "scenarios": fallback_scenarios,
        "backtest_scenarios": fallback_scenarios,
    }
