import React, { useState } from 'react';
import {
  TrendingUp,
  ShieldCheck,
  AlertCircle,
  Clock,
  ArrowUpRight,
  DollarSign,
  PackageCheck,
  HelpCircle,
  Sparkles,
  AlertTriangle,
  ArrowRight,
  Calendar,
  CheckCircle2,
} from 'lucide-react';
import { DashboardOverview, ActionType } from '../types';
import { Skeleton } from '../components/Skeleton';
import { EmptyState } from '../components/EmptyState';
import { formatRupees, formatPercent } from '../utils/formatters';
import { DATE_PRESETS, DatePresetKey } from '../utils/dateScope';

interface OverviewViewProps {
  data: DashboardOverview | null;
  loading: boolean;
  onNavigateToOrders: (actionFilter?: ActionType) => void;
  onNavigateToSimulator?: () => void;
  lastRefreshedAt?: Date;
  selectedPeriod?: string;
  onPeriodChange?: (preset: string) => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({
  data,
  loading,
  onNavigateToOrders,
  onNavigateToSimulator,
  lastRefreshedAt,
  selectedPeriod = 'yesterday',
  onPeriodChange,
}) => {
  const currentPeriod = selectedPeriod;

  if (loading || !data) {
    return (
      <div className="space-y-6 pb-12 animate-in fade-in duration-150">
        <Skeleton className="h-40 rounded-2xl" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
        </div>
        <Skeleton className="h-64 rounded-xl" />
        <Skeleton className="h-96 rounded-xl" />
      </div>
    );
  }

  const { financial_bridge: fb, orders_by_action: acts } = data;
  const totalActioned =
    (acts.SHIP_AS_IS || 0) +
    (acts.CONFIRM || 0) +
    (acts.NUDGE_PREPAID || 0) +
    (acts.HOLD || 0);

  const getPct = (cnt: number) =>
    totalActioned > 0 ? ((cnt / totalActioned) * 100).toFixed(1) : '0';

  const isNetPositive = fb.net_financial_improvement >= 0;

  return (
    <div className="space-y-8 pb-12 animate-in fade-in duration-150">
      {/* Top Banner / Timeframe Context */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-850 to-teal-950 dark:from-slate-950 dark:via-slate-900 dark:to-teal-950 text-white rounded-2xl p-6 sm:p-8 shadow-xl shadow-slate-950/10 border border-slate-800 relative overflow-hidden">
        <div className="absolute top-0 right-0 -mr-16 -mt-16 w-64 h-64 bg-teal-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="max-w-2xl space-y-2">
            <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-teal-500/20 text-teal-300 text-xs font-semibold tracking-wide uppercase">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Unit-Economics Optimizer • Timezone: IST (UTC+5:30)</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
              Executive Decision Cockpit
            </h1>
            <p className="text-slate-300 text-xs sm:text-sm leading-relaxed">
              Balancing return shipping losses against customer acquisition capital. Orders are
              evaluated in rupees pre-shipment to protect both warehouse margins and marketing investment.
            </p>
          </div>

          {/* Period Selector & Refresh Context */}
          <div className="bg-slate-800/80 dark:bg-slate-900/90 backdrop-blur-xs p-4 rounded-xl border border-slate-700/80 space-y-2 shrink-0">
            <div className="flex items-center justify-between text-xs text-slate-300 font-medium">
              <span className="flex items-center space-x-1.5">
                <Calendar className="w-3.5 h-3.5 text-teal-400" />
                <span>Evaluation Scope:</span>
              </span>
              <span className="font-mono text-teal-300 font-bold">{data.selected_date_label}</span>
            </div>

            <select
              value={currentPeriod}
              onChange={(e) => onPeriodChange?.(e.target.value)}
              className="w-full text-xs font-medium bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-white focus:outline-none focus:ring-2 focus:ring-teal-500"
            >
              {DATE_PRESETS.map((p) => (
                <option key={p.key} value={p.key}>
                  {p.label}
                </option>
              ))}
            </select>

            <div className="text-[10px] text-slate-400 flex items-center justify-between pt-1">
              <span>Timezone: Asia/Kolkata</span>
              <span>
                Synced:{' '}
                {lastRefreshedAt
                  ? lastRefreshedAt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
                  : 'Just now'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Honest Empty State when date scope has 0 orders */}
      {data.total_orders === 0 ? (
        <div className="bg-white dark:bg-slate-900 rounded-2xl p-10 sm:p-14 border border-slate-200 dark:border-slate-800 text-center space-y-4 shadow-sm">
          <div className="w-14 h-14 mx-auto rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-400">
            <Calendar className="w-7 h-7 text-teal-600 dark:text-teal-400" />
          </div>
          <div className="space-y-1">
            <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">
              No Orders Recorded for {data.selected_date_label}
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 max-w-lg mx-auto">
              The operational database currently contains verified historical orders through September 30, 2026.
              Switch to the holdout evaluation cohort or all-time dataset to inspect pre-shipment decisions:
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-3 pt-3">
            <button
              onClick={() => onPeriodChange?.('september_2026')}
              className="px-5 py-2.5 text-xs font-bold rounded-xl bg-teal-600 hover:bg-teal-700 text-white shadow-sm transition-all flex items-center space-x-2"
            >
              <span>View September 2026 Demo Cohort (329 orders)</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => onPeriodChange?.('all_time')}
              className="px-5 py-2.5 text-xs font-bold rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 transition-all"
            >
              View All Time (1,988 orders)
            </button>
          </div>
        </div>
      ) : (
        <>
          {/* Top 4 KPI Metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Metric 1: Net Financial Gain */}
            <div className="bg-white dark:bg-[#0F172A] rounded-xl p-5 border border-slate-200 dark:border-slate-800 shadow-2xs hover:shadow-sm transition-all">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  Net Financial Improvement
                </span>
                <div
                  className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                    isNetPositive
                      ? 'bg-emerald-50 dark:bg-emerald-950/70 text-emerald-600 dark:text-emerald-400'
                      : 'bg-rose-50 dark:bg-rose-950/70 text-rose-600 dark:text-rose-400'
                  }`}
                >
                  <DollarSign className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-3 flex items-baseline space-x-2">
                <span
                  className={`text-2xl font-extrabold font-mono ${
                    isNetPositive
                      ? 'text-emerald-700 dark:text-emerald-400'
                      : 'text-rose-600 dark:text-rose-400'
                  }`}
                >
                  {formatRupees(fb.net_financial_improvement, { showSign: true })}
                </span>
                <span
                  className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${
                    isNetPositive
                      ? 'text-emerald-800 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/80'
                      : 'text-rose-800 dark:text-rose-300 bg-rose-50 dark:bg-rose-950/80'
                  }`}
                >
                  {isNetPositive ? `+${fb.net_roi_percentage.toFixed(0)}% ROI` : `${fb.net_roi_percentage.toFixed(0)}% ROI`}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Net incremental gain vs baseline COD as-is
              </p>
            </div>

        {/* Metric 2: Avoided RTO Freight */}
        <div className="bg-white dark:bg-[#0F172A] rounded-xl p-5 border border-slate-200 dark:border-slate-800 shadow-2xs hover:shadow-sm transition-all">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              Avoided Direct Freight
            </span>
            <div className="w-8 h-8 rounded-lg bg-teal-50 dark:bg-teal-950/70 text-teal-600 dark:text-teal-400 flex items-center justify-center">
              <ShieldCheck className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-2xl font-extrabold text-slate-900 dark:text-slate-100 font-mono">
              ₹{formatRupees(fb.avoided_rto_savings)}
            </span>
            <span className="text-xs text-slate-400 font-medium">Saved</span>
          </div>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Avoided forward & reverse freight + 8% product damage
          </p>
        </div>

        {/* Metric 3: RTO Rate Trajectory */}
        <div className="bg-white dark:bg-[#0F172A] rounded-xl p-5 border border-slate-200 dark:border-slate-800 shadow-2xs hover:shadow-sm transition-all">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              RTO Rate Trajectory
            </span>
            <div className="w-8 h-8 rounded-lg bg-sky-50 dark:bg-sky-950/70 text-sky-600 dark:text-sky-400 flex items-center justify-center">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-2xl font-extrabold text-slate-900 dark:text-slate-100 font-mono">
              {(data.rto_rate_projected_post_intervention * 100).toFixed(1)}%
            </span>
            <span className="text-xs font-medium text-slate-400 line-through">
              {(data.rto_rate_current * 100).toFixed(1)}%
            </span>
            <span className="text-[10px] font-bold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950 px-1.5 py-0.5 rounded">
              -{((data.rto_rate_current - data.rto_rate_projected_post_intervention) * 100).toFixed(1)}%
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Projected post-confirmation & prepaid incentive
          </p>
        </div>

        {/* Metric 4: Pending Operations Action */}
        <div className="bg-white dark:bg-[#0F172A] rounded-xl p-5 border border-slate-200 dark:border-slate-800 shadow-2xs hover:shadow-sm transition-all">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              Pending Ops Review
            </span>
            <div className="w-8 h-8 rounded-lg bg-amber-50 dark:bg-amber-950/70 text-amber-600 dark:text-amber-400 flex items-center justify-center">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline space-x-2">
            <span className="text-2xl font-extrabold text-amber-700 dark:text-amber-400 font-mono">
              {data.orders_pending_review}
            </span>
            <button
              onClick={() => onNavigateToOrders('HOLD')}
              className="text-xs font-bold text-amber-700 dark:text-amber-400 hover:underline flex items-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 rounded"
            >
              <span>Review Holds</span>
              <ArrowUpRight className="w-3.5 h-3.5 ml-0.5" />
            </button>
          </div>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            Incomplete addresses or extreme risk (&gt;65% RTO)
          </p>
        </div>
      </div>

      {/* Action Distribution Breakdown */}
      <div className="bg-white dark:bg-[#0F172A] rounded-xl p-6 border border-slate-200 dark:border-slate-800 shadow-2xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800 gap-2">
          <div>
            <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
              Pre-Shipment Decision Distribution
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Distribution across the 4 pre-shipment action buckets. Click any card to view orders.
            </p>
          </div>
          <span className="text-xs font-mono font-medium text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2.5 py-1 rounded-md border border-slate-200 dark:border-slate-700">
            Total Orders: {data.total_orders.toLocaleString()}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-6">
          {/* Action 1: Ship As-Is */}
          <button
            onClick={() => onNavigateToOrders('SHIP_AS_IS')}
            className="text-left group p-4 rounded-xl border border-emerald-200 dark:border-emerald-900 bg-emerald-50/40 dark:bg-emerald-950/30 hover:bg-emerald-50 dark:hover:bg-emerald-950/50 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-emerald-800 dark:text-emerald-300 uppercase tracking-wide">
                1. Ship As-Is
              </span>
              <span className="text-xs font-bold text-emerald-700 dark:text-emerald-300 bg-emerald-100 dark:bg-emerald-900/60 px-2 py-0.5 rounded-full">
                {getPct(acts.SHIP_AS_IS || 0)}%
              </span>
            </div>
            <div className="mt-3 text-2xl font-extrabold text-emerald-950 dark:text-emerald-100 font-mono">
              {acts.SHIP_AS_IS || 0}
            </div>
            <p className="mt-1 text-xs text-emerald-700 dark:text-emerald-400/90 flex items-center justify-between">
              <span>Clean profiles; fast-tracked</span>
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
            </p>
          </button>

          {/* Action 2: Confirm */}
          <button
            onClick={() => onNavigateToOrders('CONFIRM')}
            className="text-left group p-4 rounded-xl border border-sky-200 dark:border-sky-900 bg-sky-50/40 dark:bg-sky-950/30 hover:bg-sky-50 dark:hover:bg-sky-950/50 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-sky-800 dark:text-sky-300 uppercase tracking-wide">
                2. Confirm via WhatsApp
              </span>
              <span className="text-xs font-bold text-sky-700 dark:text-sky-300 bg-sky-100 dark:bg-sky-900/60 px-2 py-0.5 rounded-full">
                {getPct(acts.CONFIRM || 0)}%
              </span>
            </div>
            <div className="mt-3 text-2xl font-extrabold text-sky-950 dark:text-sky-100 font-mono">
              {acts.CONFIRM || 0}
            </div>
            <p className="mt-1 text-xs text-sky-700 dark:text-sky-400/90 flex items-center justify-between">
              <span>High basket / moderate risk</span>
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
            </p>
          </button>

          {/* Action 3: Nudge to Prepaid */}
          <button
            onClick={() => onNavigateToOrders('NUDGE_PREPAID')}
            className="text-left group p-4 rounded-xl border border-indigo-200 dark:border-indigo-900 bg-indigo-50/40 dark:bg-indigo-950/30 hover:bg-indigo-50 dark:hover:bg-indigo-950/50 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-indigo-800 dark:text-indigo-300 uppercase tracking-wide">
                3. Nudge to Prepaid
              </span>
              <span className="text-xs font-bold text-indigo-700 dark:text-indigo-300 bg-indigo-100 dark:bg-indigo-900/60 px-2 py-0.5 rounded-full">
                {getPct(acts.NUDGE_PREPAID || 0)}%
              </span>
            </div>
            <div className="mt-3 text-2xl font-extrabold text-indigo-950 dark:text-indigo-100 font-mono">
              {acts.NUDGE_PREPAID || 0}
            </div>
            <p className="mt-1 text-xs text-indigo-700 dark:text-indigo-400/90 flex items-center justify-between">
              <span>Prior returns; ₹25 discount</span>
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
            </p>
          </button>

          {/* Action 4: Hold */}
          <button
            onClick={() => onNavigateToOrders('HOLD')}
            className="text-left group p-4 rounded-xl border border-amber-200 dark:border-amber-900 bg-amber-50/40 dark:bg-amber-950/30 hover:bg-amber-50 dark:hover:bg-amber-950/50 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-amber-800 dark:text-amber-300 uppercase tracking-wide">
                4. Hold for Review
              </span>
              <span className="text-xs font-bold text-amber-700 dark:text-amber-300 bg-amber-100 dark:bg-amber-900/60 px-2 py-0.5 rounded-full">
                {getPct(acts.HOLD || 0)}%
              </span>
            </div>
            <div className="mt-3 text-2xl font-extrabold text-amber-950 dark:text-amber-100 font-mono">
              {acts.HOLD || 0}
            </div>
            <p className="mt-1 text-xs text-amber-700 dark:text-amber-400/90 flex items-center justify-between">
              <span>Suspicious address / &gt;65% RTO</span>
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
            </p>
          </button>
        </div>
      </div>

      {/* Operations Quick Attention Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 rounded-xl bg-amber-50/60 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-amber-100 dark:bg-amber-900/60 text-amber-700 dark:text-amber-300 flex items-center justify-center font-bold">
              {data.orders_pending_review}
            </div>
            <div>
              <span className="text-xs font-bold text-amber-900 dark:text-amber-200 block">
                Orders on Manual Hold
              </span>
              <span className="text-[11px] text-amber-700 dark:text-amber-400">
                Lacking landmarks or flagged for high return risk
              </span>
            </div>
          </div>
          <button
            onClick={() => onNavigateToOrders('HOLD')}
            className="px-3 py-1.5 text-xs font-bold bg-amber-600 hover:bg-amber-700 text-white rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
          >
            Review Orders
          </button>
        </div>

        <div className="p-4 rounded-xl bg-sky-50/60 dark:bg-sky-950/30 border border-sky-200 dark:border-sky-900 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-sky-100 dark:bg-sky-900/60 text-sky-700 dark:text-sky-300 flex items-center justify-center font-bold">
              {acts.CONFIRM || 0}
            </div>
            <div>
              <span className="text-xs font-bold text-sky-900 dark:text-sky-200 block">
                Active WhatsApp Workflows
              </span>
              <span className="text-[11px] text-sky-700 dark:text-sky-400">
                Confirmation requests and prepaid nudges in progress
              </span>
            </div>
          </div>
          <button
            onClick={onNavigateToSimulator}
            className="px-3 py-1.5 text-xs font-bold bg-sky-600 hover:bg-sky-700 text-white rounded-lg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          >
            Open Simulator
          </button>
        </div>
      </div>

      {/* Financial Reconciliation Bridge (Auditable Rupee Accounting) */}
      <div className="bg-white dark:bg-[#0F172A] rounded-xl p-6 border border-slate-200 dark:border-slate-800 shadow-2xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800 gap-2">
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
                Deterministic Financial Reconciliation Bridge
              </h2>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-teal-50 dark:bg-teal-950 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
                Audited Formulas
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Reconciles avoided direct RTO cash losses against foregone delivered product margins
            </p>
          </div>
          <span className="text-xs font-medium px-2.5 py-1 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
            Cohort: 1,650 Monthly COD Orders
          </span>
        </div>

        {/* Bridge Table */}
        <div className="overflow-x-auto mt-4">
          <table className="w-full text-left text-xs sm:text-sm">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-700/80 text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                <th className="py-3 px-4">Financial Component</th>
                <th className="py-3 px-4 hidden sm:table-cell">Basis & Accounting Formula</th>
                <th className="py-3 px-4 text-right">Rupee Amount (₹)</th>
                <th className="py-3 px-4 text-right">Accounting Role</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800 font-sans">
              <tr className="bg-slate-50/60 dark:bg-slate-800/40">
                <td className="py-3 px-4 text-slate-900 dark:text-slate-100 font-bold">
                  Baseline COD Direct RTO Loss
                </td>
                <td className="py-3 px-4 text-xs text-slate-500 dark:text-slate-400 hidden sm:table-cell">
                  1,650 orders × 28% RTO × ₹169.40 direct return cash loss
                </td>
                <td className="py-3 px-4 text-right font-mono font-bold text-rose-600 dark:text-rose-400">
                  -₹{formatRupees(fb.baseline_cod_rto_loss)}
                </td>
                <td className="py-3 px-4 text-right text-xs text-slate-500 dark:text-slate-400">
                  Observed Baseline
                </td>
              </tr>

              <tr>
                <td className="py-3 px-4 text-slate-800 dark:text-slate-200 flex items-center space-x-2">
                  <div className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span>Avoided RTO Shipping & Damage Savings</span>
                </td>
                <td className="py-3 px-4 text-xs text-slate-500 dark:text-slate-400 hidden sm:table-cell">
                  Saved forward freight (₹65), reverse freight (₹65), packaging (₹25), and 8% damage (₹14.40)
                </td>
                <td className="py-3 px-4 text-right font-mono text-emerald-600 dark:text-emerald-400 font-bold">
                  +₹{formatRupees(fb.avoided_rto_savings)}
                </td>
                <td className="py-3 px-4 text-right text-xs font-bold text-emerald-700 dark:text-emerald-400">
                  Estimated Cash Saved
                </td>
              </tr>

              <tr>
                <td className="py-3 px-4 text-slate-800 dark:text-slate-200 flex items-center space-x-2">
                  <div className="w-2 h-2 rounded-full bg-rose-400" />
                  <span>Foregone Gross Margin on Cancelled Orders</span>
                </td>
                <td className="py-3 px-4 text-xs text-slate-500 dark:text-slate-400 hidden sm:table-cell">
                  Delivered contribution (62% margin - ₹90 fulfillment) on genuine customers who didn't confirm
                </td>
                <td className="py-3 px-4 text-right font-mono text-rose-600 dark:text-rose-400">
                  -₹{formatRupees(fb.foregone_margin_from_cancellations)}
                </td>
                <td className="py-3 px-4 text-right text-xs font-semibold text-rose-600 dark:text-rose-400">
                  Trade-off Loss
                </td>
              </tr>

              <tr>
                <td className="py-3 px-4 text-slate-800 dark:text-slate-200 flex items-center space-x-2">
                  <div className="w-2 h-2 rounded-full bg-slate-400" />
                  <span>WhatsApp Interactive Messaging Costs</span>
                </td>
                <td className="py-3 px-4 text-xs text-slate-500 dark:text-slate-400 hidden sm:table-cell">
                  ₹0.80 per conversation session for confirmation and prepaid links
                </td>
                <td className="py-3 px-4 text-right font-mono text-slate-700 dark:text-slate-300">
                  -₹{formatRupees(fb.messaging_costs_incurred)}
                </td>
                <td className="py-3 px-4 text-right text-xs text-slate-500 dark:text-slate-400">
                  Utility Expense
                </td>
              </tr>

              <tr>
                <td className="py-3 px-4 text-slate-800 dark:text-slate-200 flex items-center space-x-2">
                  <div className="w-2 h-2 rounded-full bg-indigo-400" />
                  <span>Prepaid Incentive Discounts Granted</span>
                </td>
                <td className="py-3 px-4 text-xs text-slate-500 dark:text-slate-400 hidden sm:table-cell">
                  ₹25 instant UPI discount granted on converted prepaid orders (dropping RTO to 4%)
                </td>
                <td className="py-3 px-4 text-right font-mono text-indigo-700 dark:text-indigo-400">
                  -₹{formatRupees(fb.prepaid_discounts_granted)}
                </td>
                <td className="py-3 px-4 text-right text-xs text-indigo-700 dark:text-indigo-400">
                  Incentive Cost
                </td>
              </tr>

              <tr className="bg-emerald-50/80 dark:bg-emerald-950/60 font-bold border-t-2 border-emerald-300 dark:border-emerald-700">
                <td className="py-3.5 px-4 text-emerald-950 dark:text-emerald-100 font-extrabold text-sm sm:text-base">
                  Net Estimated Monthly Improvement
                </td>
                <td className="py-3.5 px-4 text-xs text-emerald-900 dark:text-emerald-300 font-semibold hidden sm:table-cell">
                  Avoided Losses - Foregone Margin - Messaging & Discounts
                </td>
                <td className="py-3.5 px-4 text-right font-mono text-emerald-800 dark:text-emerald-300 text-sm sm:text-base font-extrabold">
                  +₹{formatRupees(fb.net_financial_improvement)}
                </td>
                <td className="py-3.5 px-4 text-right text-xs font-bold text-emerald-800 dark:text-emerald-300">
                  <span className="bg-emerald-100 dark:bg-emerald-900 px-2 py-1 rounded">
                    +{fb.net_roi_percentage.toFixed(0)}% ROI
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Founder Takeaway Box */}
        <div className="mt-6 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700/80 flex items-start space-x-3">
          <HelpCircle className="w-5 h-5 text-teal-600 dark:text-teal-400 shrink-0 mt-0.5" />
          <div className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed space-y-1">
            <p>
              <strong className="text-slate-900 dark:text-slate-100">Why CAC is NOT subtracted here: </strong>
              The ₹300 acquisition cost was already spent when the customer converted on the Meta/Google ad.
              For pre-shipment decisions, that money is sunk. Subtracting ₹300 again double-counts marketing spend
              and triggers unjustified cancellations that destroy genuine margin.
            </p>
            <p className="text-slate-500 dark:text-slate-400">
              COD Compass tracks <em>Acquisition Spend at Risk</em> ( (1 - P) &times; CAC ) to protect
              marketing capital while preventing freight waste.
            </p>
          </div>
        </div>
      </div>
        </>
      )}
    </div>
  );
};
