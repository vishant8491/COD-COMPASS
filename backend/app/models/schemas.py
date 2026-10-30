"""Pydantic schemas for COD Compass.

All data types are strictly typed with validation and documentation.
Financial numbers are available both as standard rupee floats for serialization
and integer paise where exact calculation is required.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class ActionType(str, Enum):
    """The four canonical pre-shipment actions required by COD Compass."""
    SHIP_AS_IS = "SHIP_AS_IS"
    CONFIRM = "CONFIRM"
    NUDGE_PREPAID = "NUDGE_PREPAID"
    HOLD = "HOLD"


class OperationalStatus(str, Enum):
    """Operational lifecycle statuses tracked in COD Compass."""
    NEW = "NEW"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    PREPAID_CONVERTED = "PREPAID_CONVERTED"
    HELD_FOR_REVIEW = "HELD_FOR_REVIEW"
    CANCELLED = "CANCELLED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    RTO = "RTO"
    IN_TRANSIT = "IN_TRANSIT"


class RiskBand(str, Enum):
    """Calibrated risk tier."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# -------------------------------------------------------------------------
# Order Schemas
# -------------------------------------------------------------------------

class OrderBase(BaseModel):
    order_id: str = Field(..., description="Unique merchant order ID, e.g. KT100001")
    order_datetime: datetime = Field(..., description="Order placement timestamp in UTC or IST")
    customer_name: str = Field(..., description="Customer full name from checkout")
    phone: str = Field(..., description="Customer phone as string to preserve leading digits")
    address: str = Field(..., description="Shipping street address")
    city: str = Field(..., description="Shipping city")
    state: str = Field(..., description="Shipping state")
    pincode: str = Field(..., description="Postal PIN code string (6 digits in India)")
    order_value: float = Field(..., ge=0.0, description="Gross order value in INR (rupees)")
    items: str = Field(..., description="Description or SKU summary of items ordered")
    num_items: int = Field(default=1, ge=1, description="Quantity of items")
    customer_prior_orders: int = Field(default=0, ge=0, description="Customer prior order count")
    customer_prior_rto: int = Field(default=0, ge=0, description="Customer prior RTO count")
    utm_source: Optional[str] = Field(default="unknown", description="Marketing acquisition source")
    courier: Optional[str] = Field(default=None, description="Assigned courier (only post-decision)")
    payment_method: str = Field(default="COD", description="COD or PREPAID")
    final_status: Optional[str] = Field(default=None, description="Historical ground truth outcome")
    operational_status: OperationalStatus = Field(
        default=OperationalStatus.NEW,
        description="Current operational lifecycle state"
    )

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, v: str) -> str:
        clean = "".join(ch for ch in str(v) if ch.isdigit())
        return clean or str(v)

    @field_validator("pincode")
    @classmethod
    def clean_pincode(cls, v: str) -> str:
        clean = "".join(ch for ch in str(v) if ch.isdigit())
        return clean[:6] if clean else str(v)


class OrderCreate(OrderBase):
    pass


class OrderOut(OrderBase):
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Joined decision fields for convenience in UI
    latest_recommendation: Optional[ActionType] = None
    latest_risk_score: Optional[float] = None
    latest_explanation: Optional[str] = None

    model_config = {"from_attributes": True}


# -------------------------------------------------------------------------
# Financial Schemas
# -------------------------------------------------------------------------

