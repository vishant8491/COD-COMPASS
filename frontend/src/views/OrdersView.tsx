import React, { useState, useEffect, useMemo } from 'react';
import {
  Search,
  Filter,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ArrowRight,
  X,
  Shield,
  HelpCircle,
  Truck,
  RotateCcw,
  Sparkles,
  ArrowUpDown,
  ChevronRight,
  AlertCircle,
  MessageSquare,
} from 'lucide-react';
import { Order, ActionType, DecisionDetail, OperationalStatus, RiskBand } from '../types';
import { fetchOrders, fetchOrderDetail, evaluateOrder, transitionOrderStatus } from '../api';
import { Skeleton } from '../components/Skeleton';
import { EmptyState } from '../components/EmptyState';
import { Modal } from '../components/Modal';
import { useToast } from '../context/ToastContext';

interface OrdersViewProps {
  initialActionFilter?: ActionType;
  initialSearch?: string;
  onNavigateToSimulatorWithOrder?: (orderId: string) => void;
  onFilterChange?: (filters: { action?: string; risk?: string; status?: string; search?: string }) => void;
}

export const OrdersView: React.FC<OrdersViewProps> = ({
  initialActionFilter,
  initialSearch = '',
  onNavigateToSimulatorWithOrder,
  onFilterChange,
}) => {
  const { showToast } = useToast();
  const [orders, setOrders] = useState<Order[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  // Filters & Search
  const [search, setSearch] = useState(initialSearch);
  const [actionFilter, setActionFilter] = useState<string>(initialActionFilter || '');
  const [riskFilter, setRiskFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [sortBy, setSortBy] = useState<'date_desc' | 'date_asc' | 'value_desc' | 'risk_desc'>('date_desc');

  // Drawer state
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);
  const [orderDetail, setOrderDetail] = useState<{
    order: Order;
    latest_decision?: DecisionDetail;
    conversations: any[];
    audit_trail: any[];
  } | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);

  // Cancel Confirmation Modal State
  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState('Customer confirmed order cancellation via support.');

  const loadOrders = async () => {
    setLoading(true);
    try {
      const res = await fetchOrders({
        search: search.trim() || undefined,
        action: actionFilter || undefined,
        risk_band: riskFilter || undefined,
        status: statusFilter || undefined,
        limit: 100,
      });
      setOrders(res.orders);
      setTotal(res.total);
      if (onFilterChange) {
        onFilterChange({ action: actionFilter, risk: riskFilter, status: statusFilter, search });
      }
    } catch (err) {
      showToast('Failed to load orders queue', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOrders();
  }, [actionFilter, riskFilter, statusFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadOrders();
  };

  const handleClearFilters = () => {
    setSearch('');
    setActionFilter('');
    setRiskFilter('');
    setStatusFilter('');
    setSortBy('date_desc');
  };

  const openDrawer = async (orderId: string) => {
    setSelectedOrderId(orderId);
    setLoadingDetail(true);
    try {
      const detail = await fetchOrderDetail(orderId);
      setOrderDetail(detail);
    } catch (err) {
      showToast(`Failed to load details for order #${orderId}`, 'error');
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleReevaluate = async () => {
    if (!selectedOrderId) return;
    setLoadingDetail(true);
    try {
      await evaluateOrder(selectedOrderId);
      const detail = await fetchOrderDetail(selectedOrderId);
      setOrderDetail(detail);
      loadOrders();
      showToast(`Order #${selectedOrderId} re-evaluated successfully`, 'success');
    } catch (err) {
      showToast('Re-evaluation failed', 'error');
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleStatusChange = async (newStatus: OperationalStatus, reason: string) => {
    if (!selectedOrderId) return;
    setIsTransitioning(true);
    try {
      await transitionOrderStatus(selectedOrderId, newStatus, reason);
      const detail = await fetchOrderDetail(selectedOrderId);
      setOrderDetail(detail);
      loadOrders();
      showToast(`Order #${selectedOrderId} transitioned to ${newStatus}`, 'success');
    } catch (err) {
      showToast('Status update failed', 'error');
    } finally {
      setIsTransitioning(false);
      setCancelModalOpen(false);
    }
  };

  // Client-side sorting on loaded page
  const sortedOrders = useMemo(() => {
    const list = [...orders];
    if (sortBy === 'date_desc') {
      list.sort((a, b) => new Date(b.order_datetime).getTime() - new Date(a.order_datetime).getTime());
    } else if (sortBy === 'date_asc') {
      list.sort((a, b) => new Date(a.order_datetime).getTime() - new Date(b.order_datetime).getTime());
    } else if (sortBy === 'value_desc') {
      list.sort((a, b) => b.order_value - a.order_value);
    } else if (sortBy === 'risk_desc') {
      list.sort((a, b) => (b.latest_risk_score || 0) - (a.latest_risk_score || 0));
    }
    return list;
  }, [orders, sortBy]);

  const getActionBadge = (action?: ActionType) => {
    switch (action) {
      case 'SHIP_AS_IS':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
            Ship As-Is
          </span>
        );
      case 'CONFIRM':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-sky-100 text-sky-800 dark:bg-sky-950/80 dark:text-sky-300 border border-sky-200 dark:border-sky-800">
            Confirm (WhatsApp)
          </span>
        );
      case 'NUDGE_PREPAID':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-indigo-100 text-indigo-800 dark:bg-indigo-950/80 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
            Nudge to Prepaid
          </span>
        );
      case 'HOLD':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
            Hold for Review
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
            Evaluating...
          </span>
        );
    }
  };

  const getRiskScorePill = (score?: number, band?: string) => {
    if (score === undefined) return null;
    const pct = (score * 100).toFixed(1);
    let colorClass = 'bg-slate-100 text-slate-800 border-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-700';
    if (score < 0.20) colorClass = 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-400 dark:border-emerald-800';
    else if (score < 0.35) colorClass = 'bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/60 dark:text-sky-400 dark:border-sky-800';
    else if (score < 0.55) colorClass = 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/60 dark:text-amber-400 dark:border-amber-800';
    else colorClass = 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/60 dark:text-rose-400 dark:border-rose-800';

    return (
      <div className="flex items-center space-x-1.5">
        <span className={`text-[11px] font-mono font-bold px-2 py-0.5 rounded border ${colorClass}`}>
          {pct}%
        </span>
        <span className="text-[10px] uppercase font-bold text-slate-400 dark:text-slate-500">{band}</span>
      </div>
    );
  };

  const hasActiveFilters = Boolean(search || actionFilter || riskFilter || statusFilter);

  return (
    <div className="space-y-6 pb-12 animate-in fade-in duration-150">
      {/* Search & Filter Bar */}
      <div className="bg-white dark:bg-[#0F172A] rounded-xl p-4 border border-slate-200 dark:border-slate-800 shadow-2xs space-y-3">
        <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
          {/* Search Input */}
          <form onSubmit={handleSearchSubmit} className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by Order ID (KT...), Customer Name, Pincode..."
              aria-label="Search orders"
              className="w-full pl-10 pr-9 py-2 text-xs sm:text-sm bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700/80 rounded-lg text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500 transition-all"
            />
            {search && (
              <button
                type="button"
                onClick={() => {
                  setSearch('');
                  loadOrders();
                }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                aria-label="Clear search"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </form>

          {/* Filter Dropdowns */}
          <div className="flex items-center flex-wrap gap-2">
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              aria-label="Filter by action"
              className="text-xs font-medium bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg px-2.5 py-2 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500"
            >
              <option value="">All Pre-Shipment Actions</option>
              <option value="SHIP_AS_IS">Ship As-Is</option>
              <option value="CONFIRM">Confirm (WhatsApp)</option>
              <option value="NUDGE_PREPAID">Nudge to Prepaid</option>
              <option value="HOLD">Hold for Review</option>
            </select>

            <select
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              aria-label="Filter by risk tier"
              className="text-xs font-medium bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg px-2.5 py-2 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500"
            >
              <option value="">All Risk Tiers</option>
              <option value="LOW">Low (&lt;20%)</option>
              <option value="MEDIUM">Medium (20–35%)</option>
              <option value="HIGH">High (35–65%)</option>
              <option value="CRITICAL">Critical (&gt;65%)</option>
            </select>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              aria-label="Filter by operational status"
              className="text-xs font-medium bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg px-2.5 py-2 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500"
            >
              <option value="">All Operational Statuses</option>
              <option value="NEW">New</option>
              <option value="AWAITING_CONFIRMATION">Awaiting Confirmation</option>
              <option value="AWAITING_PAYMENT">Awaiting Payment</option>
              <option value="CONFIRMED">Confirmed</option>
              <option value="PREPAID_CONVERTED">Prepaid Converted</option>
              <option value="HELD_FOR_REVIEW">Held for Review</option>
              <option value="CANCELLED">Cancelled</option>
            </select>

            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              aria-label="Sort orders"
              className="text-xs font-medium bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg px-2.5 py-2 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500"
            >
              <option value="date_desc">Newest First</option>
              <option value="date_asc">Oldest First</option>
              <option value="value_desc">Highest Value</option>
              <option value="risk_desc">Highest Risk</option>
            </select>
          </div>
        </div>

        {/* Active Filter Chips & Clear */}
        {hasActiveFilters && (
          <div className="flex items-center flex-wrap gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Active Filters:
            </span>

            {search && (
              <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200">
                <span>Search: {search}</span>
                <button onClick={() => setSearch('')} className="hover:text-rose-500">
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}

            {actionFilter && (
              <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md text-xs font-medium bg-teal-50 dark:bg-teal-950/80 text-teal-800 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
                <span>Action: {actionFilter}</span>
                <button onClick={() => setActionFilter('')} className="hover:text-rose-500">
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}

            {riskFilter && (
              <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200">
                <span>Risk: {riskFilter}</span>
                <button onClick={() => setRiskFilter('')} className="hover:text-rose-500">
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}

            {statusFilter && (
              <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200">
                <span>Status: {statusFilter}</span>
                <button onClick={() => setStatusFilter('')} className="hover:text-rose-500">
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}

            <button
              onClick={handleClearFilters}
              className="text-xs text-teal-600 dark:text-teal-400 hover:underline font-semibold ml-auto"
            >
              Clear all filters
            </button>
          </div>
        )}
      </div>

      {/* Orders Table Container */}
      <div className="bg-white dark:bg-[#0F172A] rounded-xl border border-slate-200 dark:border-slate-800 shadow-2xs overflow-hidden">
        <div className="px-5 py-3.5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
          <span className="font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
            Showing {sortedOrders.length} of {total.toLocaleString()} Orders
          </span>
          <span className="text-slate-400 dark:text-slate-500 hidden sm:inline">
            Click any row to open decision audit & economics drawer
          </span>
        </div>

        {loading ? (
          <div className="p-6 space-y-3">
            <Skeleton className="h-10 rounded-lg" />
            <Skeleton className="h-10 rounded-lg" />
            <Skeleton className="h-10 rounded-lg" />
            <Skeleton className="h-10 rounded-lg" />
            <Skeleton className="h-10 rounded-lg" />
          </div>
        ) : sortedOrders.length === 0 ? (
          <EmptyState
            icon={Search}
            title="No orders found matching filters"
            description="Try adjusting your search query, action bucket, or clearing active filters."
            actionText="Clear All Filters"
            onAction={handleClearFilters}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs sm:text-sm">
              <thead>
                <tr className="bg-slate-50/80 dark:bg-slate-900/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  <th className="py-3 px-4">Order ID & Date</th>
                  <th className="py-3 px-4">Location / Customer</th>
                  <th className="py-3 px-4">Value</th>
                  <th className="py-3 px-4">Risk Estimate</th>
                  <th className="py-3 px-4">Pre-Shipment Action</th>
                  <th className="py-3 px-4">Lifecycle Status</th>
                  <th className="py-3 px-4 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
                {sortedOrders.map((o) => (
                  <tr
                    key={o.order_id}
                    onClick={() => openDrawer(o.order_id)}
                    tabIndex={0}
                    role="button"
                    onKeyDown={(e) => e.key === 'Enter' && openDrawer(o.order_id)}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors cursor-pointer group focus-visible:outline-none focus-visible:bg-slate-50 dark:focus-visible:bg-slate-800/50"
                  >
                    <td className="py-3 px-4 font-mono font-bold text-slate-900 dark:text-slate-100">
                      <div>{o.order_id}</div>
                      <div className="text-[11px] text-slate-400 dark:text-slate-500 font-sans font-normal">
                        {new Date(o.order_datetime).toLocaleDateString('en-IN', {
                          day: 'numeric',
                          month: 'short',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </div>
                    </td>

                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-900 dark:text-slate-100">
                        {o.city}, {o.pincode}
                      </div>
                      <div className="text-xs text-slate-500 dark:text-slate-400 flex items-center space-x-1">
                        <span>{o.customer_name}</span>
                        {o.customer_prior_rto > 0 && (
                          <span className="text-rose-600 dark:text-rose-400 font-bold font-mono text-[10px]">
                            ({o.customer_prior_rto} prior RTO)
                          </span>
                        )}
                      </div>
                    </td>

                    <td className="py-3 px-4 font-mono font-bold text-slate-900 dark:text-slate-100">
                      ₹{o.order_value.toFixed(0)}
                    </td>

                    <td className="py-3 px-4">
                      {getRiskScorePill(o.latest_risk_score, o.latest_risk_band)}
                    </td>

                    <td className="py-3 px-4">{getActionBadge(o.latest_recommendation)}</td>

                    <td className="py-3 px-4">
                      <span className="inline-block text-[11px] font-semibold px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700/80">
                        {o.operational_status}
                      </span>
                    </td>

                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          openDrawer(o.order_id);
                        }}
                        aria-label={`View details for order ${o.order_id}`}
                        className="text-teal-700 dark:text-teal-400 group-hover:translate-x-0.5 transition-transform p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Slide-over Detail Drawer */}
      {selectedOrderId && (
        <div
          className="fixed inset-0 z-50 overflow-hidden bg-slate-900/50 dark:bg-black/75 backdrop-blur-xs flex justify-end"
          role="dialog"
          aria-modal="true"
          aria-label={`Order details for ${selectedOrderId}`}
        >
          <div className="w-full max-w-2xl bg-white dark:bg-[#0F172A] border-l border-slate-200 dark:border-slate-800 h-full shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
            {/* Drawer Header */}
            <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between bg-slate-50/70 dark:bg-slate-900/60">
              <div>
                <div className="flex items-center space-x-2">
                  <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
                    Order #{selectedOrderId}
                  </h2>
                  {orderDetail && getActionBadge(orderDetail.order.latest_recommendation)}
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Pre-shipment decision audit and economic comparison
                </p>
              </div>
              <button
                onClick={() => setSelectedOrderId(null)}
                className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500"
                aria-label="Close drawer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Drawer Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {loadingDetail || !orderDetail ? (
                <div className="space-y-4">
                  <Skeleton className="h-32 rounded-xl" />
                  <Skeleton className="h-24 rounded-xl" />
                  <Skeleton className="h-48 rounded-xl" />
                </div>
              ) : (
                <>
                  {/* Status Banner */}
                  <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 flex items-center justify-between">
                    <div>
                      <span className="text-[10px] uppercase font-bold text-slate-400 dark:text-slate-500 block">
                        Current Operational Status
                      </span>
                      <span className="font-bold text-slate-900 dark:text-slate-100 text-sm">
                        {orderDetail.order.operational_status}
                      </span>
                    </div>
                    <div className="text-right">
                      <span className="text-[10px] uppercase font-bold text-slate-400 dark:text-slate-500 block">
                        Payment Method
                      </span>
                      <span className="font-mono font-bold text-teal-700 dark:text-teal-400 text-sm">
                        {orderDetail.order.payment_method}
                      </span>
                    </div>
                  </div>

                  {/* Customer & Address Details */}
                  <div className="bg-white dark:bg-slate-900 rounded-xl p-4 border border-slate-200 dark:border-slate-800 space-y-3">
                    <div className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      Customer & Shipping Details
                    </div>
                    <div className="grid grid-cols-2 gap-4 text-xs sm:text-sm">
                      <div>
                        <span className="text-xs text-slate-400 block">Customer Name</span>
                        <span className="font-semibold text-slate-900 dark:text-slate-100">
                          {orderDetail.order.customer_name}
                        </span>
                      </div>
                      <div>
                        <span className="text-xs text-slate-400 block">Phone Number (Operational View)</span>
                        <span className="font-mono text-slate-900 dark:text-slate-100">
                          {orderDetail.order.phone}
                        </span>
                      </div>
                      <div className="col-span-2">
                        <span className="text-xs text-slate-400 block">Delivery Address</span>
                        <span className="text-slate-800 dark:text-slate-200">{orderDetail.order.address}</span>
                        <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 font-medium">
                          {orderDetail.order.city}, {orderDetail.order.state} — {orderDetail.order.pincode}
                        </div>
                      </div>
                      <div>
                        <span className="text-xs text-slate-400 block">Order Value (COD)</span>
                        <span className="font-mono font-bold text-slate-900 dark:text-slate-100 text-sm">
                          ₹{orderDetail.order.order_value.toFixed(2)}
                        </span>
                      </div>
                      <div>
                        <span className="text-xs text-slate-400 block">Basket SKU</span>
                        <span className="text-slate-700 dark:text-slate-300">{orderDetail.order.items}</span>
                      </div>
                    </div>
                  </div>

                  {/* Decision Explanation & Ops Note */}
                  {orderDetail.latest_decision && (
                    <div className="bg-teal-50/60 dark:bg-teal-950/30 rounded-xl p-4 border border-teal-200 dark:border-teal-800 space-y-2">
                      <div className="flex items-center space-x-2 text-teal-900 dark:text-teal-200 font-bold text-xs sm:text-sm">
                        <Sparkles className="w-4 h-4 text-teal-600 dark:text-teal-400" />
                        <span>Pre-Shipment Decision Engine Analysis</span>
                      </div>
                      <p className="text-xs font-semibold text-slate-900 dark:text-slate-100">
                        {orderDetail.latest_decision.explanation}
                      </p>
                      <p className="text-xs text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-900 p-3 rounded-lg border border-teal-100 dark:border-teal-900/60 font-mono leading-relaxed">
                        {orderDetail.latest_decision.plain_english_ops_note}
                      </p>

                      {orderDetail.latest_decision.review_flags.length > 0 && (
                        <div className="space-y-1.5 pt-2">
                          {orderDetail.latest_decision.review_flags.map((flag, idx) => (
                            <div
                              key={idx}
                              className="text-[11px] font-medium text-amber-800 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/60 px-2.5 py-1 rounded border border-amber-200 dark:border-amber-800/80 flex items-center space-x-1.5"
                            >
                              <AlertTriangle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 shrink-0" />
                              <span>{flag}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* 4-Action Expected Economics Comparison Table */}
                  {orderDetail.latest_decision && orderDetail.latest_decision.action_economics && (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
                          Expected Economics by Action (vs Baseline)
                        </h3>
                        <span className="text-[11px] text-slate-500">Rupee contribution</span>
                      </div>

                      <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
                        <table className="w-full text-xs text-left">
                          <thead className="bg-slate-50 dark:bg-slate-900 text-slate-500 dark:text-slate-400 font-semibold border-b border-slate-200 dark:border-slate-800">
                            <tr>
                              <th className="py-2.5 px-3">Action</th>
                              <th className="py-2.5 px-3 text-right">Expected Contrib</th>
                              <th className="py-2.5 px-3 text-right">Net Advantage</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80 font-mono">
                            {(['SHIP_AS_IS', 'CONFIRM', 'NUDGE_PREPAID', 'HOLD'] as ActionType[]).map((act) => {
                              const econ = orderDetail.latest_decision?.action_economics[act];
                              if (!econ) return null;
                              const isChosen = orderDetail.latest_decision?.recommended_action === act;
                              return (
                                <tr
                                  key={act}
                                  className={isChosen ? 'bg-teal-50/70 dark:bg-teal-950/40 font-bold' : ''}
                                >
                                  <td className="py-2.5 px-3 font-sans flex items-center space-x-1.5 text-slate-900 dark:text-slate-100">
                                    {isChosen && <CheckCircle2 className="w-3.5 h-3.5 text-teal-600 dark:text-teal-400" />}
                                    <span>{act}</span>
                                  </td>
                                  <td className="py-2.5 px-3 text-right text-slate-800 dark:text-slate-200">
                                    ₹{econ.expected_net_contribution.toFixed(2)}
                                  </td>
                                  <td
                                    className={`py-2.5 px-3 text-right font-bold ${
                                      econ.net_advantage_vs_baseline > 0
                                        ? 'text-emerald-600 dark:text-emerald-400'
                                        : econ.net_advantage_vs_baseline < 0
                                        ? 'text-rose-600 dark:text-rose-400'
                                        : 'text-slate-400'
                                    }`}
                                  >
                                    {econ.net_advantage_vs_baseline > 0 ? '+' : ''}₹
                                    {econ.net_advantage_vs_baseline.toFixed(2)}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Audit Trail Timeline */}
                  {orderDetail.audit_trail && orderDetail.audit_trail.length > 0 && (
                    <div className="space-y-3 pt-2">
                      <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
                        Lifecycle Audit Trail
                      </h3>
                      <div className="space-y-2.5 border-l-2 border-slate-200 dark:border-slate-800 pl-4 ml-2">
                        {orderDetail.audit_trail.map((audit) => (
                          <div key={audit.id} className="text-xs space-y-0.5">
                            <div className="font-semibold text-slate-900 dark:text-slate-100 flex items-center space-x-2">
                              <span>{audit.event_type}</span>
                              <span className="text-[10px] font-normal text-slate-400 dark:text-slate-500 font-mono">
                                {new Date(audit.timestamp).toLocaleTimeString('en-IN')}
                              </span>
                            </div>
                            <p className="text-slate-600 dark:text-slate-400">{audit.reason}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Drawer Footer Actions */}
            <div className="p-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 flex items-center justify-between gap-3">
              <button
                onClick={handleReevaluate}
                disabled={loadingDetail}
                className="px-3 py-2 text-xs font-semibold text-slate-700 dark:text-slate-300 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500"
              >
                Re-Evaluate
              </button>

              <div className="flex items-center space-x-2">
                {onNavigateToSimulatorWithOrder && (
                  <button
                    onClick={() => {
                      if (selectedOrderId) {
                        onNavigateToSimulatorWithOrder(selectedOrderId);
                        setSelectedOrderId(null);
                      }
                    }}
                    className="px-3 py-2 text-xs font-semibold text-sky-700 dark:text-sky-300 bg-sky-50 dark:bg-sky-950/60 border border-sky-200 dark:border-sky-800 rounded-lg hover:bg-sky-100 dark:hover:bg-sky-900/80 transition-colors flex items-center space-x-1"
                  >
                    <MessageSquare className="w-3.5 h-3.5" />
                    <span>Open Chat</span>
                  </button>
                )}

                <button
                  onClick={() => handleStatusChange('CONFIRMED', 'Manual dispatch approval from order drawer')}
                  disabled={isTransitioning}
                  className="px-3.5 py-2 text-xs font-bold text-white bg-teal-600 hover:bg-teal-700 rounded-lg shadow-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 disabled:opacity-50"
                >
                  Approve for Dispatch
                </button>

                <button
                  onClick={() => setCancelModalOpen(true)}
                  disabled={isTransitioning}
                  className="px-3.5 py-2 text-xs font-bold text-rose-700 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/60 border border-rose-200 dark:border-rose-800 rounded-lg hover:bg-rose-100 dark:hover:bg-rose-900/80 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 disabled:opacity-50"
                >
                  Cancel Order
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Destructive Cancel Order Confirmation Modal */}
      <Modal
        isOpen={cancelModalOpen}
        onClose={() => setCancelModalOpen(false)}
        title={`Cancel Order #${selectedOrderId}`}
        description="This action will cancel the order, release allocated stock, and record an audit log entry."
        size="sm"
      >
        <div className="space-y-4">
          <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 flex items-start space-x-2 text-xs text-rose-800 dark:text-rose-300">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>
              Customer acquisition cost (₹300) will be forfeited. Only proceed if customer requested
              cancellation or address is verified fraudulent.
            </span>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
              Cancellation Reason (Required for Audit Log)
            </label>
            <textarea
              rows={3}
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              className="w-full text-xs p-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-rose-500"
            />
          </div>

          <div className="flex items-center justify-end space-x-2 pt-2">
            <button
              type="button"
              onClick={() => setCancelModalOpen(false)}
              className="px-3 py-1.5 text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg"
            >
              Keep Order
            </button>
            <button
              type="button"
              disabled={isTransitioning || !cancelReason.trim()}
              onClick={() => handleStatusChange('CANCELLED', cancelReason)}
              className="px-3.5 py-1.5 text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-xs disabled:opacity-50"
            >
              Confirm Cancellation
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
