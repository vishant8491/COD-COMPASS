import React, { useState, useEffect } from 'react';
import {
  MessageSquare,
  Send,
  Clock,
  CreditCard,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RotateCcw,
  Sparkles,
  Phone,
  ShieldCheck,
  ChevronRight,
  ArrowLeft,
  Search,
  ExternalLink,
} from 'lucide-react';
import { WhatsAppMessage, SimulationState, Order } from '../types';
import {
  fetchOrders,
  fetchOrderDetail,
  sendCustomerReply,
  advanceSimulationClock,
  simulatePayment,
} from '../api';
import { useToast } from '../context/ToastContext';
import { Skeleton } from '../components/Skeleton';

interface SimulatorViewProps {
  initialOrderId?: string;
}

export const SimulatorView: React.FC<SimulatorViewProps> = ({ initialOrderId }) => {
  const { showToast } = useToast();
  const [orders, setOrders] = useState<Order[]>([]);
  const [selectedOrderId, setSelectedOrderId] = useState<string>(initialOrderId || '');
  const [messages, setMessages] = useState<WhatsAppMessage[]>([]);
  const [simulation, setSimulation] = useState<SimulationState | null>(null);
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [searchFilter, setSearchFilter] = useState('');
  const [mobileChatOpen, setMobileChatOpen] = useState(false);

  // Load orders for conversation list
  useEffect(() => {
    fetchOrders({ limit: 40 }).then((res) => {
      setOrders(res.orders);
      if (!selectedOrderId && res.orders.length > 0) {
        // Default to first order with an active WhatsApp recommendation or in progress
        const preferred =
          res.orders.find(
            (o) =>
              o.latest_recommendation === 'CONFIRM' ||
              o.latest_recommendation === 'NUDGE_PREPAID' ||
              o.operational_status === 'AWAITING_CONFIRMATION'
          ) || res.orders[0];
        setSelectedOrderId(preferred.order_id);
      }
    });
  }, []);

  const loadConversation = async (orderId: string) => {
    if (!orderId) return;
    setLoading(true);
    try {
      const detail = await fetchOrderDetail(orderId);
      setMessages(detail.conversations);
      setSimulation(detail.simulation || null);
      setSelectedOrder(detail.order);
    } catch (err) {
      showToast('Failed to load conversation history', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialOrderId) {
      setSelectedOrderId(initialOrderId);
      setMobileChatOpen(true);
    }
  }, [initialOrderId]);

  useEffect(() => {
    if (selectedOrderId) {
      loadConversation(selectedOrderId);
    }
  }, [selectedOrderId]);

  const handleSelectOrder = (orderId: string) => {
    setSelectedOrderId(orderId);
    setMobileChatOpen(true);
  };

  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || inputMessage;
    if (!text.trim() || !selectedOrderId || actionLoading) return;
    setActionLoading(true);
    try {
      const res = await sendCustomerReply(selectedOrderId, text.trim());
      setInputMessage('');
      await loadConversation(selectedOrderId);
      showToast(`Reply processed: Intent '${res.intent}'`, 'info');
    } catch (err) {
      showToast('Failed to send simulated message', 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleAdvanceClock = async (hours: number) => {
    if (!selectedOrderId || actionLoading) return;
    setActionLoading(true);
    try {
      const res = await advanceSimulationClock(selectedOrderId, hours);
      await loadConversation(selectedOrderId);
      if (res.timeout_triggered) {
        showToast('24-Hour timeout triggered: Order moved to HELD_FOR_REVIEW', 'warning');
      } else {
        showToast(`Clock advanced +${hours}h (${res.elapsed_hours}h elapsed)`, 'success');
      }
    } catch (err) {
      showToast('Clock advance failed', 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleSimulatePayment = async (status: 'SUCCESS' | 'FAILED') => {
    if (!selectedOrderId || actionLoading) return;
    setActionLoading(true);
    try {
      const res = await simulatePayment(selectedOrderId, status, 25.0);
      await loadConversation(selectedOrderId);
      if (status === 'SUCCESS') {
        showToast(`Payment SUCCESS! Order marked PREPAID (Txn: ${res.transaction_id})`, 'success');
      } else {
        showToast('Payment FAILED webhook simulated (Fallback to COD)', 'warning');
      }
    } catch (err) {
      showToast('Payment webhook simulation failed', 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const filteredOrders = orders.filter(
    (o) =>
      o.order_id.toLowerCase().includes(searchFilter.toLowerCase()) ||
      o.customer_name.toLowerCase().includes(searchFilter.toLowerCase())
  );

  return (
    <div className="space-y-6 pb-12 animate-in fade-in duration-150">
      {/* Simulation Banner Notice */}
      <div className="bg-amber-500/10 border border-amber-500/30 text-amber-900 dark:text-amber-200 px-4 py-2.5 rounded-xl text-xs flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Sparkles className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
          <span>
            <strong>Interactive Simulation Sandbox:</strong> Test automated customer engagement, Hinglish
            intent classification, 24h timeouts, and mock UPI/Card payments. No real SMS or charges are sent.
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Conversation Queue (3 cols on desktop) */}
        <div
          className={`lg:col-span-3 bg-white dark:bg-[#0F172A] rounded-2xl border border-slate-200 dark:border-slate-800 shadow-2xs overflow-hidden flex flex-col h-[650px] ${
            mobileChatOpen ? 'hidden lg:flex' : 'flex'
          }`}
        >
          <div className="p-3.5 border-b border-slate-100 dark:border-slate-800 space-y-2">
            <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
              Conversations ({filteredOrders.length})
            </h3>
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                placeholder="Search orders..."
                className="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-teal-500"
              />
            </div>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-slate-100 dark:divide-slate-800/80">
            {filteredOrders.map((o) => {
              const isSelected = o.order_id === selectedOrderId;
              return (
                <button
                  key={o.order_id}
                  onClick={() => handleSelectOrder(o.order_id)}
                  className={`w-full p-3 text-left transition-colors flex items-start justify-between ${
                    isSelected
                      ? 'bg-teal-50/80 dark:bg-teal-950/40 border-l-4 border-teal-600'
                      : 'hover:bg-slate-50 dark:hover:bg-slate-800/40'
                  }`}
                >
                  <div className="min-w-0 pr-2">
                    <div className="flex items-center space-x-1.5">
                      <span className="font-mono font-bold text-xs text-slate-900 dark:text-slate-100">
                        #{o.order_id}
                      </span>
                      <span className="text-[10px] text-slate-400 font-sans">
                        ₹{o.order_value.toFixed(0)}
                      </span>
                    </div>
                    <div className="text-xs font-medium text-slate-700 dark:text-slate-300 truncate mt-0.5">
                      {o.customer_name}
                    </div>
                    <div className="text-[10px] text-slate-400 truncate">
                      {o.latest_recommendation || o.operational_status}
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-400 shrink-0 mt-1" />
                </button>
              );
            })}
          </div>
        </div>

        {/* Center Column: WhatsApp Interactive Phone Mockup (5 cols on desktop) */}
        <div
          className={`lg:col-span-5 bg-white dark:bg-[#0F172A] rounded-2xl border border-slate-300 dark:border-slate-700 shadow-md overflow-hidden flex flex-col h-[650px] ${
            !mobileChatOpen ? 'hidden lg:flex' : 'flex'
          }`}
        >
          {/* WhatsApp Header */}
          <div className="bg-[#075E54] dark:bg-[#054c44] text-white p-3 flex items-center justify-between shadow-xs">
            <div className="flex items-center space-x-2.5">
              <button
                onClick={() => setMobileChatOpen(false)}
                className="lg:hidden p-1 text-white/80 hover:text-white"
                aria-label="Back to conversation list"
              >
                <ArrowLeft className="w-4 h-4" />
              </button>
              <div className="w-9 h-9 rounded-full bg-emerald-700 border-2 border-emerald-400/50 flex items-center justify-center font-bold text-sm">
                🌿
              </div>
              <div>
                <div className="flex items-center space-x-1.5">
                  <span className="font-bold text-xs sm:text-sm tracking-tight">Kesh Naturals</span>
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-300" />
                </div>
                <div className="text-[10px] text-emerald-200 font-sans">
                  Verified Store • {selectedOrder?.phone ? `${selectedOrder.phone.slice(0, 5)}*****` : '+91 98765*****'}
                </div>
              </div>
            </div>
            <div className="text-right">
              <span className="text-[10px] font-mono bg-emerald-800/90 dark:bg-emerald-900 px-2 py-0.5 rounded text-emerald-100">
                #{selectedOrderId}
              </span>
            </div>
          </div>

          {/* WhatsApp Chat Canvas */}
          <div
            className="flex-1 bg-[#EFEAE2] dark:bg-[#0B141A] p-4 overflow-y-auto space-y-3"
            aria-live="polite"
          >
            {loading ? (
              <div className="p-4 space-y-3">
                <Skeleton className="h-12 w-3/4 rounded-lg" />
                <Skeleton className="h-8 w-1/2 ml-auto rounded-lg" />
                <Skeleton className="h-16 w-3/4 rounded-lg" />
              </div>
            ) : messages.length === 0 ? (
              <div className="text-center py-12 text-slate-500 text-xs">
                No messages yet. Use the controls on the right to start communication.
              </div>
            ) : (
              messages.map((m) => {
                const isOutbound = m.direction === 'OUTBOUND';
                const isSystem = m.message_type === 'TIMEOUT_ALERT' || m.message_type === 'SYSTEM';
                const isPayment = m.message_type === 'PAYMENT_EVENT';

                if (isSystem) {
                  return (
                    <div key={m.id} className="flex justify-center my-2">
                      <div className="bg-amber-100 dark:bg-amber-950/80 text-amber-900 dark:text-amber-200 text-[11px] px-3 py-1.5 rounded-lg border border-amber-300 dark:border-amber-800 max-w-[90%] text-center shadow-2xs">
                        {m.content}
                      </div>
                    </div>
                  );
                }

                return (
                  <div
                    key={m.id}
                    className={`flex flex-col ${isOutbound ? 'items-start' : 'items-end'}`}
                  >
                    <div
                      className={`max-w-[85%] rounded-lg px-3 py-2 shadow-2xs text-xs leading-relaxed ${
                        isOutbound
                          ? isPayment
                            ? 'bg-teal-50 dark:bg-teal-950 text-teal-950 dark:text-teal-100 border border-teal-300 dark:border-teal-800 rounded-tl-none'
                            : 'bg-white dark:bg-[#202C33] text-slate-900 dark:text-slate-100 rounded-tl-none border border-slate-200 dark:border-slate-700/60'
                          : 'bg-[#DCF8C6] dark:bg-[#005C4B] text-slate-900 dark:text-slate-100 rounded-tr-none'
                      }`}
                    >
                      <p className="whitespace-pre-wrap">{m.content}</p>

                      {/* Payment Link Card if present */}
                      {m.payment_link && (
                        <div className="mt-2 p-2.5 rounded-lg bg-teal-50 dark:bg-teal-900/40 border border-teal-200 dark:border-teal-700 space-y-1">
                          <div className="font-bold text-teal-900 dark:text-teal-200 text-[11px] flex items-center space-x-1">
                            <CreditCard className="w-3 h-3 text-teal-600 dark:text-teal-400" />
                            <span>Instant UPI/Card Payment Link</span>
                          </div>
                          <p className="text-[10px] text-teal-700 dark:text-teal-300">
                            Apply ₹25 instant prepayment discount
                          </p>
                          <button
                            onClick={() => handleSimulatePayment('SUCCESS')}
                            className="mt-1 w-full text-center py-1 px-2 bg-teal-600 hover:bg-teal-700 text-white font-bold rounded text-[11px] transition-colors"
                          >
                            Pay Online (Simulate Webhook)
                          </button>
                        </div>
                      )}

                      <div className="mt-1 flex items-center justify-end space-x-1 text-[9px] text-slate-400 font-mono">
                        <span>
                          {new Date(m.sent_at).toLocaleTimeString('en-IN', {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </span>
                        {isOutbound && <span className="text-sky-500">✓✓</span>}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Suggested Quick Replies */}
          <div className="bg-slate-100 dark:bg-slate-800/80 p-2 border-t border-slate-200 dark:border-slate-700 flex flex-wrap gap-1.5">
            <span className="text-[10px] uppercase font-bold text-slate-400 dark:text-slate-500 px-1 py-0.5">
              Quick Replies:
            </span>
            <button
              onClick={() => handleSendMessage('Haan bhej do, confirm hai!')}
              disabled={actionLoading}
              className="text-[11px] bg-white dark:bg-slate-900 hover:bg-emerald-50 dark:hover:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 font-semibold px-2 py-0.5 rounded border border-emerald-200 dark:border-emerald-800 shadow-2xs transition-colors"
            >
              "Haan bhej do" (YES)
            </button>
            <button
              onClick={() => handleSendMessage('Cancel kardo, nahi chahiye')}
              disabled={actionLoading}
              className="text-[11px] bg-white dark:bg-slate-900 hover:bg-rose-50 dark:hover:bg-rose-950/60 text-rose-800 dark:text-rose-300 font-semibold px-2 py-0.5 rounded border border-rose-200 dark:border-rose-800 shadow-2xs transition-colors"
            >
              "Cancel kardo" (NO)
            </button>
            <button
              onClick={() => handleSendMessage('Discount link bhejo payment karta hu')}
              disabled={actionLoading}
              className="text-[11px] bg-white dark:bg-slate-900 hover:bg-teal-50 dark:hover:bg-teal-950/60 text-teal-800 dark:text-teal-300 font-semibold px-2 py-0.5 rounded border border-teal-200 dark:border-teal-800 shadow-2xs transition-colors"
            >
              "Discount link bhejo" (Prepaid)
            </button>
            <button
              onClick={() => handleSendMessage('maine payment kar diya hai')}
              disabled={actionLoading}
              title="Test: typing 'paid' in text does NOT mark order complete without gateway webhook"
              className="text-[11px] bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 font-semibold px-2 py-0.5 rounded border border-slate-200 dark:border-slate-700 shadow-2xs transition-colors"
            >
              "Maine pay kar diya" (Test Text)
            </button>
          </div>

          {/* Text Composer */}
          <div className="bg-[#F0F2F5] dark:bg-[#202C33] p-2.5 border-t border-slate-200 dark:border-slate-700 flex items-center space-x-2">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
              placeholder="Type simulated customer reply in English or Hinglish..."
              aria-label="Simulated customer reply text"
              className="flex-1 bg-white dark:bg-[#2A3942] border border-slate-300 dark:border-slate-600 rounded-full px-3.5 py-1.5 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
            <button
              onClick={() => handleSendMessage()}
              disabled={actionLoading || !inputMessage.trim()}
              aria-label="Send simulated reply"
              className="w-8 h-8 rounded-full bg-[#128C7E] hover:bg-[#075E54] text-white flex items-center justify-center shadow-xs transition-colors disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5 ml-0.5" />
            </button>
          </div>
        </div>

        {/* Right Column: Controls, Sandbox & State Inspector (4 cols on desktop) */}
        <div className="lg:col-span-4 space-y-4">
          {/* Order Snapshot */}
          <div className="bg-white dark:bg-[#0F172A] rounded-xl p-4 border border-slate-200 dark:border-slate-800 shadow-2xs space-y-2">
            <h3 className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              Order #{selectedOrderId} Snapshot
            </h3>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                <span className="text-slate-400 text-[10px] uppercase font-semibold block">Status</span>
                <span className="font-bold text-slate-900 dark:text-slate-100 text-xs mt-0.5 block">
                  {selectedOrder?.operational_status || 'NEW'}
                </span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                <span className="text-slate-400 text-[10px] uppercase font-semibold block">Payment Mode</span>
                <span className="font-mono font-bold text-teal-700 dark:text-teal-400 text-xs mt-0.5 block">
                  {selectedOrder?.payment_method || 'COD'}
                </span>
              </div>
              <div className="col-span-2 p-2.5 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300">
                <div className="font-semibold text-slate-900 dark:text-slate-100">
                  {selectedOrder?.customer_name}
                </div>
                <div className="text-[11px] text-slate-400">
                  {selectedOrder?.city}, {selectedOrder?.pincode} • Basket: ₹{selectedOrder?.order_value.toFixed(0)}
                </div>
              </div>
            </div>
          </div>

          {/* Clock Control Card */}
          <div className="bg-white dark:bg-[#0F172A] rounded-xl p-4 border border-slate-200 dark:border-slate-800 shadow-2xs space-y-2.5">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider flex items-center space-x-1.5">
                <Clock className="w-3.5 h-3.5 text-slate-400" />
                <span>Simulated Order Clock</span>
              </h3>
              <span className="text-[10px] font-mono text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded border border-slate-200 dark:border-slate-700">
                Timeout: 24h
              </span>
            </div>

            <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
              Advancing time affects this selected order's lifecycle. If the customer does not respond within
              24 hours, the order automatically moves to <strong>HELD_FOR_REVIEW</strong>.
            </p>

            <div className="grid grid-cols-2 gap-2 pt-1">
              <button
                onClick={() => handleAdvanceClock(1)}
                disabled={actionLoading}
                className="py-2 px-3 rounded-lg text-xs font-bold bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700 transition-colors disabled:opacity-50"
              >
                +1 Hour
              </button>
              <button
                onClick={() => handleAdvanceClock(25)}
                disabled={actionLoading}
                className="py-2 px-3 rounded-lg text-xs font-bold bg-amber-50 dark:bg-amber-950/60 hover:bg-amber-100 dark:hover:bg-amber-900/80 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800 transition-colors disabled:opacity-50"
              >
                +25 Hours (Timeout)
              </button>
            </div>
          </div>

          {/* Payment Gateway Sandbox */}
          <div className="bg-white dark:bg-[#0F172A] rounded-xl p-4 border border-slate-200 dark:border-slate-800 shadow-2xs space-y-2.5">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider flex items-center space-x-1.5">
                <CreditCard className="w-3.5 h-3.5 text-slate-400" />
                <span>Payment Webhook Sandbox</span>
              </h3>
              <span className="text-[10px] font-bold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950 px-2 py-0.5 rounded border border-emerald-200 dark:border-emerald-800">
                Idempotent
              </span>
            </div>

            <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
              Simulate webhook callbacks from payment gateways (Razorpay/Cashfree). Converts COD order to
              PREPAID with ₹25 discount and triggers priority dispatch notification.
            </p>

            <div className="space-y-2 pt-1">
              <button
                onClick={() => handleSimulatePayment('SUCCESS')}
                disabled={actionLoading}
                className="w-full py-2 px-3 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs transition-colors flex items-center justify-center space-x-1.5 disabled:opacity-50"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Simulate Payment SUCCESS (Convert)</span>
              </button>
              <button
                onClick={() => handleSimulatePayment('FAILED')}
                disabled={actionLoading}
                className="w-full py-2 px-3 rounded-lg text-xs font-bold bg-rose-50 dark:bg-rose-950/60 hover:bg-rose-100 dark:hover:bg-rose-900/80 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800 transition-colors flex items-center justify-center space-x-1.5 disabled:opacity-50"
              >
                <XCircle className="w-3.5 h-3.5" />
                <span>Simulate Payment FAILED (Fallback COD)</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
