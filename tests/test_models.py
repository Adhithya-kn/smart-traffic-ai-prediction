"""
tests/test_models.py - Test Suite for Machine Learning Pipeline & Invariants
"""

import pytest
from traffic_system.models.predictor import TrafficPredictor

def test_model_loading_and_prediction():
    predictor = TrafficPredictor()
    predictor.load_artifacts()

    assert predictor.model is not None, "XGBoost model should be loaded"
    assert predictor.preprocessor is not None, "Preprocessor should be loaded"
    assert len(predictor.topology) >= 16, "Topology should contain all registered unique roads"

    # Test sample inference
    features = {
        "city_zone": "Indiranagar",
        "road_id": "RD_BLR_01",
        "intersection_id": "INT_BLR_05",
        "vehicle_count": 31957,
        "average_speed": 40.0,
        "congestion_level": "Low",
        "hour": 17,
        "day_of_week": 3,
        "is_weekend": 0
    }
    pred, prob_dist = predictor.predict_segment(features)
    assert pred in ["Low", "Moderate", "High", "Severe"], f"Invalid prediction: {pred}"
    assert len(prob_dist) == 4, "Probability distribution must cover 4 classes"
    assert abs(sum(prob_dist.values()) - 1.0) < 0.05, "Probabilities must sum to ~1.0"

def test_explainability_and_entropy():
    predictor = TrafficPredictor()
    predictor.load_artifacts()

    features = {
        "city_zone": "Indiranagar",
        "road_id": "RD_BLR_01",
        "intersection_id": "INT_BLR_05",
        "vehicle_count": 31957,
        "average_speed": 40.0,
        "congestion_level": "Low",
        "hour": 17,
        "day_of_week": 3,
        "is_weekend": 0
    }
    res = predictor.predict_segment(features, explain=True)
    assert isinstance(res, dict)
    assert "prediction" in res
    assert "probabilities" in res
    assert "confidence_score" in res
    assert 0.0 <= res["confidence_score"] <= 1.0
    assert "uncertainty_entropy" in res
    assert 0.0 <= res["uncertainty_entropy"] <= 1.0
    assert "top_drivers" in res
    assert len(res["top_drivers"]) <= 3

def test_resilience_missing_and_edge_cases():
    predictor = TrafficPredictor()
    predictor.load_artifacts()

    # 1. Partial dict missing columns (auto-healed from defaults)
    partial_f = {"road_id": "RD_100", "vehicle_count": 200}
    pred, prob_dist = predictor.predict_segment(partial_f)
    assert pred in ["Low", "Moderate", "High", "Severe"]

    # 2. Unphysical negative speed (auto-clamped to valid range)
    neg_speed_f = {"road_id": "RD_100", "average_speed": -25.0}
    pred2, _ = predictor.predict_segment(neg_speed_f)
    assert pred2 in ["Low", "Moderate", "High", "Severe"]

    # 3. Empty dictionary (auto-healed)
    empty_f = {}
    pred3, _ = predictor.predict_segment(empty_f)
    assert pred3 in ["Low", "Moderate", "High", "Severe"]
