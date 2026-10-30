"""Pre-shipment Decision Engine for COD Compass.

Strictly separates Risk Scoring from Business Action Selection.
Evaluates pre-shipment financial trade-offs in rupees, applies policy thresholds,
and generates plain-English notes for operations staff.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.models.schemas import (
    ActionType,
    ActionEconomics,
    OrderBase,
    OrderEvaluation,
    PolicyConfig,
    RiskBand,
)
from app.services.financial_model import FinancialModelService, round_rupees
from app.services.llm_adapter import LLMAdapterService
from app.services.risk_model import RiskModelService


class DecisionEngineService:
    """Evaluates orders and issues recommended pre-shipment actions with economic provenance."""

    def __init__(
        self,
        risk_model: Optional[RiskModelService] = None,
        financial_model: Optional[FinancialModelService] = None,
        llm_adapter: Optional[LLMAdapterService] = None,
    ):
        self.risk_model = risk_model or RiskModelService()
        self.financial_model = financial_model or FinancialModelService()
        self.llm_adapter = llm_adapter or LLMAdapterService()

    def evaluate_order(
        self,
        order: OrderBase,
        policy: Optional[PolicyConfig] = None,
    ) -> OrderEvaluation:
        """Runs the complete pre-shipment evaluation pipeline on a single order."""
        if policy is None:
            policy = PolicyConfig()

        # Step 1: Pre-shipment feature extraction & address verification
        addr_analysis = self.llm_adapter.analyze_address_completeness(
            address=order.address,
            city=order.city,
            pincode=order.pincode,
        )

        # Step 2: Leakage-free risk probability scoring
        risk_score, uncertainty_flag = self.risk_model.predict_order_risk(
            order_value=order.order_value,
            customer_name=order.customer_name,
            address=order.address,
            pincode=order.pincode,
            customer_prior_rto=order.customer_prior_rto,
            customer_prior_orders=order.customer_prior_orders,
            utm_source=order.utm_source,
            min_pincode_sample=policy.min_pincode_sample,
        )
        risk_band = self.risk_model.get_risk_band(risk_score)

        # Step 3: Deterministic Financial Evaluation across all 4 actions
        action_economics = self.financial_model.evaluate_order_actions(
            order_value=order.order_value,
            calibrated_rto_prob=risk_score,
            is_suspicious_address=not addr_analysis["is_deliverable"],
            prior_rto_count=order.customer_prior_rto,
            policy=policy,
        )

        # Build comprehensive assumptions snapshot for decision provenance
        assumptions_snapshot = {
            "policy_id": policy.policy_id,
            "policy_version": policy.version,
            "low_risk_threshold": policy.low_risk_threshold,
            "confirm_threshold": policy.confirm_threshold,
            "nudge_threshold": policy.nudge_threshold,
            "hold_threshold": policy.hold_threshold,
            "prepaid_discount_amount": policy.prepaid_discount_amount,
            "prepaid_discount_rupees": policy.prepaid_discount_amount,
            "require_confirm_above_value": policy.require_confirm_above_value,
            "min_pincode_sample": policy.min_pincode_sample,
            "forward_shipping_cost": self.financial_model.assumptions.forward_shipping_cost,
            "return_shipping_cost": self.financial_model.assumptions.return_shipping_cost,
            "packaging_cost": self.financial_model.assumptions.packaging_cost,
            "direct_rto_loss": self.financial_model.direct_rto_loss(),
            "delivered_gross_margin": self.financial_model.assumptions.delivered_gross_margin,
            "whatsapp_cost_per_conversation": self.financial_model.assumptions.whatsapp_cost_per_conversation,
            "confirmation_response_rate": self.financial_model.assumptions.confirmation_response_rate,
            "prepaid_conversion_rate": self.financial_model.assumptions.prepaid_conversion_rate,
            "prepaid_rto_rate": self.financial_model.assumptions.prepaid_rto_rate,
            "payment_gateway_fee_pct": self.financial_model.assumptions.payment_gateway_fee_pct,
        }

        # Step 4: Safety & Policy Review Flags
        review_flags: List[str] = []
        data_limitations: List[str] = []

        if addr_analysis.get("prompt_injection_flag"):
            review_flags.append("SECURITY_FLAG: Prompt injection pattern detected in order input.")

        if not addr_analysis["is_deliverable"]:
            review_flags.append(
                f"ADDRESS_QUALITY_FLAG: Incomplete address (score: {addr_analysis['completeness_score']}). "
                f"Missing: {', '.join(addr_analysis['missing_components'])}"
            )

        if order.order_value >= policy.require_confirm_above_value:
            review_flags.append(
                f"HIGH_BASKET_VALUE: Order value ₹{order.order_value:.0f} exceeds policy threshold ₹{policy.require_confirm_above_value:.0f}."
            )

        if order.customer_prior_rto >= 2:
            review_flags.append(
                f"REPEAT_RTO_HISTORY: Customer has {order.customer_prior_rto} prior RTOs on record."
            )

        if risk_score > policy.hold_threshold:
            review_flags.append(
                f"EXTREME_RISK_FLAG: Risk score {risk_score*100:.1f}% exceeds policy hold threshold {policy.hold_threshold*100:.0f}%."
            )

        if uncertainty_flag:
            data_limitations.append(
                f"SPARSE_PINCODE_DATA: Pincode {order.pincode} has fewer than {policy.min_pincode_sample} "
                "historical orders; risk score is smoothed toward the national baseline (28.4%)."
            )

        # Step 5: Action Selection Logic with Explicit Hierarchy:
        # Precedence Hierarchy:
        # 1. Security / Address Hard Stops (HOLD)
        # 2. Extreme-Risk Safeguard (HOLD if risk_score > hold_threshold)
        # 3. Customer History Overrides (NUDGE_PREPAID if prior_rto >= 2)
        # 4. Basket Value Overrides (CONFIRM if order_value >= require_confirm_above_value)
        # 5. Remaining Contiguous Risk Bands (SHIP_AS_IS <= low < CONFIRM <= confirm < NUDGE_PREPAID <= hold)
        recommended_action: ActionType
        explanation: str
        ops_note: str

        direct_loss = self.financial_model.direct_rto_loss()
        delivered_margin = self.financial_model.delivered_order_contribution(order.order_value)
        breakeven_p = self.financial_model.calculate_cancellation_breakeven_rto(order.order_value)

        # Priority 1: Security prompt injection -> ALWAYS HOLD
        if addr_analysis.get("prompt_injection_flag"):
            recommended_action = ActionType.HOLD
            explanation = "Suspicious input detected matching automated prompt injection pattern."
            ops_note = "HOLD for manual security verification. Do not ship without human review."

        # Priority 2: Incomplete / bogus address -> HOLD for address correction
        elif not addr_analysis["is_deliverable"]:
            recommended_action = ActionType.HOLD
            explanation = f"Address lacks critical delivery landmarks (Completeness: {addr_analysis['completeness_score'] * 100:.0f}%)."
            ops_note = (
                f"Missing: {', '.join(addr_analysis['missing_components'])}. "
                f"Historical RTO on incomplete addresses is ~64%. Message customer to collect landmark before shipping."
            )

        # Priority 3: Extreme Risk Safeguard (Overrides high basket or prior RTO when risk is extreme)
        elif risk_score > policy.hold_threshold:
            recommended_action = ActionType.HOLD
            if risk_score > breakeven_p:
                explanation = (
                    f"Extreme RTO risk ({risk_score * 100:.1f}%) exceeds economic break-even threshold ({breakeven_p * 100:.1f}%) "
                    f"for basket ₹{order.order_value:.0f} — shipping as COD has negative expected contribution."
                )
                ops_note = (
                    f"At {risk_score * 100:.1f}% risk, expected direct loss (₹{risk_score * direct_loss:.2f}) "
                    f"exceeds expected delivered gross contribution (₹{(1 - risk_score) * delivered_margin:.2f}). "
                    "Hold for manual supervisor review or require full upfront payment."
                )
            else:
                explanation = (
                    f"Elevated RTO risk ({risk_score * 100:.1f}%) exceeds policy hold threshold ({policy.hold_threshold * 100:.0f}%), "
                    f"though below basket break-even ({breakeven_p * 100:.1f}%) — held as policy safety safeguard."
                )
                ops_note = (
                    f"Basket contribution is high (₹{delivered_margin:.2f}), making economic break-even {breakeven_p * 100:.1f}%. "
                    "Held as policy safeguard for address/identity verification before committing freight."
                )

        # Priority 4: Severe chronic RTO history (>=2 prior returns) -> NUDGE TO PREPAID
        elif order.customer_prior_rto >= 2:
            recommended_action = ActionType.NUDGE_PREPAID
            explanation = (
                f"Customer has {order.customer_prior_rto} prior COD returns (empirical RTO rate: 76.5%). "
                f"Offering upfront payment with ₹{policy.prepaid_discount_amount:.0f} discount protects unit economics."
            )
            ops_note = (
                f"Direct RTO loss of ₹{direct_loss:.2f} is highly probable on COD. "
                f"Offering ₹{policy.prepaid_discount_amount:.0f} discount on ₹{order.order_value:.0f} basket "
                f"converts payment upfront, reducing return risk to a residual ~4%."
            )

        # Priority 5: High Value Basket above threshold -> CONFIRM
        elif order.order_value >= policy.require_confirm_above_value:
            recommended_action = ActionType.CONFIRM
            explanation = (
                f"High-value order (₹{order.order_value:.0f} >= ₹{policy.require_confirm_above_value:.0f}). "
                "Requires WhatsApp confirmation before dispatch."
            )
            ops_note = (
                f"Potential delivered contribution is ₹{delivered_margin:.2f}. "
                f"WhatsApp confirmation verifies buyer intent before incurring ₹{direct_loss:.2f} return exposure."
            )

        # Priority 6: Contiguous Risk Bands (Gap-Free)
        elif risk_score <= policy.low_risk_threshold:
            recommended_action = ActionType.SHIP_AS_IS
            explanation = f"Low calibrated RTO risk ({risk_score * 100:.1f}% <= {policy.low_risk_threshold * 100:.0f}%). Clean shipping profile."
            ops_note = (
                f"Order expected contribution is ₹{action_economics[ActionType.SHIP_AS_IS].expected_net_contribution:.2f}. "
                "Dispatch immediately to minimize fulfillment cycle time."
            )

        elif risk_score <= policy.confirm_threshold:
            recommended_action = ActionType.CONFIRM
            explanation = (
                f"Moderate RTO risk ({risk_score * 100:.1f}%). WhatsApp confirmation optimizes net expected contribution."
            )
            ops_note = (
                f"Confirmation yields ₹{action_economics[ActionType.CONFIRM].net_advantage_vs_baseline:+.2f} "
                "incremental expected contribution vs unverified shipping."
            )

        else:
            # risk_score <= policy.hold_threshold (which equals nudge_threshold in contiguous policy)
            recommended_action = ActionType.NUDGE_PREPAID
            explanation = (
                f"Elevated RTO risk ({risk_score * 100:.1f}%). Prepaid nudge with ₹{policy.prepaid_discount_amount:.0f} "
                "discount minimizes return probability while securing order value."
            )
            ops_note = (
                f"Prepaid conversion expected advantage is ₹{action_economics[ActionType.NUDGE_PREPAID].net_advantage_vs_baseline:+.2f} "
                f"over unverified COD, while preserving ₹{action_economics[ActionType.NUDGE_PREPAID].acquisition_spend_at_risk:.2f} customer acquisition investment."
            )

        advantage = action_economics[recommended_action].net_advantage_vs_baseline

        return OrderEvaluation(
            order_id=order.order_id,
            recommended_action=recommended_action,
            explanation=explanation,
            plain_english_ops_note=ops_note,
            risk_score=risk_score,
            risk_band=risk_band,
            uncertainty_flag=uncertainty_flag,
            data_limitations=data_limitations,
            review_flags=review_flags,
            action_economics=action_economics,
            recommended_advantage_rupees=advantage,
            policy_version=policy.policy_id,
            model_version=self.risk_model.model_version,
            is_fallback=self.llm_adapter.is_fallback,
            evaluated_at=datetime.utcnow(),
            assumptions_snapshot=assumptions_snapshot,
        )

