"""Database seeder for COD Compass.

Loads orders from data/orders_sample.csv (if available) or data/demo_orders.csv into SQLite,
normalizes status labels, trains the risk model, and runs the pre-shipment decision engine
so that the dashboard and orders table are immediately fully populated.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime

# Add backend directory to sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import pandas as pd
from app.db.database import get_active_policy, get_db_connection, init_db
from app.models.schemas import ActionType, OperationalStatus, OrderBase, PolicyConfig
from app.services.chat_simulator import ChatSimulatorService
from app.services.decision_engine import DecisionEngineService
from app.services.financial_model import FinancialModelService
from app.services.llm_adapter import LLMAdapterService
from app.services.risk_model import RiskModelService


def seed_database(force_reseed: bool = False) -> None:
    init_db()

    # Determine data source
    orders_sample_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "orders_sample.csv"))
    demo_orders_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "demo_orders.csv"))

    source_arg = None
    for i, arg in enumerate(sys.argv):
        if arg == "--source" and i + 1 < len(sys.argv):
            source_arg = sys.argv[i + 1]
        elif arg == "--demo":
            source_arg = demo_orders_path

    if source_arg and os.path.exists(source_arg):
        source_path = os.path.abspath(source_arg)
        print(f"Loading specified dataset from {source_path}...")
    elif os.environ.get("DATA_SOURCE_PATH") and os.path.exists(os.environ["DATA_SOURCE_PATH"]):
        source_path = os.path.abspath(os.environ["DATA_SOURCE_PATH"])
        print(f"Loading dataset from DATA_SOURCE_PATH: {source_path}...")
    elif os.path.exists(orders_sample_path):
        source_path = orders_sample_path
        print(f"Loading private research dataset from {source_path}...")
    elif os.path.exists(demo_orders_path):
        source_path = demo_orders_path
        print(f"Loading synthetic demo dataset from {source_path}...")
    else:
        raise FileNotFoundError("Neither data/orders_sample.csv nor data/demo_orders.csv found!")

    df = pd.read_csv(source_path)
    print(f"Read {len(df)} rows from CSV.")

    # Deduplicate exact duplicate orders
    df_dedup = df.drop_duplicates(subset=["order_id"]).copy()
    print(f"Unique orders after deduplication: {len(df_dedup)}")

    # Initialize services
    risk_model = RiskModelService()
    fin_model = FinancialModelService()
    llm_adapter = LLMAdapterService()
    engine = DecisionEngineService(risk_model=risk_model, financial_model=fin_model, llm_adapter=llm_adapter)
    chat_sim = ChatSimulatorService(llm_adapter=llm_adapter)

    # Train risk model strictly on data <= 2026-08-31
    print("Fitting pre-shipment risk model with empirical Bayes pincode smoothing...")
    metrics = risk_model.train_on_dataframe(df_dedup, cutoff_date="2026-08-31")
    print(f"Model fitted! Holdout metrics on September 2026: Brier={metrics['brier_score']}, Precision={metrics['precision_at_35']}, Recall={metrics['recall_at_35']}")

    active_pol_dict = get_active_policy()
    policy = PolicyConfig(**active_pol_dict)

    with get_db_connection() as conn:
        cursor = conn.cursor()

        if force_reseed:
            print("Purging existing database tables...")
            cursor.execute("DELETE FROM conversations;")
            cursor.execute("DELETE FROM simulations;")
            cursor.execute("DELETE FROM decisions;")
            cursor.execute("DELETE FROM audit_log;")
            cursor.execute("DELETE FROM orders;")

        cursor.execute("SELECT COUNT(*) as cnt FROM orders;")
        if cursor.fetchone()["cnt"] > 0 and not force_reseed:
            print("Orders already seeded. Skipping reload.")
            return

        print("Inserting orders and running pre-shipment decision engine...")
        now_iso = datetime.utcnow().isoformat()

        inserted_count = 0
        for _, row in df_dedup.iterrows():
            order_id = str(row["order_id"]).strip()
            order_dt_str = str(row["order_datetime"]).strip()
            # Normalize ISO datetime
            try:
                dt_obj = pd.to_datetime(order_dt_str).to_pydatetime()
                order_dt_iso = dt_obj.isoformat()
            except Exception:
                order_dt_iso = order_dt_str

            cust_name = str(row.get("customer_name", "Valued Customer")).strip()
            phone = str(row.get("phone", "")).strip()
            address = str(row.get("address", "")).strip()
            city = str(row.get("city", "")).strip()
            state = str(row.get("state", "")).strip()
            pincode = str(row.get("pincode", "")).strip()
            order_val = float(row.get("order_value", 649.0))
            items = str(row.get("items", "Haircare Product")).strip()
            num_items = int(row.get("num_items", 1))
            prior_orders = int(row.get("customer_prior_orders", 0))
            prior_rto = int(row.get("customer_prior_rto", 0))
            utm = str(row.get("utm_source", "organic")).strip()
            courier = str(row.get("courier", "")).strip() or None
            raw_status = str(row.get("final_status", "")).strip().upper()

            # Set initial operational status based on simulated lifecycle
            op_status = OperationalStatus.NEW.value

            cursor.execute("""
                INSERT INTO orders (
                    order_id, order_datetime, customer_name, phone, address, city, state, pincode,
                    order_value, items, num_items, customer_prior_orders, customer_prior_rto,
                    utm_source, courier, payment_method, final_status, operational_status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                order_id, order_dt_iso, cust_name, phone, address, city, state, pincode,
                order_val, items, num_items, prior_orders, prior_rto,
                utm, courier, "COD", raw_status, op_status,
                now_iso, now_iso
            ))

            # Run Pre-Shipment Decision Engine
            order_base = OrderBase(
                order_id=order_id,
                order_datetime=dt_obj,
                customer_name=cust_name,
                phone=phone,
                address=address,
                city=city,
                state=state,
                pincode=pincode,
                order_value=order_val,
                items=items,
                num_items=num_items,
                customer_prior_orders=prior_orders,
                customer_prior_rto=prior_rto,
                utm_source=utm,
                courier=courier,
                payment_method="COD",
                final_status=raw_status,
                operational_status=OperationalStatus.NEW
            )

            eval_res = engine.evaluate_order(order=order_base, policy=policy)

            econ_json = json.dumps({(k.value if hasattr(k, "value") else str(k)): v.model_dump() for k, v in eval_res.action_economics.items()})
            flags_json = json.dumps(eval_res.review_flags)

            cursor.execute("""
                INSERT INTO decisions (
                    order_id, recommended_action, risk_score, risk_band,
                    explanation, plain_english_ops_note, uncertainty_flag,
                    action_economics_json, policy_version, model_version,
                    is_fallback, review_flags_json, evaluated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                order_id,
                eval_res.recommended_action.value,
                eval_res.risk_score,
                eval_res.risk_band.value,
                eval_res.explanation,
                eval_res.plain_english_ops_note,
                1 if eval_res.uncertainty_flag else 0,
                econ_json,
                eval_res.policy_version,
                eval_res.model_version,
                1 if eval_res.is_fallback else 0,
                flags_json,
                now_iso
            ))

            # For September orders, initiate simulated WhatsApp conversations for realistic demo
            is_september = order_dt_iso.startswith("2026-09")
            if is_september and eval_res.recommended_action in [ActionType.CONFIRM, ActionType.NUDGE_PREPAID]:
                chat_sim.initiate_conversation(
                    order_id=order_id,
                    action=eval_res.recommended_action,
                    customer_name=cust_name,
                    order_value=order_val,
                    discount_amount=policy.prepaid_discount_amount,
                    connection=conn
                )

            inserted_count += 1
            if inserted_count % 500 == 0:
                print(f"Processed and evaluated {inserted_count} orders...")

        print(f"Successfully seeded {inserted_count} orders and pre-shipment decisions!")


if __name__ == "__main__":
    force = "--force" in sys.argv
    seed_database(force_reseed=force)
