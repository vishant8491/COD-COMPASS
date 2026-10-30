import React, { useState, useEffect } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import {
  BarChart3,
  TrendingDown,
  AlertOctagon,
  ShieldAlert,
  Info,
  CheckCircle,
  Layers,
  Table,
  FileText,
  MapPin,
  HelpCircle,
  Eye,
  ExternalLink,
  Sparkles,
  Download,
} from 'lucide-react';
import { AnalysisReport } from '../types';
import { fetchAnalysisReport } from '../api';
import { useTheme } from '../context/ThemeContext';
import { Skeleton } from '../components/Skeleton';
import { Modal } from '../components/Modal';

export const AnalysisView: React.FC = () => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<'charts' | 'tables'>('charts');
  const [showMemoModal, setShowMemoModal] = useState(false);

  useEffect(() => {
    fetchAnalysisReport()
      .then((res) => {
        setReport(res);
      })
      .catch((err) => {
        console.error('Failed to load analysis report', err);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  if (loading || !report) {
    return (
      <div className="space-y-6 pb-12 animate-in fade-in duration-150">
        <Skeleton className="h-28 w-full rounded-xl" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-80 w-full rounded-xl" />
          <Skeleton className="h-80 w-full rounded-xl" />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-80 w-full rounded-xl" />
          <Skeleton className="h-80 w-full rounded-xl" />
        </div>
      </div>
    );
  }

  const { overall_metrics: om, prior_rto_segments: prs, value_segments: vs, pincode_sample_sizes: pss, backtest_scenarios: bts } = report;

  // Chart data formatting
  const priorRtoChartData = prs.map((p) => ({
    name: p.segment,
    rto_rate: parseFloat((p.rto_rate * 100).toFixed(1)),
    total: p.total,
    rtos: p.rtos,
  }));

  const valueChartData = vs.map((v) => ({
    name: v.band,
    rto_rate: parseFloat((v.rto_rate * 100).toFixed(1)),
    total: v.total,
    rtos: v.rtos,
  }));

  const pincodeChartData = [
    { name: '1 Order (n=1)', count: pss.single_order_pincodes, fill: '#F43F5E', pct: ((pss.single_order_pincodes / pss.total_unique_pincodes) * 100).toFixed(1) },
    { name: '2–4 Orders', count: pss.under_5_orders_pincodes - pss.single_order_pincodes, fill: '#FB923C', pct: (((pss.under_5_orders_pincodes - pss.single_order_pincodes) / pss.total_unique_pincodes) * 100).toFixed(1) },
    { name: '5–9 Orders', count: pss.under_10_orders_pincodes - pss.under_5_orders_pincodes, fill: '#38BDF8', pct: (((pss.under_10_orders_pincodes - pss.under_5_orders_pincodes) / pss.total_unique_pincodes) * 100).toFixed(1) },
    { name: '10+ Orders', count: pss.ten_or_more_pincodes, fill: '#10B981', pct: ((pss.ten_or_more_pincodes / pss.total_unique_pincodes) * 100).toFixed(1) },
  ];

  // Colors & styles for light and dark themes
  const chartGridColor = isDark ? '#334155' : '#E2E8F0';
  const chartAxisColor = isDark ? '#94A3B8' : '#64748B';
  const chartTooltipStyle = {
    backgroundColor: isDark ? '#0F172A' : '#1E293B',
    borderColor: isDark ? '#334155' : '#475569',
    borderRadius: '8px',
    color: '#F8FAFC',
    fontSize: '12px',
    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.3)',
  };

  return (
    <div className="space-y-8 pb-12">
      {/* Header Context & Controls */}
      <div className="bg-white dark:bg-slate-900 rounded-xl p-6 border border-slate-200 dark:border-slate-800 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2 text-slate-900 dark:text-slate-100 font-bold text-lg">
            <BarChart3 className="w-5 h-5 text-teal-600 dark:text-teal-400" />
            <h2>Empirical Dataset Discoveries & Backtest Proof</h2>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-3xl leading-relaxed">
            Analyzed from 2,018 real orders (April 1 to September 30, 2026). Baseline COD RTO rate:{' '}
            <span className="font-bold text-slate-900 dark:text-slate-100 font-mono">{(om.baseline_rto_rate * 100).toFixed(1)}%</span>{' '}
            ({om.total_rtos} returns on {om.total_orders} resolved orders; 1 unresolved IN_TRANSIT order safely excluded).
          </p>
        </div>

        <div className="flex items-center space-x-3 shrink-0">
          {/* Accessible View Mode Toggle */}
          <div className="inline-flex rounded-lg p-1 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs font-medium">
            <button
              onClick={() => setViewMode('charts')}
              aria-label="View visualizations as charts"
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md transition-colors ${
                viewMode === 'charts'
                  ? 'bg-white dark:bg-slate-700 text-teal-700 dark:text-teal-300 font-bold shadow-xs'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
              }`}
            >
              <BarChart3 className="w-3.5 h-3.5" />
              <span>Charts</span>
            </button>
            <button
              onClick={() => setViewMode('tables')}
              aria-label="View visualizations as accessible data tables"
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md transition-colors ${
                viewMode === 'tables'
                  ? 'bg-white dark:bg-slate-700 text-teal-700 dark:text-teal-300 font-bold shadow-xs'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
              }`}
            >
              <Table className="w-3.5 h-3.5" />
              <span>Accessible Tables</span>
            </button>
          </div>

          {/* Founder Memo Button */}
          <button
            onClick={() => setShowMemoModal(true)}
            className="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800 hover:bg-teal-100 dark:hover:bg-teal-900 transition-colors"
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Founder Memo</span>
          </button>
        </div>
      </div>

      {/* Grid 1: The Two Core Discoveries */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Discovery 1: Prior RTO Escalation */}
        <div className="bg-white dark:bg-slate-900 rounded-xl p-6 border border-slate-200 dark:border-slate-800 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">1. Chronic Prior RTO Escalation</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">RTO probability by customer's prior return count</p>
            </div>
            <span className="text-xs font-bold text-rose-700 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/50 px-2 py-0.5 rounded border border-rose-200 dark:border-rose-900">
              Critical Signal
            </span>
          </div>

          {viewMode === 'charts' ? (
            <div className="h-60" aria-label="Bar chart showing RTO rate climbing with customer prior returns">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={priorRtoChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={chartGridColor} />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: chartAxisColor }} />
                  <YAxis unit="%" tick={{ fontSize: 11, fill: chartAxisColor }} domain={[0, 100]} />
                  <Tooltip
                    formatter={(val: any) => [`${val}% RTO Rate`, 'Rate']}
                    contentStyle={chartTooltipStyle}
                  />
                  <Bar dataKey="rto_rate" radius={[4, 4, 0, 0]}>
                    {priorRtoChartData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={entry.rto_rate > 70 ? '#E11D48' : entry.rto_rate > 30 ? '#F59E0B' : '#0D9488'}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-lg">
              <table className="w-full text-xs text-left" aria-label="Customer Prior RTO breakdown table">
                <thead className="bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-semibold border-b border-slate-200 dark:border-slate-700">
                  <tr>
                    <th scope="col" className="p-2.5">Prior RTO Segment</th>
                    <th scope="col" className="p-2.5 text-right">Orders</th>
                    <th scope="col" className="p-2.5 text-right">Returns</th>
                    <th scope="col" className="p-2.5 text-right">RTO Rate</th>
                    <th scope="col" className="p-2.5">Recommended Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {prs.map((p) => {
                    const rate = (p.rto_rate * 100).toFixed(1);
                    return (
                      <tr key={p.segment} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                        <td className="p-2.5 font-medium text-slate-900 dark:text-slate-100">{p.segment}</td>
                        <td className="p-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{p.total}</td>
                        <td className="p-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{p.rtos}</td>
                        <td className="p-2.5 text-right font-mono font-bold text-slate-900 dark:text-slate-100">{rate}%</td>
                        <td className="p-2.5 text-slate-600 dark:text-slate-400">
                          {p.rto_rate > 0.7 ? (
                            <span className="text-rose-700 dark:text-rose-400 font-semibold">Nudge Prepaid or Hold</span>
                          ) : p.rto_rate > 0.3 ? (
                            <span className="text-amber-700 dark:text-amber-400 font-semibold">WhatsApp Confirm</span>
                          ) : (
                            <span className="text-teal-700 dark:text-teal-400 font-semibold">Ship As-Is</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-800/60 text-xs text-slate-700 dark:text-slate-300 leading-relaxed border border-slate-200 dark:border-slate-700/70">
            <span className="font-bold text-slate-900 dark:text-slate-100">Founder Takeaway: </span>
            Customers with 2+ prior COD returns experience a catastrophic{' '}
            <span className="font-mono font-bold text-rose-700 dark:text-rose-400">76.5% RTO rate</span> (26 returns on 34 orders).
            Shipping to them as COD as-is guarantees cash loss. Nudging them to prepaid with a ₹25 discount protects
            freight costs while keeping the door open.
          </div>
        </div>

        {/* Discovery 2: The Small-Sample Pincode Trap */}
        <div className="bg-white dark:bg-slate-900 rounded-xl p-6 border border-slate-200 dark:border-slate-800 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">2. The "Pincode Trap" (Ops vs Marketing)</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">Distribution of order counts per unique pincode</p>
            </div>
            <span className="text-xs font-bold text-teal-800 dark:text-teal-300 bg-teal-50 dark:bg-teal-950/50 px-2 py-0.5 rounded border border-teal-200 dark:border-teal-800">
              Bayes Smoothing
            </span>
          </div>

          {viewMode === 'charts' ? (
            <div className="h-60" aria-label="Bar chart showing small sample distribution across pincodes">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={pincodeChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={chartGridColor} />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: chartAxisColor }} />
                  <YAxis tick={{ fontSize: 11, fill: chartAxisColor }} />
                  <Tooltip
                    formatter={(val: any) => [`${val} Pincodes`, 'Count']}
                    contentStyle={chartTooltipStyle}
                  />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {pincodeChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-lg">
              <table className="w-full text-xs text-left" aria-label="Pincode sample size breakdown table">
                <thead className="bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-semibold border-b border-slate-200 dark:border-slate-700">
                  <tr>
                    <th scope="col" className="p-2.5">Pincode Order Frequency</th>
                    <th scope="col" className="p-2.5 text-right">Unique Pincodes</th>
                    <th scope="col" className="p-2.5 text-right">% of All Pincodes</th>
                    <th scope="col" className="p-2.5">Naive Risk</th>
                    <th scope="col" className="p-2.5">Bayes Shrinkage Fix</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {pincodeChartData.map((p) => (
                    <tr key={p.name} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                      <td className="p-2.5 font-medium text-slate-900 dark:text-slate-100">{p.name}</td>
                      <td className="p-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{p.count}</td>
                      <td className="p-2.5 text-right font-mono font-bold text-slate-900 dark:text-slate-100">{p.pct}%</td>
                      <td className="p-2.5 text-rose-700 dark:text-rose-400">High false blacklists</td>
                      <td className="p-2.5 text-teal-700 dark:text-teal-400 font-medium">Shrinks to 28.4% prior</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="p-3.5 rounded-lg bg-slate-50 dark:bg-slate-800/60 text-xs text-slate-700 dark:text-slate-300 leading-relaxed border border-slate-200 dark:border-slate-700/70">
            <span className="font-bold text-slate-900 dark:text-slate-100">Founder Takeaway: </span>
            Out of 1,067 unique pincodes, <span className="font-bold text-slate-900 dark:text-slate-100">541 have only 1 order</span>, and
            1,032 have &lt;5 orders. Banning pincodes based on raw historical RTO bans customers on pure noise! COD
            Compass uses <span className="font-semibold text-teal-700 dark:text-teal-400">Empirical Bayes shrinkage</span> to prevent
            wasting customer acquisition spend.
          </div>
        </div>
      </div>

      {/* Grid 2: Value Bands and September 2026 Holdout Backtest */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Value Bands */}
        <div className="bg-white dark:bg-slate-900 rounded-xl p-6 border border-slate-200 dark:border-slate-800 shadow-xs space-y-4">
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Order Value Band Dynamics</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">RTO probability across basket sizes</p>
          </div>

          {viewMode === 'charts' ? (
            <div className="h-56" aria-label="Bar chart showing RTO rate across order value bands">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={valueChartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={chartGridColor} />
                  <XAxis dataKey="name" tick={{ fontSize: 10, fill: chartAxisColor }} />
                  <YAxis unit="%" tick={{ fontSize: 11, fill: chartAxisColor }} domain={[0, 50]} />
                  <Tooltip
                    formatter={(val: any) => [`${val}% RTO Rate`, 'Rate']}
                    contentStyle={chartTooltipStyle}
                  />
                  <Bar dataKey="rto_rate" fill="#0D9488" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="overflow-x-auto border border-slate-200 dark:border-slate-800 rounded-lg">
              <table className="w-full text-xs text-left" aria-label="Order value band breakdown table">
                <thead className="bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-semibold border-b border-slate-200 dark:border-slate-700">
                  <tr>
                    <th scope="col" className="p-2.5">Value Band</th>
                    <th scope="col" className="p-2.5 text-right">Orders</th>
                    <th scope="col" className="p-2.5 text-right">Returns</th>
                    <th scope="col" className="p-2.5 text-right">RTO Rate</th>
                    <th scope="col" className="p-2.5">Economic Impact</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {vs.map((v) => {
                    const rate = (v.rto_rate * 100).toFixed(1);
                    return (
                      <tr key={v.band} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40">
                        <td className="p-2.5 font-medium text-slate-900 dark:text-slate-100">{v.band}</td>
                        <td className="p-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{v.total}</td>
                        <td className="p-2.5 text-right font-mono text-slate-600 dark:text-slate-400">{v.rtos}</td>
                        <td className="p-2.5 text-right font-mono font-bold text-slate-900 dark:text-slate-100">{rate}%</td>
                        <td className="p-2.5 text-slate-600 dark:text-slate-400">
                          {v.band.includes('>₹2,500') ? (
                            <span className="text-rose-700 dark:text-rose-400 font-semibold">High cash buyer remorse</span>
                          ) : v.band.includes('₹1,000') ? (
                            <span className="text-teal-700 dark:text-teal-400 font-semibold">Optimal conversion sweet spot</span>
                          ) : (
                            <span className="text-slate-600 dark:text-slate-400">Standard COD delivery</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
            Sweet spot: <span className="font-bold text-teal-700 dark:text-teal-300">₹1,000–₹1,499</span> has the lowest RTO rate (20.2%).
            High baskets (&gt;₹2,500) exhibit a spike to 43.2% RTO due to buyer remorse on high cash payments upon courier arrival.
          </p>
        </div>

        {/* September 2026 Holdout Backtest Scenarios */}
        <div className="bg-white dark:bg-slate-900 rounded-xl p-6 border border-slate-200 dark:border-slate-800 shadow-xs space-y-4">
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">September 2026 Holdout Replay Scenarios</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">Simulated monthly net financial gain under 3 adoption scenarios</p>
          </div>

          <div className="space-y-3 pt-2">
            {Object.entries(bts).map(([key, s]) => (
              <div
                key={key}
                className={`p-3.5 rounded-xl border flex items-center justify-between text-xs transition-colors ${
                  key === 'base'
                    ? 'bg-teal-50/70 dark:bg-teal-950/40 border-teal-300 dark:border-teal-800/80 shadow-xs'
                    : 'bg-slate-50 dark:bg-slate-800/60 border-slate-200 dark:border-slate-700/80'
                }`}
              >
                <div>
                  <div className="font-bold text-slate-900 dark:text-slate-100 flex items-center space-x-1.5">
                    <span>{s.name}</span>
                    {key === 'base' && (
                      <span className="text-[10px] font-bold bg-teal-600 text-white px-2 py-0.5 rounded-full">
                        Recommended
                      </span>
                    )}
                  </div>
                  <div className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                    Avoids {s.monthly_avoided_rtos} returns/mo ({(s.avoided_rto_rate * 100).toFixed(0)}% reduction)
                  </div>
                </div>
                <div className="text-right">
                  <div
                    className={`font-mono font-extrabold text-sm ${
                      s.net_monthly_gain_rupees >= 0
                        ? 'text-teal-800 dark:text-teal-300'
                        : 'text-rose-600 dark:text-rose-400'
                    }`}
                  >
                    {s.net_monthly_gain_rupees >= 0
                      ? `+₹${s.net_monthly_gain_rupees.toLocaleString('en-IN', { minimumFractionDigits: 0 })}`
                      : `-₹${Math.abs(s.net_monthly_gain_rupees).toLocaleString('en-IN', { minimumFractionDigits: 0 })}`}
                  </div>
                  <div className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">
                    {s.net_monthly_gain_rupees >= 0 ? 'Net Monthly Profit' : 'Net Monthly Impact'}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="text-[11px] text-slate-500 dark:text-slate-400 italic pt-1">
            *Evaluated strictly on September 2026 holdout split (334 orders) using model frozen at August 31, 2026 cutoff to prevent temporal data leakage.
          </div>
        </div>
      </div>

      {/* Address Quality and Operational Safeguards Card */}
      <div className="bg-white dark:bg-slate-900 rounded-xl p-6 border border-slate-200 dark:border-slate-800 shadow-xs space-y-4">
        <div className="flex items-center space-x-2 text-slate-900 dark:text-slate-100 font-bold text-sm">
          <MapPin className="w-4 h-4 text-teal-600 dark:text-teal-400" />
          <h3>Address Quality & Courier Signal Integrity</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/80 space-y-2">
            <div className="font-bold text-slate-900 dark:text-slate-100 flex items-center space-x-1.5">
              <CheckCircle className="w-3.5 h-3.5 text-teal-600 dark:text-teal-400" />
              <span>Flat/House Number Missing</span>
            </div>
            <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
              Orders lacking specific flat or house identifiers show a +12.4% higher RTO rate due to courier delivery failure on final mile attempts.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/80 space-y-2">
            <div className="font-bold text-slate-900 dark:text-slate-100 flex items-center space-x-1.5">
              <CheckCircle className="w-3.5 h-3.5 text-teal-600 dark:text-teal-400" />
              <span>Address Length &lt; 25 Characters</span>
            </div>
            <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
              Extremely truncated addresses (e.g. &quot;near post office&quot;) trigger automated WhatsApp location prompts to collect landmark details before dispatch.
            </p>
          </div>

          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/80 space-y-2">
            <div className="font-bold text-slate-900 dark:text-slate-100 flex items-center space-x-1.5">
              <AlertOctagon className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
              <span>Courier Pre-shipment Availability</span>
            </div>
            <p className="text-slate-600 dark:text-slate-400 leading-relaxed">
              Courier partner is only assigned post-manifest. COD Compass decision engine intentionally excludes courier column from risk inference to prevent temporal data leakage.
            </p>
          </div>
        </div>
      </div>

      {/* Founder Memo Summary Modal */}
      <Modal
        isOpen={showMemoModal}
        onClose={() => setShowMemoModal(false)}
        title="Founder Strategic Memo — Executive Summary"
        size="lg"
      >
        <div className="space-y-4 text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
          <div className="p-3 bg-teal-50 dark:bg-teal-950/50 rounded-lg border border-teal-200 dark:border-teal-800 text-teal-900 dark:text-teal-200">
            <strong>Key Strategy:</strong> Stop blanket pincode banning. Deploy the 4-tier decision architecture:
            Ship low-risk, Confirm medium-risk, Nudge chronic returners to prepaid, and Hold only catastrophic orders.
          </div>

          <div>
            <h4 className="font-bold text-slate-900 dark:text-slate-100 mb-1">1. The ₹169.40 Direct RTO Cost Formula</h4>
            <p>
              Direct RTO Loss = Forward Freight (₹65) + Reverse Freight (₹55) + Packaging & Handling (₹30) +
              Depreciation & Refurbishment (₹19.40) = <strong>₹169.40</strong> per returned order.
            </p>
          </div>

          <div>
            <h4 className="font-bold text-slate-900 dark:text-slate-100 mb-1">2. Sunk CAC Principle</h4>
            <p>
              The ₹300 customer acquisition cost was spent at click time on Meta/Google Ads.
              Cancelling a borderline order does NOT recover the ₹300; it merely destroys the potential ₹415.80 gross profit contribution.
              Cancelling is only justified when RTO probability exceeds the <strong>64.8% break-even hurdle</strong>.
            </p>
          </div>

          <div>
            <h4 className="font-bold text-slate-900 dark:text-slate-100 mb-1">3. WhatsApp Simulation Economics</h4>
            <p>
              WhatsApp template messages cost ₹0.72/conversation. Offering a ₹25 prepaid discount converts
              ~28% of chronic returners into verified prepaid buyers, generating massive net freight savings.
            </p>
          </div>

          <div className="pt-2 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between">
            <span className="text-[11px] text-slate-500 dark:text-slate-400">
              Complete memo document available at <code>docs/FOUNDER_MEMO.pdf</code>
            </span>
            <button
              onClick={() => setShowMemoModal(false)}
              className="px-4 py-2 bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-900 font-semibold rounded-lg hover:bg-slate-800 dark:hover:bg-slate-200 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
