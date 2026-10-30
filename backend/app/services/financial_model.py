"""Deterministic financial model for COD Compass.

Implements all assignment-required financial accounting, sensitivity analyses,
and incremental action evaluations relative to the baseline ('Ship As COD As-Is').

Key Principles:
1. Deterministic and fully tested down to the exact rupee and paisa.
2. Sunk CAC (₹300) is NEVER double-subtracted in incremental pre-shipment decisions,
   but is reported transparently as 'Acquisition Spend at Risk'.
3. Configurable delivered gross margin accounting (explaining product COGS vs fulfillment).
4. Direct RTO loss baseline:
   Forward (₹65) + Return (₹65) + Packaging (₹25) + Damage (0.08 * ₹180 = ₹14.40) = ₹169.40.
5. Exact break-even RTO calculation showing when holding/canceling becomes economically net-positive.
6. Exact accounting identity for every pre-shipment action:
   Expected Revenue - Expected COGS - Forward Freight - Return Freight - Packaging - Damage - Messaging - Discount - PG Fees
   == Expected Net Contribution (within 0.01 rounding tolerance).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

from app.models.schemas import ActionType, ActionEconomics, FinancialAssumptions, PolicyConfig


def round_rupees(val: float | Decimal) -> float:
    """Rounds rupee value to 2 decimal places using standard commercial half-up rounding."""
    d = Decimal(str(val)) if not isinstance(val, Decimal) else val
    return float(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def to_paise(rupees: float) -> int:
    """Converts a rupee float into an exact integer number of paise."""
    return int(Decimal(str(rupees)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * 100)


def from_paise(paise: int) -> float:
    """Converts integer paise back to a 2-decimal rupee float."""
    return round_rupees(Decimal(paise) / Decimal(100))


@dataclass(frozen=True)
class AssignmentBaselineMetrics:
    """Baseline metrics as specified directly in assignment requirements."""
    monthly_orders: int = 3000
    cod_share: float = 0.55
    cod_rto_rate: float = 0.28
    prepaid_rto_rate: float = 0.04
    aov: float = 649.0
    forward_shipping: float = 65.0
    return_shipping: float = 65.0
    packaging: float = 25.0
    damage_prob: float = 0.08
    damaged_product_cost: float = 180.0
    cac: float = 300.0

    @property
    def direct_rto_loss_per_return(self) -> float:
        """65 + 65 + 25 + (0.08 * 180) = ₹169.40"""
        expected_damage = self.damage_prob * self.damaged_product_cost
        return round_rupees(self.forward_shipping + self.return_shipping + self.packaging + expected_damage)

    @property
    def monthly_cod_orders(self) -> int:
        """3,000 * 0.55 = 1,650"""
        return int(self.monthly_orders * self.cod_share)

    @property
    def expected_monthly_cod_rtos(self) -> float:
        """1,650 * 0.28 = 462.0"""
        return round_rupees(self.monthly_cod_orders * self.cod_rto_rate)

    @property
    def expected_monthly_direct_rto_loss(self) -> float:
        """462 * 169.40 = ₹78,262.80"""
        return round_rupees(self.expected_monthly_cod_rtos * self.direct_rto_loss_per_return)


class FinancialModelService:
    """Centralized financial computation engine for COD Compass."""

    def __init__(self, assumptions: Optional[FinancialAssumptions] = None):
        self.assumptions = assumptions or FinancialAssumptions()

    def get_assignment_baseline(self) -> AssignmentBaselineMetrics:
        """Returns the canonical assignment baseline parameters."""
        return AssignmentBaselineMetrics()

    def direct_rto_loss(self, assumptions: Optional[FinancialAssumptions] = None) -> float:
        """Calculates expected direct cash loss for an order that results in RTO.

        Loss = Forward Shipping (₹65) + Return Shipping (₹65) + Packaging (₹25)
               + Damage Probability (8%) * Average Damaged Item Cost (₹180)
             = ₹169.40
        """
        p = assumptions or self.assumptions
        expected_damage = p.damaged_product_prob * p.damaged_product_cost
        return round_rupees(
            p.forward_shipping_cost + p.return_shipping_cost + p.packaging_cost + expected_damage
        )

    def delivered_order_contribution(
        self, order_value: float, assumptions: Optional[FinancialAssumptions] = None
    ) -> float:
        """Calculates net gross contribution earned on a successfully delivered order.

        Accounting clarification:
        - Delivered Gross Margin is 62% of gross order value (representing Revenue - COGS).
        - To deliver the order, the brand pays Forward Shipping (₹65) and Packaging (₹25).
        - Net Delivered Contribution = (Order Value * 0.62) - Forward Shipping - Packaging.
        """
        if not isinstance(order_value, (int, float)) or math.isnan(order_value) or math.isinf(order_value) or order_value < 0:
            raise ValueError(f"Invalid order_value: {order_value}. Must be a finite non-negative number.")
        p = assumptions or self.assumptions
        gross_profit = order_value * p.delivered_gross_margin
        net_delivered = gross_profit - p.forward_shipping_cost - p.packaging_cost
        return round_rupees(net_delivered)

    def calculate_cancellation_breakeven_rto(
        self, order_value: float, assumptions: Optional[FinancialAssumptions] = None
    ) -> float:
        """Calculates the mathematical break-even RTO probability above which
        canceling an order saves more cash in avoided RTO than it loses in delivered gross profit.

        Let P = RTO probability.
        If we ship: Expected Value = (1 - P) * Delivered_Contribution - P * Direct_RTO_Loss
        If we cancel: Expected Value = 0 (saving RTO loss, but losing delivered profit).

        Canceling is better when:
            0 > (1 - P) * Delivered_Contribution - P * Direct_RTO_Loss
            P > Delivered_Contribution / (Direct_RTO_Loss + Delivered_Contribution)

        Note on nonpositive delivered contribution:
        If Delivered_Contribution <= 0, the order loses money even if delivered with 0% RTO.
        In this case, shipping is never economically net-positive, so break-even RTO is 0.0.
        """
        if not isinstance(order_value, (int, float)) or math.isnan(order_value) or math.isinf(order_value) or order_value < 0:
            raise ValueError(f"Invalid order_value: {order_value}. Must be a finite non-negative number.")

        delivered_contrib = self.delivered_order_contribution(order_value, assumptions=assumptions)
        rto_loss = self.direct_rto_loss(assumptions=assumptions)

        if delivered_contrib <= 0.0:
            return 0.0

        breakeven_p = delivered_contrib / (rto_loss + delivered_contrib)
        return round(float(breakeven_p), 4)

    def evaluate_order_actions(
        self,
        order_value: float,
        calibrated_rto_prob: float,
        is_suspicious_address: bool = False,
        prior_rto_count: int = 0,
        policy: Optional[PolicyConfig] = None,
        assumptions: Optional[FinancialAssumptions] = None,
        active_hold_review: bool = False,
    ) -> Dict[ActionType, ActionEconomics]:
        """Calculates expected economics and incremental contribution for all 4 pre-shipment actions.

        Baseline comparator is ActionType.SHIP_AS_IS:
        Incremental Advantage = Action_Expected_Contribution - Baseline_Expected_Contribution.

        Guarantees strict accounting identity for EVERY action:
        Revenue - COGS - Forward - Return - Packaging - Damage - Messaging - Discount - PG Fees == Net Contribution
        """
        if not isinstance(order_value, (int, float)) or math.isnan(order_value) or math.isinf(order_value) or order_value < 0:
            raise ValueError(f"Invalid order_value: {order_value}. Must be a finite non-negative number.")
        if not isinstance(calibrated_rto_prob, (int, float)) or math.isnan(calibrated_rto_prob) or math.isinf(calibrated_rto_prob) or not (0.0 <= calibrated_rto_prob <= 1.0):
            raise ValueError(f"Invalid calibrated_rto_prob: {calibrated_rto_prob}. Must be between 0.0 and 1.0.")

        # Ensure unified assumptions: if policy is provided, synchronize prepaid discount
        p = (assumptions or self.assumptions).model_copy()
        if policy is not None:
            p.prepaid_discount_rupees = policy.prepaid_discount_amount

        rto_loss = self.direct_rto_loss(assumptions=p)
        cogs = round_rupees(order_value * (1.0 - p.delivered_gross_margin))
        delivered_contrib = self.delivered_order_contribution(order_value, assumptions=p)
        cac_at_risk = round_rupees(p.customer_acquisition_cost)

        # -------------------------------------------------------------
        # Action 0: Baseline - SHIP_AS_IS (COD As-Is)
        # -------------------------------------------------------------
        p_del_baseline = 1.0 - calibrated_rto_prob
        p_rto_baseline = calibrated_rto_prob

        rev_0 = round_rupees(p_del_baseline * order_value)
        cogs_0 = round_rupees(p_del_baseline * cogs)
        fwd_0 = p.forward_shipping_cost
        ret_0 = round_rupees(p_rto_baseline * p.return_shipping_cost)
        pkg_0 = p.packaging_cost
        dmg_0 = round_rupees(p_rto_baseline * (p.damaged_product_prob * p.damaged_product_cost))
        msg_0 = 0.0
        disc_0 = 0.0
        fee_0 = 0.0

        net_0 = round_rupees(rev_0 - cogs_0 - fwd_0 - ret_0 - pkg_0 - dmg_0 - msg_0 - disc_0 - fee_0)

        baseline_econ = ActionEconomics(
            action=ActionType.SHIP_AS_IS,
            expected_gross_revenue=rev_0,
            expected_cogs=cogs_0,
            expected_forward_shipping=fwd_0,
            expected_return_shipping=ret_0,
            expected_packaging=pkg_0,
            expected_damage_loss=dmg_0,
            expected_messaging_cost=msg_0,
            expected_discount=disc_0,
            expected_payment_fee=fee_0,
            expected_net_contribution=net_0,
            net_advantage_vs_baseline=0.0,
            acquisition_spend_at_risk=round_rupees(p_del_baseline * cac_at_risk),
        )

        # -------------------------------------------------------------
        # Action 1: CONFIRM (WhatsApp Interactive Confirmation)
        # -------------------------------------------------------------
        msg_cost = p.whatsapp_cost_per_conversation
        r = p.confirmation_response_rate

        p_rto_conf = max(0.04, calibrated_rto_prob * 0.40)
        p_del_conf = 1.0 - p_rto_conf

        rev_1 = round_rupees(r * p_del_conf * order_value)
        cogs_1 = round_rupees(r * p_del_conf * cogs)
        fwd_1 = round_rupees(r * p.forward_shipping_cost)
        ret_1 = round_rupees(r * p_rto_conf * p.return_shipping_cost)
        pkg_1 = round_rupees(r * p.packaging_cost)
        dmg_1 = round_rupees(r * p_rto_conf * (p.damaged_product_prob * p.damaged_product_cost))
        msg_1 = msg_cost
        disc_1 = 0.0
        fee_1 = 0.0

        net_1 = round_rupees(rev_1 - cogs_1 - fwd_1 - ret_1 - pkg_1 - dmg_1 - msg_1 - disc_1 - fee_1)

        confirm_econ = ActionEconomics(
            action=ActionType.CONFIRM,
            expected_gross_revenue=rev_1,
            expected_cogs=cogs_1,
            expected_forward_shipping=fwd_1,
            expected_return_shipping=ret_1,
            expected_packaging=pkg_1,
            expected_damage_loss=dmg_1,
            expected_messaging_cost=msg_1,
            expected_discount=disc_1,
            expected_payment_fee=fee_1,
            expected_net_contribution=net_1,
            net_advantage_vs_baseline=round_rupees(net_1 - net_0),
            acquisition_spend_at_risk=round_rupees((1.0 - r) * (1.0 - calibrated_rto_prob) * cac_at_risk),
        )

        # -------------------------------------------------------------
        # Action 2: NUDGE_PREPAID (Prepaid Incentive Offer + Fallback Confirmation)
        # -------------------------------------------------------------
        disc_amount = p.prepaid_discount_rupees
        c = p.prepaid_conversion_rate
        pg_rate = p.payment_gateway_fee_pct

        p_rto_prep = p.prepaid_rto_rate
        p_del_prep = 1.0 - p_rto_prep

        net_paid = max(0.0, order_value - disc_amount)
        pg_fee_unit = net_paid * pg_rate

        # Converted branch (prob c): shipped prepaid
        # Non-converted branch (prob 1-c): fallback to confirmation without duplicate messaging fee
        rev_2 = round_rupees(c * p_del_prep * order_value + (1.0 - c) * r * p_del_conf * order_value)
        cogs_2 = round_rupees(c * p_del_prep * cogs + (1.0 - c) * r * p_del_conf * cogs)
        fwd_2 = round_rupees(c * p.forward_shipping_cost + (1.0 - c) * r * p.forward_shipping_cost)
        ret_2 = round_rupees(c * p_rto_prep * p.return_shipping_cost + (1.0 - c) * r * p_rto_conf * p.return_shipping_cost)
        pkg_2 = round_rupees(c * p.packaging_cost + (1.0 - c) * r * p.packaging_cost)
        dmg_2 = round_rupees(
            c * p_rto_prep * (p.damaged_product_prob * p.damaged_product_cost)
            + (1.0 - c) * r * p_rto_conf * (p.damaged_product_prob * p.damaged_product_cost)
        )
        msg_2 = msg_cost
        disc_2 = round_rupees(c * disc_amount)
        fee_2 = round_rupees(c * pg_fee_unit)

        net_2 = round_rupees(rev_2 - cogs_2 - fwd_2 - ret_2 - pkg_2 - dmg_2 - msg_2 - disc_2 - fee_2)

        nudge_econ = ActionEconomics(
            action=ActionType.NUDGE_PREPAID,
            expected_gross_revenue=rev_2,
            expected_cogs=cogs_2,
            expected_forward_shipping=fwd_2,
            expected_return_shipping=ret_2,
            expected_packaging=pkg_2,
            expected_damage_loss=dmg_2,
            expected_messaging_cost=msg_2,
            expected_discount=disc_2,
            expected_payment_fee=fee_2,
            expected_net_contribution=net_2,
            net_advantage_vs_baseline=round_rupees(net_2 - net_0),
            acquisition_spend_at_risk=round_rupees(
                (1.0 - c) * (1.0 - r) * (1.0 - calibrated_rto_prob) * cac_at_risk
            ),
        )

        # -------------------------------------------------------------
        # Action 3: HOLD (Operational Review Quarantine)
        # -------------------------------------------------------------
        if active_hold_review:
            # Active operational review: outreach collects landmarks on ~70% of genuine orders
            hold_recovery_rate = 0.70
            hold_rto_rate = 0.12
            p_del_hold = 1.0 - hold_rto_rate
            rec = hold_recovery_rate * (1.0 - calibrated_rto_prob)

            rev_3 = round_rupees(rec * p_del_hold * order_value)
            cogs_3 = round_rupees(rec * p_del_hold * cogs)
            fwd_3 = round_rupees(rec * p.forward_shipping_cost)
            ret_3 = round_rupees(rec * hold_rto_rate * p.return_shipping_cost)
            pkg_3 = round_rupees(rec * p.packaging_cost)
            dmg_3 = round_rupees(rec * hold_rto_rate * (p.damaged_product_prob * p.damaged_product_cost))
            msg_3 = msg_cost
            disc_3 = 0.0
            fee_3 = 0.0
            net_3 = round_rupees(rev_3 - cogs_3 - fwd_3 - ret_3 - pkg_3 - dmg_3 - msg_3 - disc_3 - fee_3)
        else:
            # Terminal review / cancellation baseline: no dispatch, zero fulfillment cost or revenue
            rev_3 = 0.0
            cogs_3 = 0.0
            fwd_3 = 0.0
            ret_3 = 0.0
            pkg_3 = 0.0
            dmg_3 = 0.0
            msg_3 = 0.0
            disc_3 = 0.0
            fee_3 = 0.0
            net_3 = 0.0

        hold_econ = ActionEconomics(
            action=ActionType.HOLD,
            expected_gross_revenue=rev_3,
            expected_cogs=cogs_3,
            expected_forward_shipping=fwd_3,
            expected_return_shipping=ret_3,
            expected_packaging=pkg_3,
            expected_damage_loss=dmg_3,
            expected_messaging_cost=msg_3,
            expected_discount=disc_3,
            expected_payment_fee=fee_3,
            expected_net_contribution=net_3,
            net_advantage_vs_baseline=round_rupees(net_3 - net_0),
            acquisition_spend_at_risk=round_rupees((1.0 - calibrated_rto_prob) * cac_at_risk),
        )

        return {
            ActionType.SHIP_AS_IS: baseline_econ,
            ActionType.CONFIRM: confirm_econ,
            ActionType.NUDGE_PREPAID: nudge_econ,
            ActionType.HOLD: hold_econ,
        }

    def evaluate_prepaid_discount_options(
        self,
        order_value: float,
        calibrated_rto_prob: float,
        discounts: Optional[List[float]] = None,
        policy: Optional[PolicyConfig] = None,
        assumptions: Optional[FinancialAssumptions] = None,
    ) -> List[Dict[str, Any]]:
        """Evaluates different prepaid discount levels (e.g. ₹0, ₹15, ₹25, ₹35, ₹50)
        including full non-converter fallback economics, residual RTO, fees, and messaging.
        """
        if not isinstance(order_value, (int, float)) or math.isnan(order_value) or math.isinf(order_value) or order_value < 0:
            raise ValueError(f"Invalid order_value: {order_value}. Must be a finite non-negative number.")
        if not isinstance(calibrated_rto_prob, (int, float)) or math.isnan(calibrated_rto_prob) or not (0.0 <= calibrated_rto_prob <= 1.0):
            raise ValueError(f"Invalid calibrated_rto_prob: {calibrated_rto_prob}.")

        if discounts is None:
            discounts = [0.0, 15.0, 25.0, 35.0, 50.0]

        p = (assumptions or self.assumptions).model_copy()
        if policy is not None:
            p.prepaid_discount_rupees = policy.prepaid_discount_amount

        rto_loss = self.direct_rto_loss(assumptions=p)
        cogs = round_rupees(order_value * (1.0 - p.delivered_gross_margin))
        gross_profit = round_rupees(order_value * p.delivered_gross_margin)
        delivered_contrib = self.delivered_order_contribution(order_value, assumptions=p)
        msg_cost = p.whatsapp_cost_per_conversation

        # Baseline COD expected contribution without nudge intervention
        baseline_cod_ev = round_rupees((1.0 - calibrated_rto_prob) * delivered_contrib - calibrated_rto_prob * rto_loss)

        # Baseline d=0 evaluation
        d0 = 0.0
        c0 = 0.10
        net_val_0 = max(0.0, order_value - d0)
        pg_0 = net_val_0 * p.payment_gateway_fee_pct
        p_del_prep = 1.0 - p.prepaid_rto_rate
        p_rto_prep = p.prepaid_rto_rate

        # Converted prepaid branch net value
        conv_ev_0 = (
            p_del_prep * gross_profit
            - d0
            - pg_0
            - p.forward_shipping_cost
            - p.packaging_cost
            - p_rto_prep * (p.return_shipping_cost + p.damaged_product_prob * p.damaged_product_cost)
        )
        pool_ev_0 = c0 * conv_ev_0 + (1.0 - c0) * baseline_cod_ev - msg_cost

        results = []
        for disc in discounts:
            # Empirical conversion elasticity
            estimated_conv = min(0.45, 0.10 + (disc / 100.0) * 0.60)
            net_val = max(0.0, order_value - disc)
            pg_fee = net_val * p.payment_gateway_fee_pct

            # Converted prepaid branch EV per converted order (with 4% residual RTO)
            conv_ev = (
                p_del_prep * gross_profit
                - disc
                - pg_fee
                - p.forward_shipping_cost
                - p.packaging_cost
                - p_rto_prep * (p.return_shipping_cost + p.damaged_product_prob * p.damaged_product_cost)
            )

            # Full pool expected value per targeted customer
            # (converters achieve conv_ev; nonconverters fall back to baseline COD; minus messaging fee)
            total_pool_ev = (
                estimated_conv * conv_ev
                + (1.0 - estimated_conv) * baseline_cod_ev
                - msg_cost
            )

            # Break-even conversion rate needed for this discount to beat ₹0 discount:
            # c * conv_ev + (1 - c) * baseline_cod_ev - msg_cost >= pool_ev_0
            # c * (conv_ev - baseline_cod_ev) >= pool_ev_0 + msg_cost - baseline_cod_ev
            denom = conv_ev - baseline_cod_ev
            if denom > 0:
                breakeven_conv_pct = round(
                    float(((pool_ev_0 + msg_cost - baseline_cod_ev) / denom) * 100.0), 2
                )
            else:
                breakeven_conv_pct = 100.0

            results.append({
                "discount_rupees": disc,
                "estimated_conversion_rate": round(float(estimated_conv), 4),
                "pg_fee_rupees": round_rupees(pg_fee),
                "net_prepaid_contribution_per_order": round_rupees(conv_ev),
                "nonconverter_fallback_ev": round_rupees(baseline_cod_ev),
                "expected_incremental_pool": round_rupees(total_pool_ev - baseline_cod_ev),
                "total_expected_pool_ev": round_rupees(total_pool_ev),
                "breakeven_conversion_rate_percent": breakeven_conv_pct,
            })

        return results

    def evaluate_cohort_financials(
        self,
        orders: Any,
        policy: Optional[PolicyConfig] = None,
        assumptions: Optional[FinancialAssumptions] = None,
        active_hold_review: bool = True,
        scenario_overrides: Optional[Dict[str, float]] = None,
        scale_to_monthly_orders: Optional[float] = 1650.0,
    ) -> Dict[str, Any]:
        """Unified, single-source-of-truth cohort financial evaluation.

        Reconciles the complete financial bridge across:
        - Avoided RTO freight & damage
        - Changes in delivered gross contribution
        - Prepaid discounts granted
        - WhatsApp interactive messaging costs
        - Payment gateway fees

        Strictly guarantees:
        Reconciliation Discrepancy == 0.00
        Net Financial Improvement == Policy Net - Baseline Net
        """
        # Convert DataFrame or list of dicts to standard list of dicts
        if hasattr(orders, "to_dict"):
            order_list = orders.to_dict(orient="records")
        elif isinstance(orders, list):
            order_list = list(orders)
        else:
            order_list = []

        # Empty cohort handling
        if not order_list:
            return {
                "total_orders": 0,
                "orders_by_action": {act.value: 0 for act in ActionType},
                "baseline_net_contribution_rupees": 0.0,
                "policy_net_contribution_rupees": 0.0,
                "net_financial_improvement_rupees": 0.0,
                "avoided_rto_freight_and_damage_rupees": 0.0,
                "change_in_delivered_contribution_rupees": 0.0,
                "prepaid_incentive_discounts_rupees": 0.0,
                "whatsapp_interactive_messaging_rupees": 0.0,
                "payment_gateway_fees_rupees": 0.0,
                "reconciliation_discrepancy_rupees": 0.0,
                "avoided_rtos_count": 0.0,
                "policy_rtos_count": 0.0,
                "baseline_rtos_count": 0.0,
                "baseline_rto_rate": 0.0,
                "policy_rto_rate": 0.0,
                "monthly_scaled_projection": {
                    "scale_factor_exact": 0.0,
                    "projected_monthly_avoided_rtos": 0.0,
                    "projected_avoided_rto_freight_rupees": 0.0,
                    "projected_change_in_delivered_contribution_rupees": 0.0,
                    "projected_prepaid_discounts_rupees": 0.0,
                    "projected_messaging_costs_rupees": 0.0,
                    "projected_payment_gateway_fees_rupees": 0.0,
                    "projected_net_monthly_gain_rupees": 0.0,
                },
            }

        p = (assumptions or self.assumptions).model_copy()
        if policy is not None:
            p.prepaid_discount_rupees = policy.prepaid_discount_amount

        direct_rto_loss_unit = self.direct_rto_loss(assumptions=p)

        overrides = scenario_overrides or {}
        p_conf_resp = overrides.get("confirm_response_rate", p.confirmation_response_rate)
        p_conf_rto = overrides.get("confirmed_rto_rate", 0.12)
        p_prep_conv = overrides.get("prepaid_conversion_rate", p.prepaid_conversion_rate)
        p_prep_rto = overrides.get("prepaid_residual_rto_rate", p.prepaid_rto_rate)
        p_hold_recov = overrides.get("hold_recovery_rate", 0.70 if active_hold_review else 0.0)
        p_hold_leakage = overrides.get("hold_rto_leakage_rate", 0.0)

        # Action distribution count
        action_counts = {act.value: 0 for act in ActionType}
        for o in order_list:
            act_val = o.get("recommended_action") or ActionType.SHIP_AS_IS.value
            if hasattr(act_val, "value"):
                act_val = act_val.value
            action_counts[act_val] = action_counts.get(act_val, 0) + 1

        # Check if ground truth status is present (DELIVERED / RTO)
        has_ground_truth = any(
            str(o.get("status_normalized") or o.get("actual_status") or o.get("final_status") or "").strip().upper()
            in ("DELIVERED", "RTO")
            for o in order_list
        )

        total_orders_count = len(order_list)

        if has_ground_truth:
            def get_status(o: Dict[str, Any]) -> str:
                return str(o.get("status_normalized") or o.get("actual_status") or o.get("final_status") or "").strip().upper()

            delivered_orders = [o for o in order_list if get_status(o) == "DELIVERED"]
            rto_orders = [o for o in order_list if get_status(o) == "RTO"]

            obs_deliv_rev = sum(float(o.get("order_value", 0.0)) for o in delivered_orders)
            base_deliv_contrib = (obs_deliv_rev * p.delivered_gross_margin) - (
                len(delivered_orders) * (p.forward_shipping_cost + p.packaging_cost)
            )
            base_rto_cost = len(rto_orders) * direct_rto_loss_unit
            base_net_contrib = base_deliv_contrib - base_rto_cost

            # Bucket 1: SHIP_AS_IS
            ship_orders = [
                o for o in order_list
                if (o.get("recommended_action") or ActionType.SHIP_AS_IS.value) in (ActionType.SHIP_AS_IS.value, ActionType.SHIP_AS_IS)
            ]
            ship_deliv = [o for o in ship_orders if get_status(o) == "DELIVERED"]
            ship_rto = [o for o in ship_orders if get_status(o) == "RTO"]
            ship_deliv_cnt = len(ship_deliv)
            ship_rto_cnt = len(ship_rto)
            ship_deliv_rev = sum(float(o.get("order_value", 0.0)) for o in ship_deliv)
            ship_deliv_contrib = (ship_deliv_rev * p.delivered_gross_margin) - (
                ship_deliv_cnt * (p.forward_shipping_cost + p.packaging_cost)
            )
            ship_rto_cost = ship_rto_cnt * direct_rto_loss_unit

            # Bucket 2: CONFIRM
            confirm_orders = [
                o for o in order_list
                if (o.get("recommended_action") or "") in (ActionType.CONFIRM.value, ActionType.CONFIRM)
            ]
            confirm_cnt = len(confirm_orders)
            confirm_val_sum = sum(float(o.get("order_value", 0.0)) for o in confirm_orders)
            mean_confirm_val = (confirm_val_sum / float(confirm_cnt)) if confirm_cnt > 0 else 0.0
            confirm_msg_cost = confirm_cnt * p.whatsapp_cost_per_conversation

            confirmed_cnt = confirm_cnt * p_conf_resp
            confirmed_rto_cnt = confirmed_cnt * p_conf_rto
            confirmed_deliv_cnt = confirmed_cnt - confirmed_rto_cnt
            confirmed_deliv_contrib = (
                confirmed_deliv_cnt * mean_confirm_val * p.delivered_gross_margin
            ) - (confirmed_deliv_cnt * (p.forward_shipping_cost + p.packaging_cost))
            confirmed_rto_cost = confirmed_rto_cnt * direct_rto_loss_unit

            ghosted_cnt = confirm_cnt * (1.0 - p_conf_resp)
            ghosted_genuine_cnt = ghosted_cnt * (1.0 - 0.65)
            recovered_ghosted_deliv_cnt = ghosted_genuine_cnt * (0.35 if p_conf_resp >= 0.70 else 0.20)
            recovered_ghosted_deliv_contrib = (
                recovered_ghosted_deliv_cnt * mean_confirm_val * p.delivered_gross_margin
            ) - (recovered_ghosted_deliv_cnt * (p.forward_shipping_cost + p.packaging_cost))

            confirm_tot_deliv_contrib = confirmed_deliv_contrib + recovered_ghosted_deliv_contrib
            confirm_tot_rto_cost = confirmed_rto_cost

            # Bucket 3: NUDGE_PREPAID
            nudge_orders = [
                o for o in order_list
                if (o.get("recommended_action") or "") in (ActionType.NUDGE_PREPAID.value, ActionType.NUDGE_PREPAID)
            ]
            nudge_cnt = len(nudge_orders)
            nudge_val_sum = sum(float(o.get("order_value", 0.0)) for o in nudge_orders)
            mean_nudge_val = (nudge_val_sum / float(nudge_cnt)) if nudge_cnt > 0 else 0.0
            nudge_msg_cost = nudge_cnt * (p.whatsapp_cost_per_conversation * 1.20)

            prepaid_conv_cnt = nudge_cnt * p_prep_conv
            prepaid_rto_cnt = prepaid_conv_cnt * p_prep_rto
            prepaid_deliv_cnt = prepaid_conv_cnt - prepaid_rto_cnt
            prepaid_deliv_contrib = (
                prepaid_deliv_cnt * mean_nudge_val * p.delivered_gross_margin
            ) - (prepaid_deliv_cnt * (p.forward_shipping_cost + p.packaging_cost))
            prepaid_rto_cost = prepaid_rto_cnt * direct_rto_loss_unit
            prepaid_disc = prepaid_conv_cnt * p.prepaid_discount_rupees
            prepaid_pg = prepaid_conv_cnt * (
                max(0.0, mean_nudge_val - p.prepaid_discount_rupees) * p.payment_gateway_fee_pct
            )

            unconv_cnt = nudge_cnt * (1.0 - p_prep_conv)
            unconv_confirmed_cnt = unconv_cnt * p_conf_resp
            unconv_rto_cnt = unconv_confirmed_cnt * p_conf_rto
            unconv_deliv_cnt = unconv_confirmed_cnt - unconv_rto_cnt
            unconv_deliv_contrib = (
                unconv_deliv_cnt * mean_nudge_val * p.delivered_gross_margin
            ) - (unconv_deliv_cnt * (p.forward_shipping_cost + p.packaging_cost))
            unconv_rto_cost = unconv_rto_cnt * direct_rto_loss_unit

            nudge_tot_deliv_contrib = prepaid_deliv_contrib + unconv_deliv_contrib
            nudge_tot_rto_cost = prepaid_rto_cost + unconv_rto_cost
            nudge_tot_disc = prepaid_disc
            nudge_tot_pg = prepaid_pg

            # Bucket 4: HOLD
            hold_orders = [
                o for o in order_list
                if (o.get("recommended_action") or "") in (ActionType.HOLD.value, ActionType.HOLD)
            ]
            hold_deliv = [o for o in hold_orders if get_status(o) == "DELIVERED"]
            hold_rto = [o for o in hold_orders if get_status(o) == "RTO"]
            hold_deliv_cnt = len(hold_deliv)
            hold_rto_cnt = len(hold_rto)
            hold_deliv_rev = sum(float(o.get("order_value", 0.0)) for o in hold_deliv)

            recovered_hold_cnt = hold_deliv_cnt * p_hold_recov
            mean_hold_deliv_val = (hold_deliv_rev / float(hold_deliv_cnt)) if hold_deliv_cnt > 0 else 0.0
            recovered_hold_val = mean_hold_deliv_val * recovered_hold_cnt
            hold_tot_deliv_contrib = (recovered_hold_val * p.delivered_gross_margin) - (
                recovered_hold_cnt * (p.forward_shipping_cost + p.packaging_cost)
            )

            residual_hold_rto_cnt = hold_rto_cnt * p_hold_leakage
            hold_tot_rto_cost = residual_hold_rto_cnt * direct_rto_loss_unit

            # Sum total policy outcomes
            policy_deliv_contrib = (
                ship_deliv_contrib + confirm_tot_deliv_contrib + nudge_tot_deliv_contrib + hold_tot_deliv_contrib
            )
            policy_rto_cost = (
                ship_rto_cost + confirm_tot_rto_cost + nudge_tot_rto_cost + hold_tot_rto_cost
            )
            policy_msg_cost = confirm_msg_cost + nudge_msg_cost
            policy_disc = nudge_tot_disc
            policy_pg = nudge_tot_pg

            policy_net_contrib = (
                policy_deliv_contrib - policy_rto_cost - policy_msg_cost - policy_disc - policy_pg
            )

            avoided_rto_savings = base_rto_cost - policy_rto_cost
            change_in_deliv_contrib = policy_deliv_contrib - base_deliv_contrib
            net_gain = policy_net_contrib - base_net_contrib
            policy_rto_count = policy_rto_cost / direct_rto_loss_unit
            avoided_rtos_count = float(len(rto_orders)) - policy_rto_count
            baseline_rto_count = float(len(rto_orders))

        else:
            # Expected value calculations when ground truth is absent
            base_deliv_contrib = 0.0
            base_rto_cost = 0.0
            policy_deliv_contrib = 0.0
            policy_rto_cost = 0.0
            policy_msg_cost = 0.0
            policy_disc = 0.0
            policy_pg = 0.0
            baseline_rto_count = 0.0
            policy_rto_count = 0.0

            for o in order_list:
                val = float(o.get("order_value", 649.0))
                prob = float(o.get("risk_score") or o.get("calibrated_rto_prob") or 0.284)
                act_str = o.get("recommended_action") or ActionType.SHIP_AS_IS.value
                try:
                    act_enum = ActionType(act_str)
                except Exception:
                    act_enum = ActionType.SHIP_AS_IS

                econ_map = self.evaluate_order_actions(
                    order_value=val,
                    calibrated_rto_prob=prob,
                    policy=policy,
                    assumptions=p,
                    active_hold_review=active_hold_review,
                )
                b = econ_map[ActionType.SHIP_AS_IS]
                c = econ_map[act_enum]

                # Baseline accumulation
                base_deliv_contrib += b.expected_gross_revenue - b.expected_cogs - b.expected_forward_shipping - b.expected_packaging
                base_rto_cost += b.expected_return_shipping + b.expected_damage_loss
                baseline_rto_count += prob

                # Policy accumulation
                policy_deliv_contrib += c.expected_gross_revenue - c.expected_cogs - c.expected_forward_shipping - c.expected_packaging
                policy_rto_cost += c.expected_return_shipping + c.expected_damage_loss
                policy_msg_cost += c.expected_messaging_cost
                policy_disc += c.expected_discount
                policy_pg += c.expected_payment_fee
                policy_rto_count += (c.expected_return_shipping / p.return_shipping_cost) if p.return_shipping_cost > 0 else prob

            base_net_contrib = base_deliv_contrib - base_rto_cost
            policy_net_contrib = policy_deliv_contrib - policy_rto_cost - policy_msg_cost - policy_disc - policy_pg
            avoided_rto_savings = base_rto_cost - policy_rto_cost
            change_in_deliv_contrib = policy_deliv_contrib - base_deliv_contrib
            net_gain = policy_net_contrib - base_net_contrib
            avoided_rtos_count = baseline_rto_count - policy_rto_count

        bridge_check = avoided_rto_savings + change_in_deliv_contrib - policy_disc - policy_msg_cost - policy_pg
        discrepancy = round(bridge_check - net_gain, 6)

        baseline_rto_rate = round(baseline_rto_count / float(total_orders_count), 4) if total_orders_count > 0 else 0.0
        policy_rto_rate = round(policy_rto_count / float(total_orders_count), 4) if total_orders_count > 0 else 0.0

        scale_factor = (scale_to_monthly_orders / float(total_orders_count)) if (scale_to_monthly_orders and total_orders_count > 0) else 1.0

        return {
            "total_orders": total_orders_count,
            "orders_by_action": action_counts,
            "baseline_net_contribution_rupees": round(base_net_contrib, 2),
            "policy_net_contribution_rupees": round(policy_net_contrib, 2),
            "net_financial_improvement_rupees": round(net_gain, 2),
            "avoided_rto_freight_and_damage_rupees": round(avoided_rto_savings, 2),
            "change_in_delivered_contribution_rupees": round(change_in_deliv_contrib, 2),
            "prepaid_incentive_discounts_rupees": round(-policy_disc, 2),
            "whatsapp_interactive_messaging_rupees": round(-policy_msg_cost, 2),
            "payment_gateway_fees_rupees": round(-policy_pg, 2),
            "reconciliation_discrepancy_rupees": round(discrepancy, 6),
            "avoided_rtos_count": round(avoided_rtos_count, 3),
            "policy_rtos_count": round(policy_rto_count, 3),
            "baseline_rtos_count": round(baseline_rto_count, 3),
            "baseline_rto_rate": baseline_rto_rate,
            "policy_rto_rate": policy_rto_rate,
            "monthly_scaled_projection": {
                "scale_factor_exact": scale_factor,
                "projected_monthly_avoided_rtos": round(avoided_rtos_count * scale_factor, 1),
                "projected_avoided_rto_freight_rupees": round(avoided_rto_savings * scale_factor, 2),
                "projected_change_in_delivered_contribution_rupees": round(change_in_deliv_contrib * scale_factor, 2),
                "projected_prepaid_discounts_rupees": round(-policy_disc * scale_factor, 2),
                "projected_messaging_costs_rupees": round(-policy_msg_cost * scale_factor, 2),
                "projected_payment_gateway_fees_rupees": round(-policy_pg * scale_factor, 2),
                "projected_net_monthly_gain_rupees": round(net_gain * scale_factor, 2),
            },
        }