class FinancialAssumptions(BaseModel):
    """Core business assumptions (defaults match assignment specifications)."""
    monthly_orders: int = Field(default=3000, description="Monthly total order volume")
    cod_share: float = Field(default=0.55, ge=0.0, le=1.0, description="COD order share (55%)")
    cod_rto_rate: float = Field(default=0.28, ge=0.0, le=1.0, description="Baseline COD RTO rate (28%)")
    prepaid_rto_rate: float = Field(default=0.04, ge=0.0, le=1.0, description="Prepaid RTO rate (4%)")
    average_order_value: float = Field(default=649.0, ge=0.0, description="AOV in INR")
    delivered_gross_margin: float = Field(default=0.62, ge=0.0, le=1.0, description="Gross margin on delivered")
    forward_shipping_cost: float = Field(default=65.0, ge=0.0, description="Forward shipping fee")
    return_shipping_cost: float = Field(default=65.0, ge=0.0, description="Return shipping fee")
    packaging_cost: float = Field(default=25.0, ge=0.0, description="Packaging & handling cost")
    damaged_product_cost: float = Field(default=180.0, ge=0.0, description="Average damaged item cost")
    damaged_product_prob: float = Field(default=0.08, ge=0.0, le=1.0, description="Probability of return damage")
    customer_acquisition_cost: float = Field(default=300.0, ge=0.0, description="Sunk marketing CAC per order")
    # Operational costs & conversion rates
    whatsapp_cost_per_conversation: float = Field(default=0.80, ge=0.0, description="WhatsApp utility session cost")
    confirmation_response_rate: float = Field(default=0.70, ge=0.0, le=1.0, description="Expected confirmation rate")
    confirmation_abandonment_is_rto_bias: float = Field(
        default=0.65, ge=0.0, le=1.0,
        description="Fraction of abandoned orders that would have RTO'd"
    )
    prepaid_conversion_rate: float = Field(default=0.22, ge=0.0, le=1.0, description="Nudge to prepaid conversion")
    payment_gateway_fee_pct: float = Field(default=0.02, ge=0.0, le=0.10, description="PG fee on prepaid (2%)")
    prepaid_discount_rupees: float = Field(default=25.0, ge=0.0, description="Prepaid incentive discount")


class ActionEconomics(BaseModel):
    """Deterministic expected rupee economics for a specific pre-shipment action."""
    action: ActionType
    expected_gross_revenue: float
    expected_cogs: float
    expected_forward_shipping: float
    expected_return_shipping: float
    expected_packaging: float
    expected_damage_loss: float
    expected_messaging_cost: float
    expected_discount: float
    expected_payment_fee: float
    expected_net_contribution: float
    net_advantage_vs_baseline: float = Field(
        ...,
        description="Incremental contribution compared to shipping as COD as-is"
    )
    acquisition_spend_at_risk: float = Field(
        ...,
        description="Reported transparently as marketing CAC at risk (not double-subtracted)"
    )


class OrderEvaluation(BaseModel):
    """Full decision output returned by the engine for an order."""
    order_id: str
    recommended_action: ActionType
    explanation: str
    plain_english_ops_note: str
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Calibrated RTO probability")
    risk_band: RiskBand
    uncertainty_flag: bool = Field(
        ...,
        description="True if prediction has high uncertainty (e.g. low sample pincode)"
    )
    data_limitations: List[str] = Field(default_factory=list)
    review_flags: List[str] = Field(default_factory=list)
    action_economics: Dict[str, ActionEconomics]
    recommended_advantage_rupees: float
    policy_version: str
    model_version: str
    is_fallback: bool = Field(
        default=False,
        description="True if offline heuristic fallback was used instead of live LLM"
    )
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    assumptions_snapshot: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Snapshot of financial assumptions and policy parameters applied for this evaluation"
    )


# -------------------------------------------------------------------------
# Policy Configuration Schemas
# -------------------------------------------------------------------------

