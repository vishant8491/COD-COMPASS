import React, { useState, useEffect, useMemo } from 'react';
import {
  Sliders,
  Sparkles,
  Save,
  RotateCcw,
  History,
  CheckCircle2,
  AlertTriangle,
  Play,
  TrendingUp,
  DollarSign,
  HelpCircle,
  Shield,
  Layers,
  ArrowRight,
} from 'lucide-react';
import { PolicyConfig, PolicyPreviewResponse } from '../types';
import { fetchActivePolicy, fetchPolicyVersions, savePolicy, previewPolicyImpact } from '../api';
import { useToast } from '../context/ToastContext';
import { Modal } from '../components/Modal';
import { Skeleton } from '../components/Skeleton';

export const PolicyView: React.FC = () => {
  const { showToast } = useToast();
  const [originalPolicy, setOriginalPolicy] = useState<PolicyConfig | null>(null);
  const [policy, setPolicy] = useState<PolicyConfig | null>(null);
  const [versions, setVersions] = useState<PolicyConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState<PolicyPreviewResponse | null>(null);
  const [confirmModalOpen, setConfirmModalOpen] = useState(false);

  const loadPolicies = async () => {
    setLoading(true);
    try {
      const active = await fetchActivePolicy();
      const vers = await fetchPolicyVersions();
      setOriginalPolicy(active);
      setPolicy({ ...active });
      setVersions(vers);
      // Run initial preview
      const prev = await previewPolicyImpact(active, 200);
      setPreview(prev);
    } catch (err) {
      showToast('Failed to load active policy', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPolicies();
  }, []);

  const hasUnsavedChanges = useMemo(() => {
    if (!originalPolicy || !policy) return false;
    return JSON.stringify(originalPolicy) !== JSON.stringify(policy);
  }, [originalPolicy, policy]);

  // Validation: Thresholds must be ordered
  const validationErrors = useMemo(() => {
    if (!policy) return [];
    const errs: string[] = [];
    if (policy.low_risk_threshold >= policy.confirm_threshold) {
      errs.push('Low Risk Max must be strictly lower than Confirmation Upper Bound.');
    }
    if (policy.confirm_threshold >= policy.nudge_threshold) {
      errs.push('Confirmation Upper Bound must be strictly lower than Prepaid Nudge Cutoff.');
    }
    if (policy.nudge_threshold > policy.hold_threshold) {
      errs.push('Prepaid Nudge Cutoff must be lower than or equal to Hold Minimum.');
    }
    return errs;
  }, [policy]);

  const handleReset = () => {
    if (originalPolicy) {
      setPolicy({ ...originalPolicy });
      showToast('Changes reset to last deployed version', 'info');
    }
  };

  const handlePreview = async () => {
    if (!policy || validationErrors.length > 0) return;
    setPreviewing(true);
    try {
      const prev = await previewPolicyImpact(policy, 250);
      setPreview(prev);
      showToast('Simulation complete: Impact estimated on 250 sample orders', 'success');
    } catch (err) {
      showToast('Policy preview failed', 'error');
    } finally {
      setPreviewing(false);
    }
  };

  const handleConfirmDeploy = async () => {
    if (!policy || validationErrors.length > 0) return;
    setSaving(true);
    try {
      await savePolicy(policy);
      showToast(`Policy v${policy.version + 1} deployed and activated successfully!`, 'success');
      setConfirmModalOpen(false);
      await loadPolicies();
    } catch (err) {
      showToast('Failed to deploy policy', 'error');
    } finally {
      setSaving(false);
    }
  };

  if (loading || !policy) {
    return (
      <div className="space-y-6 pb-12 animate-in fade-in duration-150">
        <Skeleton className="h-20 rounded-xl" />
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          <Skeleton className="lg:col-span-7 h-96 rounded-xl" />
          <Skeleton className="lg:col-span-5 h-96 rounded-xl" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12 animate-in fade-in duration-150">
      {/* Top Banner & Action Controls */}
      <div className="bg-white dark:bg-[#0F172A] rounded-xl p-5 border border-slate-200 dark:border-slate-800 shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2">
            <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
              Non-Technical Policy Rules Editor
            </h2>
            <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-teal-50 dark:bg-teal-950/80 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
              Active: {originalPolicy?.policy_id} (v{originalPolicy?.version})
            </span>
            {hasUnsavedChanges && (
              <span className="text-xs font-bold px-2 py-0.5 rounded bg-amber-50 dark:bg-amber-950 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800 flex items-center space-x-1">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                <span>Unsaved Edits</span>
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            Adjust risk cutoffs, incentive discounts, and safeguards. Preview financial impact on real orders before deployment.
          </p>
        </div>

        <div className="flex items-center space-x-2.5">
          {hasUnsavedChanges && (
            <button
              type="button"
              onClick={handleReset}
              className="px-3 py-2 text-xs font-semibold text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-lg transition-colors flex items-center space-x-1"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset</span>
            </button>
          )}

          <button
            type="button"
            onClick={handlePreview}
            disabled={previewing || validationErrors.length > 0}
            className="px-3.5 py-2 text-xs font-bold text-teal-800 dark:text-teal-200 bg-teal-50 dark:bg-teal-950/60 hover:bg-teal-100 dark:hover:bg-teal-900/80 border border-teal-200 dark:border-teal-800 rounded-lg flex items-center space-x-1.5 transition-colors disabled:opacity-50"
          >
            <Play className={`w-3.5 h-3.5 ${previewing ? 'animate-spin' : ''}`} />
            <span>{previewing ? 'Simulating...' : 'Preview Impact'}</span>
          </button>

          <button
            type="button"
            onClick={() => setConfirmModalOpen(true)}
            disabled={saving || validationErrors.length > 0 || !hasUnsavedChanges}
            className="px-4 py-2 text-xs font-bold text-white bg-teal-600 hover:bg-teal-700 rounded-lg shadow-xs flex items-center space-x-1.5 transition-colors disabled:opacity-50"
          >
            <Save className="w-3.5 h-3.5" />
            <span>Deploy New Version</span>
          </button>
        </div>
      </div>

      {/* Validation Alert */}
      {validationErrors.length > 0 && (
        <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-xs text-rose-800 dark:text-rose-300 space-y-1">
          <div className="font-bold flex items-center space-x-1.5">
            <AlertTriangle className="w-4 h-4 text-rose-600 dark:text-rose-400" />
            <span>Invalid Policy Threshold Configuration:</span>
          </div>
          <ul className="list-disc list-inside pl-1 space-y-0.5">
            {validationErrors.map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: 5 Nontechnical Policy Settings Groups (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          <div className="bg-white dark:bg-[#0F172A] rounded-xl p-6 border border-slate-200 dark:border-slate-800 shadow-2xs space-y-6">
            {/* Group 1: Decision Thresholds */}
            <div className="space-y-4">
              <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider border-b border-slate-100 dark:border-slate-800 pb-2">
                1. Calibrated Decision Thresholds
              </h3>

              {/* Threshold 1: Low Risk */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    Low Risk Maximum (Ship As-Is)
                  </span>
                  <div className="flex items-center space-x-1.5">
                    <input
                      type="number"
                      min="0.05"
                      max="0.40"
                      step="0.01"
                      value={policy.low_risk_threshold}
                      onChange={(e) =>
                        setPolicy({ ...policy, low_risk_threshold: parseFloat(e.target.value) || 0 })
                      }
                      className="w-16 text-right px-1.5 py-0.5 rounded border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 font-mono text-xs text-slate-900 dark:text-slate-100"
                    />
                    <span className="text-[11px] font-mono text-emerald-600 dark:text-emerald-400 font-bold">
                      ({(policy.low_risk_threshold * 100).toFixed(0)}%)
                    </span>
                  </div>
                </div>
                <input
                  type="range"
                  min="0.10"
                  max="0.30"
                  step="0.01"
                  value={policy.low_risk_threshold}
                  onChange={(e) =>
                    setPolicy({ ...policy, low_risk_threshold: parseFloat(e.target.value) })
                  }
                  className="w-full accent-teal-600"
                />
                <p className="text-[11px] text-slate-400 dark:text-slate-500">
                  Orders below this cutoff are fast-tracked for immediate dispatch without intervention.
                </p>
              </div>

              {/* Threshold 2: Confirmation Upper Bound */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    Confirmation Upper Bound (WhatsApp)
                  </span>
                  <div className="flex items-center space-x-1.5">
                    <input
                      type="number"
                      min="0.20"
                      max="0.50"
                      step="0.01"
                      value={policy.confirm_threshold}
                      onChange={(e) =>
                        setPolicy({ ...policy, confirm_threshold: parseFloat(e.target.value) || 0 })
                      }
                      className="w-16 text-right px-1.5 py-0.5 rounded border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 font-mono text-xs text-slate-900 dark:text-slate-100"
                    />
                    <span className="text-[11px] font-mono text-sky-600 dark:text-sky-400 font-bold">
                      ({(policy.confirm_threshold * 100).toFixed(0)}%)
                    </span>
                  </div>
                </div>
                <input
                  type="range"
                  min="0.25"
                  max="0.45"
                  step="0.01"
                  value={policy.confirm_threshold}
                  onChange={(e) =>
                    setPolicy({ ...policy, confirm_threshold: parseFloat(e.target.value) })
                  }
                  className="w-full accent-teal-600"
                />
                <p className="text-[11px] text-slate-400 dark:text-slate-500">
                  Moderate-risk orders receive a ₹0.80 WhatsApp confirmation flow.
                </p>
              </div>

              {/* Threshold 3: Prepaid Nudge Upper Bound */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    Prepaid Nudge Upper Bound (Incentive Offer)
                  </span>
                  <div className="flex items-center space-x-1.5">
                    <input
                      type="number"
                      min="0.35"
                      max="0.75"
                      step="0.01"
                      value={policy.nudge_threshold}
                      onChange={(e) =>
                        setPolicy({ ...policy, nudge_threshold: parseFloat(e.target.value) || 0 })
                      }
                      className="w-16 text-right px-1.5 py-0.5 rounded border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 font-mono text-xs text-slate-900 dark:text-slate-100"
                    />
                    <span className="text-[11px] font-mono text-indigo-600 dark:text-indigo-400 font-bold">
                      ({(policy.nudge_threshold * 100).toFixed(0)}%)
                    </span>
                  </div>
                </div>
                <input
                  type="range"
                  min="0.40"
                  max="0.65"
                  step="0.01"
                  value={policy.nudge_threshold}
                  onChange={(e) =>
                    setPolicy({ ...policy, nudge_threshold: parseFloat(e.target.value) })
                  }
                  className="w-full accent-teal-600"
                />
                <p className="text-[11px] text-slate-400 dark:text-slate-500">
                  Elevated-risk orders receive a payment link with an instant prepayment discount.
                </p>
              </div>

              {/* Threshold 4: Hold Minimum */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    Hold / Review Minimum (Economic Breakeven)
                  </span>
                  <div className="flex items-center space-x-1.5">
                    <input
                      type="number"
                      min="0.55"
                      max="0.90"
                      step="0.01"
                      value={policy.hold_threshold}
                      onChange={(e) =>
                        setPolicy({ ...policy, hold_threshold: parseFloat(e.target.value) || 0 })
                      }
                      className="w-16 text-right px-1.5 py-0.5 rounded border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 font-mono text-xs text-slate-900 dark:text-slate-100"
                    />
                    <span className="text-[11px] font-mono text-amber-600 dark:text-amber-400 font-bold">
                      ({(policy.hold_threshold * 100).toFixed(0)}%)
                    </span>
                  </div>
                </div>
                <input
                  type="range"
                  min="0.60"
                  max="0.80"
                  step="0.01"
                  value={policy.hold_threshold}
                  onChange={(e) =>
                    setPolicy({ ...policy, hold_threshold: parseFloat(e.target.value) })
                  }
                  className="w-full accent-teal-600"
                />
                <p className="text-[11px] text-slate-400 dark:text-slate-500">
                  Orders exceeding this threshold break the 64.8% unit-economic breakeven and are held.
                </p>
              </div>
            </div>

            {/* Group 2: Confirmation & Basket Rules */}
            <div className="space-y-3 pt-2">
              <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider border-b border-slate-100 dark:border-slate-800 pb-2">
                2. Confirmation & Basket Rules
              </h3>

              <div className="space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    Force Confirmation Above Basket Size (₹)
                  </span>
                  <span className="font-mono font-bold text-slate-900 dark:text-slate-100">
                    ₹{policy.require_confirm_above_value.toFixed(0)}
                  </span>
                </div>
                <input
                  type="range"
                  min="1000"
                  max="3000"
                  step="100"
                  value={policy.require_confirm_above_value}
                  onChange={(e) =>
                    setPolicy({ ...policy, require_confirm_above_value: parseFloat(e.target.value) })
                  }
                  className="w-full accent-teal-600"
                />
              </div>

              <div className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    Minimum Pincode Sample Size
                  </span>
                  <span className="font-mono font-bold text-slate-900 dark:text-slate-100">
                    {policy.min_pincode_sample} orders
                  </span>
                </div>
                <input
                  type="range"
                  min="2"
                  max="20"
                  step="1"
                  value={policy.min_pincode_sample}
                  onChange={(e) =>
                    setPolicy({ ...policy, min_pincode_sample: parseInt(e.target.value) })
                  }
                  className="w-full accent-teal-600"
                />
                <p className="text-[11px] text-slate-400">
                  Pincodes with fewer orders are smoothed toward the national prior (28.4%) to avoid the pincode trap.
                </p>
              </div>
            </div>

            {/* Group 3: Prepaid Incentive Offer */}
            <div className="space-y-3 pt-2">
              <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider border-b border-slate-100 dark:border-slate-800 pb-2">
                3. Prepaid Incentive Offer
              </h3>

              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-800 dark:text-slate-200 block">
                  Prepaid Instant Discount Amount (₹)
                </label>
                <div className="grid grid-cols-4 gap-2">
                  {[0.0, 15.0, 25.0, 35.0].map((disc) => (
                    <button
                      key={disc}
                      type="button"
                      onClick={() => setPolicy({ ...policy, prepaid_discount_amount: disc })}
                      className={`py-2 text-xs font-mono font-bold rounded-lg border transition-all ${
                        policy.prepaid_discount_amount === disc
                          ? 'bg-teal-600 text-white border-teal-600 shadow-xs'
                          : 'bg-slate-50 dark:bg-slate-900 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800'
                      }`}
                    >
                      ₹{disc.toFixed(0)}
                    </button>
                  ))}
                </div>
                <p className="text-[11px] text-slate-400">
                  Recommended: ₹25 discount maximizes total incremental profit pool with ~22% expected conversion.
                </p>
              </div>
            </div>

            {/* Group 4: Cancellation Safeguard Toggle */}
            <div className="space-y-3 pt-2">
              <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider border-b border-slate-100 dark:border-slate-800 pb-2">
                4. Operational Safeguards
              </h3>

              <div className="flex items-center justify-between p-3.5 rounded-xl bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                <div className="pr-4">
                  <span className="text-xs font-bold text-slate-900 dark:text-slate-100 block">
                    Automatic Cancellation on High Risk
                  </span>
                  <span className="text-[11px] text-slate-500 dark:text-slate-400">
                    Default OFF. High-risk orders are placed on Hold for human verification before cancelling,
                    protecting ₹300 customer acquisition spend.
                  </span>
                </div>
                <input
                  type="checkbox"
                  checked={policy.auto_cancel_enabled}
                  onChange={(e) => setPolicy({ ...policy, auto_cancel_enabled: e.target.checked })}
                  className="w-4 h-4 rounded text-teal-600 focus:ring-teal-500"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Right: Pre-Application Simulation Preview (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          <div className="bg-white dark:bg-[#0F172A] rounded-xl p-6 border border-teal-200 dark:border-teal-800 shadow-2xs space-y-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2 text-teal-900 dark:text-teal-200">
                <Sparkles className="w-4 h-4 text-teal-600 dark:text-teal-400" />
                <h3 className="font-bold text-xs uppercase tracking-wider">
                  Pre-Application Impact Preview
                </h3>
              </div>
              <span className="text-[10px] text-slate-400 font-mono">Simulated Sample</span>
            </div>

            {preview ? (
              <div className="space-y-5">
                {/* Net Monthly Bottom-Line Gain */}
                <div className="p-4 rounded-xl bg-teal-50/70 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800">
                  <span className="text-[10px] font-bold text-teal-800 dark:text-teal-300 uppercase tracking-wider block">
                    Projected Net Monthly Impact
                  </span>
                  <div className="mt-1 flex items-baseline space-x-2">
                    <span className="text-2xl font-extrabold text-teal-950 dark:text-teal-100 font-mono">
                      +₹{preview.projected_net_monthly_impact_rupees.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                    </span>
                    <span className="text-xs font-semibold text-teal-700 dark:text-teal-400">/ month</span>
                  </div>
                  <p className="text-[11px] text-teal-700/80 dark:text-teal-400/80 mt-1">
                    Simulated over {preview.total_orders_evaluated} orders scaled to standard 1,650 monthly COD volume
                  </p>
                </div>

                {/* Projected Action Mix */}
                <div className="space-y-2.5">
                  <span className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider block">
                    Projected Pre-Shipment Action Mix
                  </span>

                  <div className="space-y-2 text-xs">
                    <div>
                      <div className="flex justify-between text-slate-600 dark:text-slate-400 mb-1">
                        <span>Ship As-Is</span>
                        <span className="font-bold text-emerald-700 dark:text-emerald-400">
                          {preview.action_percentages.SHIP_AS_IS}%
                        </span>
                      </div>
                      <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div
                          className="bg-emerald-500 h-2 rounded-full transition-all"
                          style={{ width: `${preview.action_percentages.SHIP_AS_IS}%` }}
                        />
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between text-slate-600 dark:text-slate-400 mb-1">
                        <span>Confirm via WhatsApp</span>
                        <span className="font-bold text-sky-700 dark:text-sky-400">
                          {preview.action_percentages.CONFIRM}%
                        </span>
                      </div>
                      <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div
                          className="bg-sky-500 h-2 rounded-full transition-all"
                          style={{ width: `${preview.action_percentages.CONFIRM}%` }}
                        />
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between text-slate-600 dark:text-slate-400 mb-1">
                        <span>Nudge to Prepaid</span>
                        <span className="font-bold text-indigo-700 dark:text-indigo-400">
                          {preview.action_percentages.NUDGE_PREPAID}%
                        </span>
                      </div>
                      <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div
                          className="bg-indigo-500 h-2 rounded-full transition-all"
                          style={{ width: `${preview.action_percentages.NUDGE_PREPAID}%` }}
                        />
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between text-slate-600 dark:text-slate-400 mb-1">
                        <span>Hold for Review</span>
                        <span className="font-bold text-amber-700 dark:text-amber-400">
                          {preview.action_percentages.HOLD}%
                        </span>
                      </div>
                      <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div
                          className="bg-amber-500 h-2 rounded-full transition-all"
                          style={{ width: `${preview.action_percentages.HOLD}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Sub-breakdown */}
                <div className="pt-2 border-t border-slate-100 dark:border-slate-800 grid grid-cols-2 gap-2 text-xs">
                  <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                    <span className="text-[10px] text-slate-400 block uppercase font-semibold">Avoided Freight</span>
                    <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400">
                      +₹{preview.projected_avoided_rto_rupees.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                    </span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                    <span className="text-[10px] text-slate-400 block uppercase font-semibold">Intervention Costs</span>
                    <span className="font-mono font-bold text-slate-700 dark:text-slate-300">
                      -₹{preview.projected_messaging_discount_cost_rupees.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-slate-400 text-xs">
                Click Preview Impact to run pre-application simulation
              </div>
            )}
          </div>

          {/* Version History Table */}
          <div className="bg-white dark:bg-[#0F172A] rounded-xl p-5 border border-slate-200 dark:border-slate-800 shadow-2xs space-y-3">
            <h3 className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider flex items-center space-x-1.5">
              <History className="w-3.5 h-3.5 text-slate-400" />
              <span>Policy Version History</span>
            </h3>

            <div className="divide-y divide-slate-100 dark:divide-slate-800 max-h-48 overflow-y-auto">
              {versions.map((v) => (
                <div key={v.version} className="py-2 flex items-center justify-between text-xs">
                  <div>
                    <div className="font-bold text-slate-900 dark:text-slate-100">
                      v{v.version} — {v.name}
                    </div>
                    <div className="text-[10px] text-slate-400 font-mono">
                      Cutoffs: {(v.low_risk_threshold * 100).toFixed(0)}% / {(v.confirm_threshold * 100).toFixed(0)}% / {(v.nudge_threshold * 100).toFixed(0)}%
                    </div>
                  </div>
                  {v.is_active ? (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-teal-50 dark:bg-teal-950 text-teal-700 dark:text-teal-300 border border-teal-200 dark:border-teal-800">
                      Active
                    </span>
                  ) : (
                    <button
                      onClick={() => setPolicy({ ...v })}
                      className="text-xs text-teal-600 dark:text-teal-400 hover:underline font-semibold"
                    >
                      Inspect
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Confirmation Modal for Deploying Policy Version */}
      <Modal
        isOpen={confirmModalOpen}
        onClose={() => setConfirmModalOpen(false)}
        title="Deploy New Policy Version"
        description="This will create a new immutable policy version and apply it to all incoming COD orders."
        size="md"
      >
        <div className="space-y-4">
          <div className="p-3.5 rounded-xl bg-teal-50 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800 text-xs text-teal-900 dark:text-teal-200 space-y-1">
            <span className="font-bold block">Summary of Policy Changes:</span>
            <ul className="list-disc list-inside space-y-0.5 text-[11px] text-teal-800 dark:text-teal-300">
              <li>Low Risk Cutoff: {(policy.low_risk_threshold * 100).toFixed(0)}% RTO probability</li>
              <li>Confirmation Upper Bound: {(policy.confirm_threshold * 100).toFixed(0)}% RTO probability</li>
              <li>Prepaid Nudge Upper Bound: {(policy.nudge_threshold * 100).toFixed(0)}% RTO probability</li>
              <li>Hold Threshold: {(policy.hold_threshold * 100).toFixed(0)}% RTO probability</li>
              <li>Prepaid Discount: ₹{policy.prepaid_discount_amount.toFixed(0)}</li>
              <li>Auto-cancel: {policy.auto_cancel_enabled ? 'ENABLED' : 'DISABLED (Hold)'}</li>
            </ul>
          </div>

          <div className="text-xs text-slate-500 dark:text-slate-400">
            Historical evaluations will retain their original policy version for audit compliance.
          </div>

          <div className="flex items-center justify-end space-x-2 pt-2">
            <button
              type="button"
              onClick={() => setConfirmModalOpen(false)}
              className="px-3 py-1.5 text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={saving}
              onClick={handleConfirmDeploy}
              className="px-4 py-1.5 text-xs font-bold text-white bg-teal-600 hover:bg-teal-700 rounded-lg shadow-xs disabled:opacity-50"
            >
              Confirm & Deploy v{policy.version + 1}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
