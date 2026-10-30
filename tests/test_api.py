"""Direct integration tests for COD Compass API handlers."""

import pytest
from app.api.endpoints import (
    get_analysis_report,
    get_current_policy,
    get_dashboard_overview,
    get_order_detail,
    health_check,
    list_orders,
    preview_policy_impact,
)
from app.models.schemas import PolicyConfig, PolicyPreviewRequest


def test_health_check_handler():
    data = health_check()
    assert data["status"] == "healthy"
    assert data["service"] == "COD Compass Decision Engine"
    assert "active_policy" in data
    assert "is_fallback" in data


def test_list_orders_handler():
    res = list_orders(search=None, action=None, status=None, risk_band=None, limit=10, offset=0)
    assert res["total"] > 0
    assert len(res["orders"]) <= 10
    first_order = res["orders"][0]
    assert "order_id" in first_order
    assert "order_value" in first_order


def test_get_order_detail_handler():
    # Fetch first order id
    res = list_orders(limit=1, offset=0)
    first_id = res["orders"][0]["order_id"]

    detail = get_order_detail(first_id)
    assert "order" in detail
    assert "latest_decision" in detail
    assert detail["order"]["order_id"] == first_id


def test_dashboard_overview_handler():
    # 1. Default to Yesterday (in Asia/Kolkata timezone) - returns honest empty state on historical/demo dataset
    overview_yesterday = get_dashboard_overview(date_preset="yesterday")
    assert overview_yesterday.total_orders == 0
    assert "Yesterday" in overview_yesterday.selected_date_label
    assert overview_yesterday.financial_bridge.net_financial_improvement == 0.0

    # Calculate expected counts independently from the active database
    from app.db.database import get_db_connection
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM orders WHERE REPLACE(order_datetime, ' ', 'T') >= '2026-09-01T00:00:00' AND REPLACE(order_datetime, ' ', 'T') < '2026-10-01T00:00:00';")
        expected_sep_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM orders;")
        expected_total_count = cursor.fetchone()[0]

    # Verify that the expected counts are non-zero and match known datasets (153 for synthetic demo, 329 for original data)
    assert expected_sep_count > 0
    assert expected_sep_count in (153, 329), f"Unexpected September order count: {expected_sep_count}"
    assert expected_total_count in (500, 1988), f"Unexpected total order count: {expected_total_count}"

    # 2. Preset for September 2026 cohort - independently verified
    overview_sep = get_dashboard_overview(date_preset="september_2026")
    assert overview_sep.total_orders == expected_sep_count
    assert "September 2026" in overview_sep.selected_date_label
    assert overview_sep.orders_by_action is not None
    assert overview_sep.financial_bridge.avoided_rto_savings > 0.0

    # 3. Preset for All Time - independently verified
    overview_all = get_dashboard_overview(date_preset="all_time")
    assert overview_all.total_orders == expected_total_count
    assert "All Time" in overview_all.selected_date_label


def test_policy_preview_handler():
    pol = PolicyConfig(
        policy_id="test_preview_pol",
        version=99,
        name="Test Preview Policy",
        description="Testing policy impact simulation",
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
    req = PolicyPreviewRequest(policy=pol, sample_size=50)
    preview = preview_policy_impact(req)
    assert preview.total_orders_evaluated > 0
    assert len(preview.action_distribution) == 4
    assert preview.projected_net_monthly_impact_rupees is not None


def test_analysis_report_handler():
    report = get_analysis_report()
    assert "overall_metrics" in report
    assert "prior_rto_segments" in report
    assert "pincode_sample_sizes" in report
    assert "backtest_scenarios" in report
    assert report["overall_metrics"]["total_orders"] > 0


def test_analysis_report_frontend_contract():
    """Defect 2: Verifies that analysis endpoint outputs match the frontend contract
    defined in frontend/src/types.ts and required by AnalysisView.tsx.
    """
    report = get_analysis_report()
    bts = report.get("backtest_scenarios", {})

    # Must contain scenarios, never an empty dict
    assert len(bts) >= 3, f"Expected at least 3 scenarios, got {len(bts)}"
    for key in ("base", "conservative", "optimistic"):
        assert key in bts, f"Missing scenario key '{key}' in backtest_scenarios"
        sc = bts[key]
        assert "name" in sc and isinstance(sc["name"], str) and len(sc["name"]) > 0
        assert "avoided_rto_rate" in sc and isinstance(sc["avoided_rto_rate"], (int, float))
        assert "monthly_avoided_rtos" in sc and isinstance(sc["monthly_avoided_rtos"], (int, float))
        assert "avoided_shipping_savings_rupees" in sc and isinstance(sc["avoided_shipping_savings_rupees"], (int, float))
        assert "messaging_cost_rupees" in sc and isinstance(sc["messaging_cost_rupees"], (int, float))
        assert "net_monthly_gain_rupees" in sc and isinstance(sc["net_monthly_gain_rupees"], (int, float))

    # Verify that negative monetary values are preserved (not clamped or lost)
    assert bts["conservative"]["net_monthly_gain_rupees"] < 0, "Conservative scenario should project negative net monthly gain"
    assert bts["base"]["net_monthly_gain_rupees"] < 0, "Base scenario should project negative net monthly gain"
    assert bts["optimistic"]["net_monthly_gain_rupees"] > 0, "Optimistic scenario should project positive net monthly gain"
