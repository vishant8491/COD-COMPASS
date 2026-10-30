export type ActionType = 'SHIP_AS_IS' | 'CONFIRM' | 'NUDGE_PREPAID' | 'HOLD';

export type OperationalStatus =
  | 'NEW'
  | 'AWAITING_CONFIRMATION'
  | 'AWAITING_PAYMENT'
  | 'CONFIRMED'
  | 'PREPAID_CONVERTED'
  | 'HELD_FOR_REVIEW'
  | 'CANCELLED'
  | 'SHIPPED'
  | 'DELIVERED'
  | 'RTO'
  | 'IN_TRANSIT';

export type RiskBand = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface ActionEconomics {
  action: ActionType;
  expected_gross_revenue: number;
  expected_cogs: number;
  expected_forward_shipping: number;
  expected_return_shipping: number;
  expected_packaging: number;
  expected_damage_loss: number;
  expected_messaging_cost: number;
  expected_discount: number;
  expected_payment_fee: number;
  expected_net_contribution: number;
  net_advantage_vs_baseline: number;
  acquisition_spend_at_risk: number;
}

export interface Order {
  order_id: string;
  order_datetime: string;
  customer_name: string;
  phone: string;
  address: string;
  city: string;
  state: string;
  pincode: string;
  order_value: number;
  items: string;
  num_items: number;
  customer_prior_orders: number;
  customer_prior_rto: number;
  utm_source?: string;
  courier?: string;
  payment_method: string;
  final_status?: string;
  operational_status: OperationalStatus;
  latest_recommendation?: ActionType;
  latest_risk_score?: number;
  latest_risk_band?: RiskBand;
  latest_explanation?: string;
  plain_english_ops_note?: string;
  uncertainty_flag?: boolean;
}

export interface DecisionDetail {
  id: number;
  order_id: string;
  recommended_action: ActionType;
  risk_score: number;
  risk_band: RiskBand;
  explanation: string;
  plain_english_ops_note: string;
  uncertainty_flag: boolean;
  action_economics: Record<ActionType, ActionEconomics>;
  policy_version: string;
  model_version: string;
  is_fallback: boolean;
  review_flags: string[];
  evaluated_at: string;
}

export interface WhatsAppMessage {
  id: number;
  direction: 'OUTBOUND' | 'INBOUND';
  content: string;
  message_type: string;
  quick_replies: string[];
  payment_link?: string;
  sent_at: string;
}

export interface SimulationState {
  order_id: string;
  step: string;
  payment_status?: string;
  payment_link?: string;
  discount_applied: number;
  simulated_clock_time: string;
  updated_at: string;
}

export interface FinancialBridge {
  baseline_cod_revenue: number;
  baseline_cod_rto_loss: number;
  baseline_net_contribution: number;
  avoided_rto_savings: number;
  foregone_margin_from_cancellations: number;
  messaging_costs_incurred: number;
  prepaid_discounts_granted: number;
  net_financial_improvement: number;
  net_roi_percentage: number;
}

export interface DashboardOverview {
  selected_date_label: string;
  total_orders: number;
  orders_by_action: Record<ActionType, number>;
  rto_rate_current: number;
  rto_rate_projected_post_intervention: number;
  financial_bridge: FinancialBridge;
  orders_pending_review: number;
  active_policy_version: string;
  model_version: string;
}

export interface PolicyConfig {
  id?: number;
  policy_id: string;
  version: number;
  name: string;
  description: string;
  low_risk_threshold: number;
  confirm_threshold: number;
  nudge_threshold: number;
  hold_threshold: number;
  prepaid_discount_amount: number;
  auto_cancel_enabled: boolean;
  require_confirm_above_value: number;
  min_pincode_sample: number;
  is_active: boolean;
  created_at?: string;
}

export interface PolicyPreviewResponse {
  total_orders_evaluated: number;
  action_distribution: Record<ActionType, number>;
  action_percentages: Record<ActionType, number>;
  projected_avoided_rto_rupees: number;
  projected_foregone_contribution_rupees: number;
  projected_messaging_discount_cost_rupees: number;
  projected_net_monthly_impact_rupees: number;
}

export interface AnalysisReport {
  overall_metrics: {
    total_orders: number;
    total_rtos: number;
    baseline_rto_rate: number;
  };
  prior_rto_segments: Array<{
    segment: string;
    total: number;
    rtos: number;
    rto_rate: number;
  }>;
  value_segments: Array<{
    band: string;
    total: number;
    rtos: number;
    rto_rate: number;
  }>;
  pincode_sample_sizes: {
    total_unique_pincodes: number;
    single_order_pincodes: number;
    under_5_orders_pincodes: number;
    under_10_orders_pincodes: number;
    ten_or_more_pincodes: number;
  };
  model_metrics: Record<string, any>;
  backtest_scenarios: Record<
    string,
    {
      name: string;
      avoided_rto_rate: number;
      monthly_avoided_rtos: number;
      avoided_shipping_savings_rupees: number;
      messaging_cost_rupees: number;
      net_monthly_gain_rupees: number;
    }
  >;
}

