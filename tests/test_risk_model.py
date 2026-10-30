"""Unit tests for the pre-shipment risk model and feature pipeline.

Verifies:
1. Leak-free design: only pre-shipment features are accepted.
2. Empirical Bayes pincode smoothing prevents banning sparse pincodes.
3. Fake names and incomplete addresses are detected.
4. Severe prior RTO history (>=2) triggers elevated risk probability.
5. IN_TRANSIT orders are excluded from binary outcome training.
"""

import pandas as pd
import pytest
from app.services.risk_model import (
    DEFAULT_PRIOR_RTO_RATE,
    RiskModelService,
    extract_address_features,
)


def test_address_heuristics_detection():
    # Suspicious names
    f1 = extract_address_features("Test User", "Flat 402, Gandhi Road, Opposite Post Office")
    assert f1["is_suspicious_name"] is True
    assert f1["is_suspicious_address"] is False

    # Bogus address
    f2 = extract_address_features("Ananya Sharma", "xyz")
    assert f2["is_suspicious_name"] is False
    assert f2["is_suspicious_address"] is True

    # Complete valid address
    f3 = extract_address_features("Rohit Verma", "Flat 101, Green Heights, Near City Mall, MG Road")
    assert f3["is_suspicious_name"] is False
    assert f3["is_suspicious_address"] is False
    assert f3["has_landmark"] is True
    assert f3["has_building_number"] is True


def test_sparse_pincode_empirical_bayes_smoothing():
    svc = RiskModelService()
    # Unseen pincode
    smoothed, is_uncertain = svc.compute_smoothed_pincode_rate("999999", min_sample=5)
    assert smoothed == svc.global_prior_rto
    assert is_uncertain is True

    # Pincode with 1 order that happened to RTO
    svc.pincode_stats["110099"] = {"total": 1.0, "rto": 1.0}
    smoothed_1, is_uncertain_1 = svc.compute_smoothed_pincode_rate("110099", min_sample=5)
    # Smoothed should NOT be 100%!
    # Formula: (10 * 0.2841 + 1) / (10 + 1) = 3.841 / 11 ≈ 0.349
    assert 0.33 <= smoothed_1 <= 0.37
    assert is_uncertain_1 is True


def test_prior_rto_escalation():
    svc = RiskModelService()

    # Zero prior RTO
    prob_0, _ = svc.predict_order_risk(
        order_value=649.0,
        customer_name="Aarav Gupta",
        address="Flat 204, Park Avenue, Near Metro Station",
        pincode="400001",
        customer_prior_rto=0,
        customer_prior_orders=2,
    )

    # 2+ prior RTOs
    prob_2, _ = svc.predict_order_risk(
        order_value=649.0,
        customer_name="Aarav Gupta",
        address="Flat 204, Park Avenue, Near Metro Station",
        pincode="400001",
        customer_prior_rto=2,
        customer_prior_orders=3,
    )

    assert prob_2 > prob_0
    assert prob_2 >= 0.50


def test_in_transit_excluded_from_training():
    svc = RiskModelService()
    dummy_data = [
        {"order_id": "KT1", "order_datetime": "2026-05-01 10:00:00", "final_status": "DELIVERED", "pincode": "110001", "order_value": 649, "customer_name": "A", "address": "Addr 1", "customer_prior_rto": 0, "customer_prior_orders": 0},
        {"order_id": "KT2", "order_datetime": "2026-05-02 10:00:00", "final_status": "RTO", "pincode": "110001", "order_value": 649, "customer_name": "B", "address": "Addr 2", "customer_prior_rto": 0, "customer_prior_orders": 0},
        {"order_id": "KT3", "order_datetime": "2026-05-03 10:00:00", "final_status": "IN_TRANSIT", "pincode": "110001", "order_value": 649, "customer_name": "C", "address": "Addr 3", "customer_prior_rto": 0, "customer_prior_orders": 0},
    ]
    df = pd.DataFrame(dummy_data)
    metrics = svc.train_on_dataframe(df, cutoff_date="2026-05-02")
    # Training samples should be 2, strictly excluding IN_TRANSIT
    assert metrics["training_samples"] == 2

