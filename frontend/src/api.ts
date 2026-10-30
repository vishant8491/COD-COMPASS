import {
  ActionType,
  AnalysisReport,
  DashboardOverview,
  Order,
  DecisionDetail,
  OperationalStatus,
  PolicyConfig,
  PolicyPreviewResponse,
  WhatsAppMessage,
  SimulationState,
} from './types';

const BASE_URL = '/api';

export async function fetchHealth(): Promise<{ status: string; is_fallback: boolean; active_policy: string }> {
  const res = await fetch(`${BASE_URL}/health`);
  if (!res.ok) throw new Error('Failed to fetch health');
  return res.json();
}

export async function fetchOverview(preset: string = 'yesterday'): Promise<DashboardOverview> {
  const res = await fetch(`${BASE_URL}/dashboard/overview?date_preset=${encodeURIComponent(preset)}`);
  if (!res.ok) throw new Error('Failed to fetch dashboard overview');
  return res.json();
}

export async function fetchOrders(params: {
  search?: string;
  action?: string;
  status?: string;
  risk_band?: string;
  limit?: number;
  offset?: number;
}): Promise<{ total: number; limit: number; offset: number; orders: Order[] }> {
  const query = new URLSearchParams();
  if (params.search) query.append('search', params.search);
  if (params.action) query.append('action', params.action);
  if (params.status) query.append('status', params.status);
  if (params.risk_band) query.append('risk_band', params.risk_band);
  if (params.limit) query.append('limit', params.limit.toString());
  if (params.offset) query.append('offset', params.offset.toString());

  const res = await fetch(`${BASE_URL}/orders?${query.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch orders');
  return res.json();
}

export async function fetchOrderDetail(orderId: string): Promise<{
  order: Order;
  latest_decision?: DecisionDetail;
  simulation?: SimulationState;
  conversations: WhatsAppMessage[];
  audit_trail: any[];
}> {
  const res = await fetch(`${BASE_URL}/orders/${orderId}`);
  if (!res.ok) throw new Error(`Failed to fetch order ${orderId}`);
  return res.json();
}

export async function evaluateOrder(orderId: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/orders/${orderId}/evaluate`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed to evaluate order ${orderId}`);
  return res.json();
}

export async function transitionOrderStatus(
  orderId: string,
  newStatus: OperationalStatus,
  reason: string
): Promise<any> {
  const res = await fetch(`${BASE_URL}/orders/${orderId}/transition`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_status: newStatus, reason }),
  });
  if (!res.ok) throw new Error(`Failed to transition order status`);
  return res.json();
}

export async function fetchActivePolicy(): Promise<PolicyConfig> {
  const res = await fetch(`${BASE_URL}/policy/active`);
  if (!res.ok) throw new Error('Failed to fetch active policy');
  return res.json();
}

export async function fetchPolicyVersions(): Promise<PolicyConfig[]> {
  const res = await fetch(`${BASE_URL}/policy/versions`);
  if (!res.ok) throw new Error('Failed to fetch policy versions');
  return res.json();
}

export async function savePolicy(policy: PolicyConfig): Promise<any> {
  const res = await fetch(`${BASE_URL}/policy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(policy),
  });
  if (!res.ok) throw new Error('Failed to save policy');
  return res.json();
}

export async function previewPolicyImpact(
  policy: PolicyConfig,
  sampleSize: number = 200
): Promise<PolicyPreviewResponse> {
  const res = await fetch(`${BASE_URL}/policy/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ policy, sample_size: sampleSize }),
  });
  if (!res.ok) throw new Error('Failed to preview policy impact');
  return res.json();
}

export async function sendCustomerReply(orderId: string, replyText: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/simulator/reply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ order_id: orderId, reply_text: replyText }),
  });
  if (!res.ok) throw new Error('Failed to process customer reply');
  return res.json();
}

export async function advanceSimulationClock(orderId: string, advanceHours: number): Promise<any> {
  const res = await fetch(`${BASE_URL}/simulator/advance_clock`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ order_id: orderId, advance_hours: advanceHours }),
  });
  if (!res.ok) throw new Error('Failed to advance simulation clock');
  return res.json();
}

export async function simulatePayment(
  orderId: string,
  paymentStatus: 'SUCCESS' | 'FAILED',
  discountAvailed: number = 25.0
): Promise<any> {
  const res = await fetch(`${BASE_URL}/simulator/simulate_payment`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      order_id: orderId,
      payment_status: paymentStatus,
      discount_availed: discountAvailed,
    }),
  });
  if (!res.ok) throw new Error('Failed to simulate payment');
  return res.json();
}

export async function fetchAnalysisReport(): Promise<AnalysisReport> {
  const res = await fetch(`${BASE_URL}/analysis/report`);
  if (!res.ok) throw new Error('Failed to fetch analysis report');
  return res.json();
}

