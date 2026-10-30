"""Unit tests for the COD Compass deterministic financial model.

Verifies:
1. Exact baseline math required by assignment:
   - Direct RTO loss per return = ₹169.40.
   - Monthly COD orders = 1,650.
   - Expected monthly returns = 462.
   - Expected monthly direct RTO loss = ₹78,262.80.
2. Delivered order gross margin & contribution accounting.
3. Sunk CAC handling (never double-counted in incremental decisions).
4. Break-even RTO probability formula (~64.8%).
5. Prepaid discount option comparison (₹0, ₹15, ₹25, ₹35).
"""

import pytest
from app.models.schemas import ActionType, FinancialAssumptions
from app.services.financial_model import (
    AssignmentBaselineMetrics,
    FinancialModelService,
    from_paise,
    round_rupees,
    to_paise,
)


def test_baseline_assignment_figures():
    """Validates the canonical assignment figures down to the exact paisa."""
    baseline = AssignmentBaselineMetrics()

    # 1. Direct RTO loss: 65 + 65 + 25 + (0.08 * 180) = 169.40
    assert baseline.direct_rto_loss_per_return == 169.40

    # 2. Monthly COD orders: 3000 * 0.55 = 1650
    assert baseline.monthly_cod_orders == 1650

    # 3. Expected monthly COD RTOs: 1650 * 0.28 = 462.0
    assert baseline.expected_monthly_cod_rtos == 462.0

    # 4. Expected monthly direct RTO loss: 462 * 169.40 = 78,262.80
    assert baseline.expected_monthly_direct_rto_loss == 78262.80


def test_financial_service_direct_rto_loss():
    svc = FinancialModelService()
    assert svc.direct_rto_loss() == 169.40


def test_delivered_order_contribution():
    svc = FinancialModelService()
    # At ₹649 AOV:
    # 62% gross profit = 649 * 0.62 = 402.38
    # Less forward shipping (65) and packaging (25) = 402.38 - 90 = 312.38
    contrib = svc.delivered_order_contribution(649.0)
    assert contrib == 312.38


def test_cancellation_breakeven_rto():
    svc = FinancialModelService()
    # Break-even P = Delivered_Contrib / (RTO_Loss + Delivered_Contrib)
    # 312.38 / (169.40 + 312.38) = 312.38 / 481.78 = 0.6483 -> 65%
    be_p = svc.calculate_cancellation_breakeven_rto(649.0)
    assert 0.64 <= be_p <= 0.66


def test_sunk_cac_is_not_subtracted_from_incremental_actions():
    svc = FinancialModelService()
    # Order evaluated with 25% risk
    econ = svc.evaluate_order_actions(order_value=649.0, calibrated_rto_prob=0.25)

    # Baseline advantage vs baseline is always 0.0
    assert econ[ActionType.SHIP_AS_IS].net_advantage_vs_baseline == 0.0

    # CAC at risk is reported for transparency (₹300 * P_del)
    # but NOT subtracted from expected_net_contribution
    baseline = econ[ActionType.SHIP_AS_IS]
    expected_before_cac = (0.75 * 312.38) - (0.25 * 169.40)  # 234.285 - 42.35 = 191.935
    assert abs(baseline.expected_net_contribution - expected_before_cac) <= 0.02
    assert baseline.acquisition_spend_at_risk == round_rupees(0.75 * 300.0)


def test_prepaid_discount_options_comparison():
    svc = FinancialModelService()
    opts = svc.evaluate_prepaid_discount_options(
        order_value=649.0, calibrated_rto_prob=0.35, discounts=[0.0, 15.0, 25.0, 35.0]
    )
    assert len(opts) == 4
    # Ensure ₹25 discount provides attractive incremental profit pool
    d25 = next(o for o in opts if o["discount_rupees"] == 25.0)
    assert d25["net_prepaid_contribution_per_order"] > 250.0
    assert d25["estimated_conversion_rate"] >= 0.20


def test_paise_rounding_helper():
    assert to_paise(169.40) == 16940
    assert from_paise(16940) == 169.40
    assert to_paise(78262.80) == 7826280
    assert from_paise(7826280) == 78262.80

