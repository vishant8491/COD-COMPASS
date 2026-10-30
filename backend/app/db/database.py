"""Database connection and schema management for COD Compass.

Uses standard Python sqlite3 with parameterized queries to prevent SQL injection.
Provides clean context manager for connections and automatic schema initialization.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, Tuple

def get_database_path() -> str:
    """Returns the absolute path to the active SQLite database."""
    path = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "cod_compass.db"))
    return os.path.abspath(path)


DATABASE_PATH = get_database_path()


@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """Provides a SQLite connection with row factory enabled."""
    db_path = get_database_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Initializes all required SQLite database tables and default policy."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Orders Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                order_datetime TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                address TEXT NOT NULL,
                city TEXT NOT NULL,
                state TEXT NOT NULL,
                pincode TEXT NOT NULL,
                order_value REAL NOT NULL,
                items TEXT NOT NULL,
                num_items INTEGER NOT NULL DEFAULT 1,
                customer_prior_orders INTEGER NOT NULL DEFAULT 0,
                customer_prior_rto INTEGER NOT NULL DEFAULT 0,
                utm_source TEXT DEFAULT 'unknown',
                courier TEXT,
                payment_method TEXT DEFAULT 'COD',
                final_status TEXT,
                operational_status TEXT DEFAULT 'NEW',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # Pre-shipment Decisions Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                recommended_action TEXT NOT NULL,
                risk_score REAL NOT NULL,
                risk_band TEXT NOT NULL,
                explanation TEXT NOT NULL,
                plain_english_ops_note TEXT,
                uncertainty_flag INTEGER NOT NULL DEFAULT 0,
                action_economics_json TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                model_version TEXT NOT NULL,
                is_fallback INTEGER NOT NULL DEFAULT 0,
                review_flags_json TEXT DEFAULT '[]',
                assumptions_snapshot_json TEXT,
                evaluated_at TEXT NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
            );
        """)

        # Migration: ensure assumptions_snapshot_json column exists
        cursor.execute("PRAGMA table_info(decisions);")
        decision_cols = [row["name"] for row in cursor.fetchall()]
        if "assumptions_snapshot_json" not in decision_cols:
            cursor.execute("ALTER TABLE decisions ADD COLUMN assumptions_snapshot_json TEXT;")

        # Configurable Policy Versions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id TEXT UNIQUE NOT NULL,
                version INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                low_risk_threshold REAL NOT NULL DEFAULT 0.20,
                confirm_threshold REAL NOT NULL DEFAULT 0.35,
                nudge_threshold REAL NOT NULL DEFAULT 0.65,
                hold_threshold REAL NOT NULL DEFAULT 0.65,
                prepaid_discount_amount REAL NOT NULL DEFAULT 25.0,
                auto_cancel_enabled INTEGER NOT NULL DEFAULT 0,
                require_confirm_above_value REAL NOT NULL DEFAULT 1500.0,
                min_pincode_sample INTEGER NOT NULL DEFAULT 5,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
        """)

        # WhatsApp Conversation Message Store
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                direction TEXT NOT NULL,
                content TEXT NOT NULL,
                message_type TEXT NOT NULL DEFAULT 'CHAT',
                quick_replies_json TEXT,
                payment_link TEXT,
                sent_at TEXT NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
            );
        """)

        # WhatsApp & Payment Simulation Lifecycle State
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simulations (
                order_id TEXT PRIMARY KEY,
                step TEXT NOT NULL DEFAULT 'INITIATED',
                payment_status TEXT,
                payment_link TEXT,
                discount_applied REAL DEFAULT 0.0,
                simulated_clock_time TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
            );
        """)

        # Audit Trail
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                old_state TEXT,
                new_state TEXT,
                reason TEXT,
                metadata_json TEXT,
                timestamp TEXT NOT NULL
            );
        """)

        # Payment Transactions Table (Idempotent callback safety and audit tracking)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payment_transactions (
                transaction_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL,
                metadata_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
            );
        """)

        # Create Indices for frequent lookups
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_pincode ON orders(pincode);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_phone ON orders(phone);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(operational_status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_order ON decisions(order_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conv_order ON conversations(order_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_payment_tx_order ON payment_transactions(order_id);")

        # Seed Default Policy if none exists
        cursor.execute("SELECT COUNT(*) as cnt FROM policies;")
        if cursor.fetchone()["cnt"] == 0:
            now_iso = datetime.utcnow().isoformat()
            cursor.execute("""
                INSERT INTO policies (
                    policy_id, version, name, description,
                    low_risk_threshold, confirm_threshold, nudge_threshold, hold_threshold,
                    prepaid_discount_amount, auto_cancel_enabled, require_confirm_above_value,
                    min_pincode_sample, is_active, created_at
                ) VALUES (
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?
                );
            """, (
                "default_v1", 1, "Balanced Margin & Growth Policy",
                "Baseline policy balancing direct RTO reduction against customer acquisition retention.",
                0.20, 0.35, 0.65, 0.65,
                25.0, 0, 1500.0,
                5, 1, now_iso
            ))


def get_active_policy() -> Dict[str, Any]:
    """Retrieves the currently active policy from SQLite."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM policies WHERE is_active = 1 ORDER BY version DESC LIMIT 1;")
        row = cursor.fetchone()
        if not row:
            init_db()
            cursor.execute("SELECT * FROM policies WHERE is_active = 1 ORDER BY version DESC LIMIT 1;")
            row = cursor.fetchone()
        return dict(row)


def save_policy(policy_data: Dict[str, Any]) -> int:
    """Saves a new policy version and deactivates prior policies."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Find next version number
        cursor.execute("SELECT MAX(version) as max_v FROM policies;")
        max_v = cursor.fetchone()["max_v"] or 0
        new_v = max_v + 1
        now_iso = datetime.utcnow().isoformat()

        # Mark all prior inactive
        cursor.execute("UPDATE policies SET is_active = 0;")

        cursor.execute("""
            INSERT INTO policies (
                policy_id, version, name, description,
                low_risk_threshold, confirm_threshold, nudge_threshold, hold_threshold,
                prepaid_discount_amount, auto_cancel_enabled, require_confirm_above_value,
                min_pincode_sample, is_active, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?);
        """, (
            f"policy_v{new_v}", new_v, policy_data.get("name", f"Policy v{new_v}"),
            policy_data.get("description", "Updated operational policy"),
            float(policy_data.get("low_risk_threshold", 0.20)),
            float(policy_data.get("confirm_threshold", 0.35)),
            float(policy_data.get("nudge_threshold", 0.55)),
            float(policy_data.get("hold_threshold", 0.70)),
            float(policy_data.get("prepaid_discount_amount", 25.0)),
            1 if policy_data.get("auto_cancel_enabled", False) else 0,
            float(policy_data.get("require_confirm_above_value", 1500.0)),
            int(policy_data.get("min_pincode_sample", 5)),
            now_iso
        ))
        return cursor.lastrowid