class PolicyConfig(BaseModel):
    id: Optional[int] = None
    policy_id: str = Field(default="default_v1", description="Policy slug or version code")
    version: int = Field(default=1, ge=1)
    name: str = Field(default="Balanced Margin & Growth Policy")
    description: str = Field(
        default="Recommended production policy balancing RTO loss prevention with customer conversion."
    )
    low_risk_threshold: float = Field(default=0.20, ge=0.0, le=1.0, description="Score <= threshold -> Ship As-Is")
    confirm_threshold: float = Field(default=0.35, ge=0.0, le=1.0, description="Score between low and confirm -> Confirm")
    nudge_threshold: float = Field(default=0.65, ge=0.0, le=1.0, description="Score between confirm and nudge -> Nudge")
    hold_threshold: float = Field(default=0.65, ge=0.0, le=1.0, description="Score > hold_threshold -> Hold")
    prepaid_discount_amount: float = Field(default=25.0, ge=0.0, description="Prepaid incentive discount (₹)")
    auto_cancel_enabled: bool = Field(default=False, description="Whether extreme risk triggers auto-cancel vs hold")
    require_confirm_above_value: float = Field(default=1500.0, ge=0.0, description="Force confirmation above basket size")
    min_pincode_sample: int = Field(default=5, ge=1, description="Minimum orders before trusting raw pincode RTO rate")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def validate_thresholds(self) -> PolicyConfig:
        if not (0.0 <= self.low_risk_threshold < self.confirm_threshold <= self.nudge_threshold <= 1.0):
            raise ValueError(
                f"Policy thresholds must be strictly ordered: "
                f"0.0 <= low ({self.low_risk_threshold}) < confirm ({self.confirm_threshold}) <= nudge ({self.nudge_threshold}) <= 1.0"
            )
        if self.hold_threshold < self.nudge_threshold:
            raise ValueError(
                f"Contradictory configuration: hold_threshold ({self.hold_threshold}) cannot be less than nudge_threshold ({self.nudge_threshold})"
            )
        return self


class PolicyPreviewRequest(BaseModel):
    policy: PolicyConfig
    sample_size: int = Field(default=500, ge=50, le=3000)


class PolicyPreviewResponse(BaseModel):
    total_orders_evaluated: int
    action_distribution: Dict[ActionType, int]
    action_percentages: Dict[ActionType, float]
    projected_avoided_rto_rupees: float
    projected_foregone_contribution_rupees: float
    projected_messaging_discount_cost_rupees: float
    projected_net_monthly_impact_rupees: float


# -------------------------------------------------------------------------
# WhatsApp Simulator Schemas
# -------------------------------------------------------------------------

class MessageDirection(str, Enum):
    OUTBOUND = "OUTBOUND"
    INBOUND = "INBOUND"


class WhatsAppMessageOut(BaseModel):
    id: Optional[int] = None
    order_id: str
    direction: MessageDirection
    content: str
    message_type: str = Field(default="CHAT")
    quick_replies: Optional[List[str]] = None
    payment_link: Optional[str] = None
    sent_at: datetime = Field(default_factory=datetime.utcnow)


class WhatsAppCustomerReply(BaseModel):
    order_id: str
    reply_text: str
    client_timestamp: Optional[datetime] = None


class AdvanceClockRequest(BaseModel):
    order_id: str
    advance_hours: int = Field(default=1, ge=1, le=72)


class SimulatePaymentRequest(BaseModel):
    order_id: str
    payment_status: str = Field(..., description="SUCCESS or FAILED")
    transaction_id: Optional[str] = None
    discount_availed: float = Field(default=25.0)


# -------------------------------------------------------------------------
# Dashboard & Analytics Schemas
# -------------------------------------------------------------------------

class FinancialBridge(BaseModel):
    """Exact reconciliation bridge between baseline and post-intervention performance."""
    baseline_cod_revenue: float
    baseline_cod_rto_loss: float
    baseline_net_contribution: float
    avoided_rto_savings: float
    foregone_margin_from_cancellations: float
    messaging_costs_incurred: float
    prepaid_discounts_granted: float
    net_financial_improvement: float
    net_roi_percentage: float


class DashboardOverview(BaseModel):
    selected_date_label: str
    total_orders: int
    orders_by_action: Dict[ActionType, int]
    rto_rate_current: float
    rto_rate_projected_post_intervention: float
    financial_bridge: FinancialBridge
    orders_pending_review: int
    active_policy_version: str
    model_version: str
