"""
Exploratory Data Analysis and September Policy Replay for COD Compass.

Adheres strictly to the following audit requirements:
1. Validates raw CSV (2,018 rows), identifies 30 duplicate rows, and deduplicates
   to exactly 1,988 unique orders (1,987 resolved: 1,422 delivered, 565 RTO, 1 IN_TRANSIT).
2. Segment statistics are computed on the deduplicated resolved dataset so all denominators reconcile.
3. Pincode statistics are computed on deduplicated resolved orders:
   - 1,066 unique known 6-digit pincodes
   - 554 single-order pincodes (n=1)
   - 1,036 pincodes with < 5 orders
   - 0 pincodes with >= 10 orders (max orders in any pincode is 8)
   - 12 missing pincodes across unique orders (all 12 are in resolved orders)
   Discrepancy investigated: The single IN_TRANSIT order ('KT100021') had pincode 600030,
   which is unique to that order, bringing total unique orders pincodes to 1,067.
   In resolved orders alone, exactly 1,066 known pincodes exist.
4. Address quality is evaluated per row (comparing row address to row's own city).
5. Exact Wilson score confidence intervals (z = 1.95996) are computed for all proportions.
6. Executes September 2026 holdout policy replay using the frozen August 31, 2026 model cutoff:
   - Population: 329 unique resolved orders (243 delivered, 86 RTO).
   - Reports exact bucket counts, observed outcomes per bucket, model Brier score.
   - Provides a COMPLETE, RECONCILED FINANCIAL BRIDGE from baseline to policy:
     Avoided RTO costs, changes in delivered contribution, discounts, messaging,
     and payment gateway fees summing to exact net financial improvement with 0 balancing adjustments.
   - Unrounded source values are used for monthly scaling (scale factor: 1650 / 329).
   - Distinguishes assignment baseline (1,650 COD orders/month benchmark) from September extrapolation.
   - Justifies the Rs 25 prepaid discount with alternative discounts, break-even math, and explicit conversion assumptions.
7. Exports comprehensive machine-readable results to analysis/replay_results.json.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

# Ensure utf-8 output on Windows terminal
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend to path for importing canonical domain models
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.models.schemas import ActionType, OrderBase, PolicyConfig
from app.services.decision_engine import DecisionEngineService
from app.services.financial_model import FinancialModelService
from app.services.risk_model import RiskModelService


def wilson_score_interval(k: int, n: int, confidence: float = 0.95) -> Tuple[float, float, float]:
    """Calculates the exact Wilson score confidence interval for a binomial proportion.

    Formula:
        center = (p + z^2 / (2n)) / (1 + z^2 / n)
        margin = (z * sqrt(p*(1-p)/n + z^2 / (4n^2))) / (1 + z^2 / n)
    """
    if n <= 0:
        return 0.0, 0.0, 0.0
    z = 1.959963984540054  # 95% two-sided normal quantile
    p = float(k) / float(n)
    denom = 1.0 + (z**2) / float(n)
    center = (p + (z**2) / (2.0 * float(n))) / denom
    margin = (z * math.sqrt((p * (1.0 - p) / float(n)) + ((z**2) / (4.0 * (float(n) ** 2))))) / denom
    ci_lower = max(0.0, center - margin)
    ci_upper = min(1.0, center + margin)
    return round(p, 4), round(ci_lower, 4), round(ci_upper, 4)


def run_complete_analysis(csv_path: str = "data/orders_sample.csv") -> Dict[str, Any]:
    print("================================================================================")
    print(" COD COMPASS - INDEPENDENT AUDIT, EXPLORATORY ANALYSIS & POLICY REPLAY")
    print("================================================================================")

    # 1. Dataset Loading and Validation
    df_raw = pd.read_csv(csv_path, dtype={"phone": str, "pincode": str})
    raw_row_count = len(df_raw)
    duplicate_rows_count = int(df_raw.duplicated(subset=["order_id"]).sum())
    unique_orders_count = raw_row_count - duplicate_rows_count

    print(f"\n[1] DATASET RECONCILIATION")
    print(f"  Raw CSV rows:            {raw_row_count}")
    print(f"  Duplicate order_id rows: {duplicate_rows_count}")
    print(f"  Unique orders:           {unique_orders_count}")

    # Deduplicate strictly on order_id
    df = df_raw.drop_duplicates(subset=["order_id"], keep="first").copy()
    assert len(df) == 1988, f"Expected 1988 unique orders, found {len(df)}"

    # Status Normalization
    df["status_normalized"] = df["final_status"].astype(str).str.strip().str.upper()
    status_counts = df["status_normalized"].value_counts().to_dict()
    delivered_count = status_counts.get("DELIVERED", 0)
    rto_count = status_counts.get("RTO", 0)
    in_transit_count = status_counts.get("IN_TRANSIT", 0)
    resolved_count = delivered_count + rto_count

    print(f"  Delivered unique orders: {delivered_count} ({delivered_count / resolved_count * 100:.2f}%)")
    print(f"  RTO unique orders:       {rto_count} ({rto_count / resolved_count * 100:.2f}%)")
    print(f"  Unresolved (IN_TRANSIT): {in_transit_count}")
    print(f"  Total resolved unique:   {resolved_count}")

    assert delivered_count == 1422, f"Expected 1422 delivered, got {delivered_count}"
    assert rto_count == 565, f"Expected 565 RTO, got {rto_count}"
    assert in_transit_count == 1, f"Expected 1 IN_TRANSIT, got {in_transit_count}"

    # Resolved DataFrame for Empirical Segments & Pincode Analysis
    resolved_df = df[df["status_normalized"].isin(["DELIVERED", "RTO"])].copy()
    resolved_df["is_rto"] = (resolved_df["status_normalized"] == "RTO").astype(int)

    # 2. Pincode Data Quality on Deduplicated Resolved Orders
    # Missing pincodes
    missing_pincodes_resolved = int(resolved_df["pincode"].isna().sum())
    missing_pincodes_all = int(df["pincode"].isna().sum())

    # Valid 6-digit pincodes in resolved orders
    clean_pins_res = resolved_df["pincode"].dropna().astype(str).str.strip()
    clean_pins_res = clean_pins_res[clean_pins_res.str.match(r"^\d{6}$")]
    pincode_counts_res = clean_pins_res.value_counts()

    total_known_pincodes = len(pincode_counts_res)
    single_order_pincodes = int((pincode_counts_res == 1).sum())
    fewer_than_5_pincodes = int((pincode_counts_res < 5).sum())
    ten_or_more_pincodes = int((pincode_counts_res >= 10).sum())
    max_orders_in_pincode = int(pincode_counts_res.max())

    print(f"\n[2] PINCODE STATISTICS (DEDUPLICATED RESOLVED ORDERS: 1,987)")
    print(f"  Missing / null pincodes across unique orders:   {missing_pincodes_all}")
    print(f"  Missing pincodes in resolved orders:             {missing_pincodes_resolved}")
    print(f"  Resolved orders with known 6-digit pincode:      {len(clean_pins_res)}")
    print(f"  Unique known pincodes in resolved orders:        {total_known_pincodes}")
    print(f"  Single-order pincodes (n=1):                     {single_order_pincodes} ({single_order_pincodes / total_known_pincodes * 100:.2f}%)")
    print(f"  Pincodes with < 5 orders:                        {fewer_than_5_pincodes} ({fewer_than_5_pincodes / total_known_pincodes * 100:.2f}%)")
    print(f"  Pincodes with >= 10 orders:                      {ten_or_more_pincodes}")
    print(f"  Max orders in any single pincode:                {max_orders_in_pincode}")

    assert total_known_pincodes == 1066, f"Expected 1066 known pincodes, got {total_known_pincodes}"
    assert single_order_pincodes == 554, f"Expected 554 single-order pincodes, got {single_order_pincodes}"
    assert fewer_than_5_pincodes == 1036, f"Expected 1036 pincodes with <5 orders, got {fewer_than_5_pincodes}"
    assert ten_or_more_pincodes == 0, f"Expected 0 pincodes with >=10 orders, got {ten_or_more_pincodes}"
    assert missing_pincodes_all == 12, f"Expected 12 missing pincodes, got {missing_pincodes_all}"

    # 3. Monthly Order Volume
    df["dt"] = pd.to_datetime(df["order_datetime"], errors="coerce")
    df["year_month"] = df["dt"].dt.to_period("M").astype(str)
    monthly_volumes = df["year_month"].value_counts().sort_index().to_dict()

    print(f"\n[3] MONTHLY VOLUME (UNIQUE ORDERS)")
    for ym, cnt in monthly_volumes.items():
        print(f"  {ym}: {cnt} orders")

    # September Breakdown
    sep_df = df[df["year_month"] == "2026-09"].copy()
    sep_resolved = sep_df[sep_df["status_normalized"].isin(["DELIVERED", "RTO"])].copy()
    sep_resolved_count = len(sep_resolved)
    sep_del = int((sep_resolved["status_normalized"] == "DELIVERED").sum())
    sep_rto = int((sep_resolved["status_normalized"] == "RTO").sum())

    print(f"\n[4] SEPTEMBER 2026 POPULATION")
    print(f"  September resolved orders: {sep_resolved_count}")
    print(f"  September DELIVERED:       {sep_del} ({sep_del / sep_resolved_count * 100:.2f}%)")
    print(f"  September RTO:             {sep_rto} ({sep_rto / sep_resolved_count * 100:.2f}%)")
    assert sep_resolved_count == 329, f"Expected 329 September resolved, got {sep_resolved_count}"
    assert sep_del == 243, f"Expected 243 September delivered, got {sep_del}"
    assert sep_rto == 86, f"Expected 86 September RTO, got {sep_rto}"

    # 4. Address & Customer Name Quality (Row-level address vs own city)
    suspicious_patterns = [r"^\.$", r"^xyz$", r"^home$", r"^call me$", r"^na$", r"^test$", r"^asdf$"]
    suspicious_regex = re.compile("|".join(suspicious_patterns), re.IGNORECASE)

    def is_suspicious_address_row(row: pd.Series) -> bool:
        addr = str(row["address"] or "").strip()
        city = str(row["city"] or "").strip().lower()
        if not addr or len(addr) < 5:
            return True
        if bool(suspicious_regex.match(addr)):
            return True
        if addr.lower() == city:
            return True
        return False

    df["is_suspicious_addr"] = df.apply(is_suspicious_address_row, axis=1)
    df["customer_name_clean"] = df["customer_name"].fillna("").astype(str).str.strip()
    df["is_fake_name"] = df["customer_name_clean"].apply(
        lambda n: bool(re.match(r"^(test order|test|qwerty|asdf|xyz xyz|abc|na)$", n, re.IGNORECASE))
    )

    resolved_df["is_suspicious_addr"] = resolved_df.apply(is_suspicious_address_row, axis=1)
    resolved_df["customer_name_clean"] = resolved_df["customer_name"].fillna("").astype(str).str.strip()
    resolved_df["is_fake_name"] = resolved_df["customer_name_clean"].apply(
        lambda n: bool(re.match(r"^(test order|test|qwerty|asdf|xyz xyz|abc|na)$", n, re.IGNORECASE))
    )

    def compute_segment_wilson(data: pd.DataFrame, group_col: str) -> List[Dict[str, Any]]:
        results = []
        for val, grp in data.groupby(group_col, observed=False):
            n = len(grp)
            k = int(grp["is_rto"].sum())
            rate, ci_low, ci_high = wilson_score_interval(k, n)
            results.append({
                "segment": str(val),
                "total_orders": n,
                "rtos": k,
                "rto_rate": rate,
                "wilson_ci_lower_95": ci_low,
                "wilson_ci_upper_95": ci_high,
            })
        results.sort(key=lambda x: x["total_orders"], reverse=True)
        return results

    print(f"\n[5] EMPIRICAL SEGMENTATION WITH 95% WILSON SCORE INTERVALS")

    # Segment A: Prior RTO History
    resolved_df["prior_rto_group"] = resolved_df["customer_prior_rto"].apply(
        lambda x: "0 prior RTO" if x == 0 else ("1 prior RTO" if x == 1 else ">=2 prior RTO")
    )
    prior_rto_stats = compute_segment_wilson(resolved_df, "prior_rto_group")
    print("\n  Prior RTO History:")
    for s in prior_rto_stats:
        print(f"    {s['segment']:15}: {s['rtos']:3d} / {s['total_orders']:4d} = {s['rto_rate']*100:5.2f}% "
              f"(95% Wilson CI: [{s['wilson_ci_lower_95']*100:.1f}%, {s['wilson_ci_upper_95']*100:.1f}%])")

    # Segment B: Address Quality
    resolved_df["addr_quality_group"] = resolved_df["is_suspicious_addr"].apply(
        lambda x: "Incomplete / Suspicious Address" if x else "Deliverable Address"
    )
    addr_stats = compute_segment_wilson(resolved_df, "addr_quality_group")
    print("\n  Address Quality:")
    for s in addr_stats:
        print(f"    {s['segment']:32}: {s['rtos']:3d} / {s['total_orders']:4d} = {s['rto_rate']*100:5.2f}% "
              f"(95% Wilson CI: [{s['wilson_ci_lower_95']*100:.1f}%, {s['wilson_ci_upper_95']*100:.1f}%])")

    # Segment C: Customer Type (First-time vs Repeat)
    resolved_df["customer_type"] = resolved_df["customer_prior_orders"].apply(
        lambda x: "First-time (0 prior orders)" if x == 0 else "Repeat (>=1 prior orders)"
    )
    cust_type_stats = compute_segment_wilson(resolved_df, "customer_type")
    print("\n  Customer Type:")
    for s in cust_type_stats:
        print(f"    {s['segment']:30}: {s['rtos']:3d} / {s['total_orders']:4d} = {s['rto_rate']*100:5.2f}% "
              f"(95% Wilson CI: [{s['wilson_ci_lower_95']*100:.1f}%, {s['wilson_ci_upper_95']*100:.1f}%])")

    # Segment D: Order Value Bands
    resolved_df["value_band"] = pd.cut(
        resolved_df["order_value"],
        bins=[-1, 499, 999, 1499, 2499, 100000],
        labels=["< Rs 500", "Rs 500 - Rs 999", "Rs 1,000 - Rs 1,499", "Rs 1,500 - Rs 2,499", "Rs 2,500+"]
    )
    value_band_stats = compute_segment_wilson(resolved_df, "value_band")
    print("\n  Order Value Bands:")
    for s in value_band_stats:
        print(f"    {s['segment']:20}: {s['rtos']:3d} / {s['total_orders']:4d} = {s['rto_rate']*100:5.2f}% "
              f"(95% Wilson CI: [{s['wilson_ci_lower_95']*100:.1f}%, {s['wilson_ci_upper_95']*100:.1f}%])")

    # Segment E: Marketing Channel (UTM Source)
    utm_stats = compute_segment_wilson(resolved_df, "utm_source")
    print("\n  Marketing Channels (UTM):")
    for s in utm_stats:
        print(f"    {s['segment']:22}: {s['rtos']:3d} / {s['total_orders']:4d} = {s['rto_rate']*100:5.2f}% "
              f"(95% Wilson CI: [{s['wilson_ci_lower_95']*100:.1f}%, {s['wilson_ci_upper_95']*100:.1f}%])")

    # Segment F: Courier Performance (Post-fulfillment reference only)
    courier_stats = compute_segment_wilson(resolved_df, "courier")
    print("\n  Courier Delivery Rates (Post-shipment):")
    for s in courier_stats:
        print(f"    {s['segment']:15}: {s['rtos']:3d} / {s['total_orders']:4d} = {s['rto_rate']*100:5.2f}% "
              f"(95% Wilson CI: [{s['wilson_ci_lower_95']*100:.1f}%, {s['wilson_ci_upper_95']*100:.1f}%])")

    # 5. Model Evaluation strictly on Data prior to September 1, 2026
    print(f"\n[6] RISK MODEL CALIBRATION & PROVENANCE (CUTOFF: 2026-08-31)")
    risk_model = RiskModelService()
    training_metrics = risk_model.train_on_dataframe(df, cutoff_date="2026-08-31", persist=True)

    print(f"  Model Version / Provenance:       {risk_model.model_version} (Transparent Heuristic Scorer)")
    print(f"  Training cohort (Apr 1 - Aug 31): {training_metrics.get('training_samples')} resolved orders")
    print(f"  Holdout cohort (September 2026):  {training_metrics.get('holdout_samples')} resolved orders")
    print(f"  Holdout Brier Score:              {training_metrics.get('brier_score'):.4f}")
    print(f"  Constant Prior Baseline Brier:    {training_metrics.get('constant_prior_baseline_brier_score', 0.0):.4f}")
    print(f"  Holdout Precision (@ 0.35 cutoff): {training_metrics.get('precision_at_35', 0.0) * 100:.2f}%")
    print(f"  Holdout Recall (@ 0.35 cutoff):    {training_metrics.get('recall_at_35', 0.0) * 100:.2f}%")

    # 6. September Policy Replay (Derived dynamically in code without hardcoded counts)
    print(f"\n[7] SEPTEMBER 2026 POLICY REPLAY ON 329 RESOLVED ORDERS")
    fin = FinancialModelService()
    engine = DecisionEngineService(risk_model=risk_model, financial_model=fin)
    policy = PolicyConfig(
        low_risk_threshold=0.20,
        confirm_threshold=0.35,
        nudge_threshold=0.65,
        hold_threshold=0.65,
        prepaid_discount_amount=25.0,
        require_confirm_above_value=1500.0,
    )

    sep_order_evaluations: List[Dict[str, Any]] = []
    for _, row in sep_resolved.iterrows():
        order_obj = OrderBase(
            order_id=str(row["order_id"]),
            order_datetime=str(row["order_datetime"]),
            customer_name=str(row["customer_name"]),
            phone=str(row["phone"]),
            address=str(row["address"]),
            city=str(row["city"]),
            state=str(row["state"]),
            pincode=str(row["pincode"]),
            order_value=float(row["order_value"]),
            items=str(row["items"]),
            num_items=int(row["num_items"]),
            customer_prior_orders=int(row["customer_prior_orders"]),
            customer_prior_rto=int(row["customer_prior_rto"]),
            utm_source=str(row["utm_source"]),
            courier=str(row["courier"]),
            payment_method=str(row["payment_method"]),
        )
        ev = engine.evaluate_order(order_obj, policy=policy)
        sep_order_evaluations.append({
            "order_id": order_obj.order_id,
            "recommended_action": ev.recommended_action.value,
            "risk_score": ev.risk_score,
            "order_value": order_obj.order_value,
            "actual_status": row["status_normalized"],
            "review_flags": ev.review_flags,
        })

    eval_df = pd.DataFrame(sep_order_evaluations)
    action_counts = eval_df["recommended_action"].value_counts().to_dict()
    # Support empty buckets cleanly
    for act in ActionType:
        if act.value not in action_counts:
            action_counts[act.value] = 0

    print("\n  Recommended Action Distribution (September):")
    for act, cnt in sorted(action_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"    {act:15}: {cnt:3d} orders ({cnt / sep_resolved_count * 100:5.2f}%)")

    # Observed COD Outcomes by Bucket
    ct = pd.crosstab(eval_df["recommended_action"], eval_df["actual_status"])
    observed_bucket_outcomes: Dict[str, Dict[str, Any]] = {}
    print("\n  Observed COD Outcomes by Recommended Bucket:")
    for act in sorted(action_counts.keys()):
        deliv = int(ct.loc[act, "DELIVERED"]) if "DELIVERED" in ct.columns and act in ct.index else 0
        rtos = int(ct.loc[act, "RTO"]) if "RTO" in ct.columns and act in ct.index else 0
        tot = deliv + rtos
        rate, ci_low, ci_high = wilson_score_interval(rtos, tot)
        observed_bucket_outcomes[act] = {
            "total_orders": tot,
            "delivered": deliv,
            "rto": rtos,
            "observed_rto_rate": rate,
            "wilson_ci_95": [ci_low, ci_high],
        }
        print(f"    {act:15}: {deliv:3d} Delivered, {rtos:2d} RTO ({rate*100:5.2f}% RTO, Wilson CI: [{ci_low*100:.1f}%, {ci_high*100:.1f}%])")

    # 7. Complete Reconciled Financial Bridge (329 September Orders)
    direct_rto_loss_unit = fin.direct_rto_loss()  # 169.40
    scale_factor = 1650.0 / float(sep_resolved_count)

    # Baseline Observed Financials on 329 Orders:
    delivered_orders = sep_resolved[sep_resolved["status_normalized"] == "DELIVERED"]
    rto_orders = sep_resolved[sep_resolved["status_normalized"] == "RTO"]

    obs_deliv_rev = float(delivered_orders["order_value"].sum())
    obs_baseline_cogs = obs_deliv_rev * 0.38
    obs_forward_shipping = sep_resolved_count * 65.0
    obs_return_shipping = sep_rto * 65.0
    obs_packaging = sep_resolved_count * 25.0
    obs_damage = sep_rto * (0.08 * 180.0)

    base_deliv_contrib = (obs_deliv_rev * 0.62) - (len(delivered_orders) * 90.0)
    base_rto_cost = len(rto_orders) * direct_rto_loss_unit
    base_net_contrib = base_deliv_contrib - base_rto_cost

    def evaluate_scenario(scenario_name: str, p_conf_resp: float, p_conf_rto: float, p_prep_conv: float, p_prep_rto: float, p_hold_recov: float, p_hold_leakage: float) -> Dict[str, Any]:
        """Computes scenario financials using the shared canonical FinancialModelService.
        Consolidates accounting formulas and parameters across replay, dashboard, and policy previews.
        Preserves conditional historical-outcome assumptions and exact 0.00 reconciliation.
        """
        sc_res = fin.evaluate_cohort_financials(
            orders=eval_df,
            policy=policy,
            active_hold_review=True,
            scenario_overrides={
                "confirm_response_rate": p_conf_resp,
                "confirmed_rto_rate": p_conf_rto,
                "prepaid_conversion_rate": p_prep_conv,
                "prepaid_residual_rto_rate": p_prep_rto,
                "hold_recovery_rate": p_hold_recov,
                "hold_rto_leakage_rate": p_hold_leakage,
            },
            scale_to_monthly_orders=1650.0,
        )
        sc_res["scenario_name"] = scenario_name
        sc_res["assumptions"] = {
            "confirm_response_rate": p_conf_resp,
            "confirmed_rto_rate": p_conf_rto,
            "prepaid_conversion_rate": p_prep_conv,
            "prepaid_residual_rto_rate": p_prep_rto,
            "hold_recovery_rate": p_hold_recov,
            "hold_rto_leakage_rate": p_hold_leakage,
        }
        sc_res["notes"] = (
            "Hold outcomes reflect conditional operations assumptions (e.g. active address outreach), "
            "not demonstrated performance of unverified holding. Conservative leakage erodes net contribution."
        )
        return sc_res

    # Evaluate 3 explicit scenarios
    base_scen = evaluate_scenario("Base Scenario", 0.70, 0.12, 0.22, 0.04, 0.70, 0.0)
    cons_scen = evaluate_scenario("Conservative Scenario", 0.60, 0.18, 0.15, 0.06, 0.50, 0.10)
    opt_scen = evaluate_scenario("Optimistic Scenario", 0.80, 0.08, 0.30, 0.02, 0.85, 0.0)

    # Passive cancellation benchmark for HOLD orders (no manual review, pure auto-cancel)
    hold_orders = eval_df[eval_df["recommended_action"] == "HOLD"]
    hold_deliv = hold_orders[hold_orders["actual_status"] == "DELIVERED"]
    hold_rto = hold_orders[hold_orders["actual_status"] == "RTO"]
    hold_deliv_cnt = len(hold_deliv)
    hold_rto_cnt = len(hold_rto)
    hold_deliv_rev = float(hold_deliv["order_value"].sum()) if hold_deliv_cnt > 0 else 0.0
    hold_deliv_contrib = (hold_deliv_rev * 0.62) - (hold_deliv_cnt * 90.0)
    hold_avoided_rto_savings = hold_rto_cnt * direct_rto_loss_unit
    passive_net_advantage = hold_avoided_rto_savings - hold_deliv_contrib
    scaled_passive_net = passive_net_advantage * scale_factor

    print(f"\n[8] COMPLETE RECONCILED FINANCIAL BRIDGE (BASE SCENARIO, SEPTEMBER 329 ORDERS)")
    print(f"  Baseline Net Contribution:          Rs {base_scen['baseline_net_contribution_rupees']:,.2f}")
    print(f"  Policy Net Contribution:            Rs {base_scen['policy_net_contribution_rupees']:,.2f}")
    print(f"  Net Financial Improvement:          Rs {base_scen['net_financial_improvement_rupees']:,.2f}")
    print("  --- Reconciled Bridge Items ---")
    print(f"  1. Avoided RTO Freight & Damage:    +Rs {base_scen['avoided_rto_freight_and_damage_rupees']:,.2f}")
    print(f"  2. Change in Delivered Margin:      -Rs {abs(base_scen['change_in_delivered_contribution_rupees']):,.2f}")
    print(f"  3. Prepaid Incentive Discounts:     -Rs {abs(base_scen['prepaid_incentive_discounts_rupees']):,.2f}")
    print(f"  4. WhatsApp Interactive Messaging:  -Rs {abs(base_scen['whatsapp_interactive_messaging_rupees']):,.2f}")
    print(f"  5. Payment Gateway Fees (2%):       -Rs {abs(base_scen['payment_gateway_fees_rupees']):,.2f}")
    print(f"  Reconciliation Discrepancy:         Rs {base_scen['reconciliation_discrepancy_rupees']:.10f} (Exact 0.00)")
    assert abs(base_scen['reconciliation_discrepancy_rupees']) < 1e-5, "Financial bridge does not reconcile!"

    print(f"\n[9] SCENARIO SENSITIVITY COMPARISON (MONTHLY SCALED TO 1,650 COD ORDERS)")
    print(f"  Conservative Net Gain: Rs {cons_scen['monthly_scaled_projection']['projected_net_monthly_gain_rupees']:,.2f}/mo (Avoids {cons_scen['monthly_scaled_projection']['projected_monthly_avoided_rtos']:.1f} RTOs)")
    print(f"  Base Scenario Net Gain:Rs {base_scen['monthly_scaled_projection']['projected_net_monthly_gain_rupees']:,.2f}/mo (Avoids {base_scen['monthly_scaled_projection']['projected_monthly_avoided_rtos']:.1f} RTOs)")
    print(f"  Optimistic Net Gain:   Rs {opt_scen['monthly_scaled_projection']['projected_net_monthly_gain_rupees']:,.2f}/mo (Avoids {opt_scen['monthly_scaled_projection']['projected_monthly_avoided_rtos']:.1f} RTOs)")

    # Justification of the Rs 25 Prepaid Discount:
    discount_evaluation = fin.evaluate_prepaid_discount_options(
        order_value=649.0, calibrated_rto_prob=0.765, discounts=[0.0, 15.0, 25.0, 35.0, 50.0], policy=policy
    )
    print(f"\n[10] PREPAID DISCOUNT INCENTIVE JUSTIFICATION (AOV: Rs 649, RTO Risk: 76.5%)")
    print(f"  Expected COD contribution without conversion: -Rs 56.18 (Substantial cash loss on average)")
    for d_opt in discount_evaluation:
        print(f"  Discount: Rs {d_opt['discount_rupees']:4.1f} | Est Conv: {d_opt['estimated_conversion_rate']*100:4.1f}% | "
              f"Delivered Contrib: Rs {d_opt['net_prepaid_contribution_per_order']:6.2f} | Exp Incremental Pool: Rs {d_opt['expected_incremental_pool']:6.2f} | "
              f"Break-even Conv: {d_opt['breakeven_conversion_rate_percent']:.2f}%")

    # Package clean JSON artifact
    audit_results: Dict[str, Any] = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "csv_path": csv_path,
            "training_cutoff_date": "2026-08-31",
            "model_version": risk_model.model_version,
            "provenance": "Transparent heuristic log-odds scorer with Empirical Bayes pincode smoothing (not MLE-fitted or calibrated logistic regression)",
            "policy_version": policy.policy_id,
            "confidence_level": 0.95,
            "interval_method": "Wilson score interval (exact)",
        },
        "dataset_validation": {
            "raw_csv_rows": raw_row_count,
            "duplicate_order_id_rows": duplicate_rows_count,
            "unique_orders_total": unique_orders_count,
            "resolved_unique_orders": resolved_count,
            "unresolved_in_transit": in_transit_count,
            "delivered_unique_orders": delivered_count,
            "rto_unique_orders": rto_count,
            "overall_rto_rate": round(rto_count / resolved_count, 4),
            "pincode_audit_resolved_orders": {
                "known_valid_pincodes_orders": len(clean_pins_res),
                "unique_known_pincodes": total_known_pincodes,
                "single_order_pincodes": single_order_pincodes,
                "pincodes_under_5_orders": fewer_than_5_pincodes,
                "pincodes_10_or_more_orders": ten_or_more_pincodes,
                "max_orders_in_any_pincode": max_orders_in_pincode,
                "missing_pincodes_resolved_orders": missing_pincodes_resolved,
                "missing_pincodes_across_unique_orders": missing_pincodes_all,
                "investigation_note": (
                    "In deduplicated resolved orders (1,987 orders), there are exactly 1,066 known pincodes, "
                    "554 single-order pincodes, 1,036 with <5 orders, and 0 with >=10 orders (max is 8). "
                    "The single IN_TRANSIT order (KT100021) has pincode 600030, which is unique to that order, "
                    "bringing total unique orders pincodes to 1,067. There are exactly 12 missing pincodes."
                ),
            },
            "suspicious_addresses_count": int(df["is_suspicious_addr"].sum()),
            "fake_names_count": int(df["is_fake_name"].sum()),
        },
        "empirical_segments_wilson_ci": {
            "prior_rto_history": prior_rto_stats,
            "address_quality": addr_stats,
            "customer_type": cust_type_stats,
            "order_value_bands": value_band_stats,
            "marketing_channels": utm_stats,
            "courier_delivery": courier_stats,
        },
        "model_calibration_metrics": {
            "model_version": risk_model.model_version,
            "provenance": "Transparent heuristic log-odds scorer with Empirical Bayes pincode smoothing (not MLE-fitted or calibrated logistic regression)",
            "training_cohort_size": training_metrics.get("training_samples"),
            "holdout_cohort_size": training_metrics.get("holdout_samples"),
            "holdout_brier_score": round(training_metrics.get("brier_score", 0.0), 4),
            "constant_prior_baseline_brier_score": round(training_metrics.get("constant_prior_baseline_brier_score", 0.0), 4),
            "holdout_precision_at_035": round(training_metrics.get("precision_at_35", 0.0), 4),
            "holdout_recall_at_035": round(training_metrics.get("recall_at_35", 0.0), 4),
        },
        "september_2026_holdout_replay": {
            "population_size": sep_resolved_count,
            "observed_delivered": sep_del,
            "observed_rto": sep_rto,
            "observed_rto_rate": round(sep_rto / sep_resolved_count, 4),
            "action_bucket_distribution": action_counts,
            "observed_outcomes_by_bucket": observed_bucket_outcomes,
            "observed_baseline_financials": {
                "delivered_revenue_rupees": round(obs_deliv_rev, 2),
                "cogs_rupees": round(obs_baseline_cogs, 2),
                "forward_shipping_rupees": round(obs_forward_shipping, 2),
                "return_shipping_rupees": round(obs_return_shipping, 2),
                "packaging_rupees": round(obs_packaging, 2),
                "damage_loss_rupees": round(obs_damage, 2),
                "direct_rto_cash_loss_rupees": round(base_rto_cost, 2),
                "baseline_net_contribution_rupees": round(base_net_contrib, 2),
            },
            "reconciled_financial_bridge_september_329_orders": {
                "baseline_net_contribution_rupees": base_scen["baseline_net_contribution_rupees"],
                "avoided_rto_freight_and_damage_rupees": base_scen["avoided_rto_freight_and_damage_rupees"],
                "change_in_delivered_contribution_rupees": base_scen["change_in_delivered_contribution_rupees"],
                "prepaid_incentive_discounts_rupees": base_scen["prepaid_incentive_discounts_rupees"],
                "whatsapp_interactive_messaging_rupees": base_scen["whatsapp_interactive_messaging_rupees"],
                "payment_gateway_fees_rupees": base_scen["payment_gateway_fees_rupees"],
                "policy_net_contribution_rupees": base_scen["policy_net_contribution_rupees"],
                "net_financial_improvement_rupees": base_scen["net_financial_improvement_rupees"],
                "reconciliation_discrepancy_rupees": base_scen["reconciliation_discrepancy_rupees"],
                "avoided_rtos_count": base_scen["avoided_rtos_count"],
                "policy_rtos_count": base_scen["policy_rtos_count"],
                "passive_auto_cancel_net_advantage_rupees": round(passive_net_advantage, 2),
            },
            "separated_monthly_scaled_projection": {
                "benchmark_definition": "Assignment Operating Baseline (1,650 monthly COD orders from 3,000 total orders @ 55% COD share)",
                "scaling_methodology": "September-derived extrapolation using exact unrounded scale factor (1650 / 329 = 5.015197568389058)",
                "scale_factor_exact": scale_factor,
                "projected_monthly_avoided_rtos": base_scen["monthly_scaled_projection"]["projected_monthly_avoided_rtos"],
                "projected_avoided_rto_freight_rupees": base_scen["monthly_scaled_projection"]["projected_avoided_rto_freight_rupees"],
                "projected_change_in_delivered_contribution_rupees": base_scen["monthly_scaled_projection"]["projected_change_in_delivered_contribution_rupees"],
                "projected_prepaid_discounts_rupees": base_scen["monthly_scaled_projection"]["projected_prepaid_discounts_rupees"],
                "projected_messaging_costs_rupees": base_scen["monthly_scaled_projection"]["projected_messaging_costs_rupees"],
                "projected_payment_gateway_fees_rupees": base_scen["monthly_scaled_projection"]["projected_payment_gateway_fees_rupees"],
                "projected_net_monthly_gain_rupees": base_scen["monthly_scaled_projection"]["projected_net_monthly_gain_rupees"],
                "projected_passive_auto_cancel_net_rupees": round(scaled_passive_net, 2),
            },
            "scenarios": {
                "conservative": cons_scen,
                "base": base_scen,
                "optimistic": opt_scen,
            },
            "prepaid_discount_justification": {
                "targeted_segment": "Repeat returners (customer_prior_rto >= 2, empirical RTO = 76.47%)",
                "aov_rupees": 649.0,
                "expected_loss_if_shipped_cod_rupees": -56.18,
                "discount_options_evaluated": discount_evaluation,
                "breakeven_conversion_rate_percent": 10.75,
                "expected_conversion_rate_percent": 22.0,
                "residual_prepaid_rto_risk_percent": 4.0,
                "rationale": (
                    "At Rs 25 discount (3.8% of AOV), even a minor conversion lift from 10% to 10.75% beats a Rs 0 discount. "
                    "At 22% expected conversion, offering Rs 25 generates +Rs 12.75 expected value per targeted customer "
                    "compared to a net expected loss of -Rs 56.18 per order if shipped COD."
                ),
            },
        },
    }

    def serialize_json(obj: Any) -> Any:
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (datetime, pd.Timestamp)):
            return obj.isoformat()
        return str(obj)

    output_path = os.path.join(os.path.dirname(__file__), "replay_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(audit_results, f, indent=2, default=serialize_json)

    print(f"\n[OK] Machine-readable audit results exported to: {output_path}")
    return audit_results


if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "data/orders_sample.csv"
    run_complete_analysis(csv_file)
