"""
tests/test_prediction_pipeline.py - Verification of XGBoost Training, Chronological Split & Metrics
"""

import json
from traffic_system.config import TRAINING_METRICS_FILE, ARTIFACTS_DIR
from traffic_system.models.predictor import TrafficPredictor


def test_prediction_artifacts_and_metrics_integrity():
    predictor = TrafficPredictor()
    predictor.load_artifacts()

    assert predictor.is_trained() is True
    metrics = predictor.metrics

    assert "accuracy_pct" in metrics
    assert "weighted_f1_pct" in metrics
    assert "weighted_precision_pct" in metrics
    assert "weighted_recall_pct" in metrics
    assert "confusion_matrix" in metrics

    # Verification of 4x4 confusion matrix
    cm = metrics["confusion_matrix"]
    assert len(cm) == 4
    for row in cm:
        assert len(row) == 4

    assert metrics.get("split_mode") == "chronological"
    assert "prediction_horizon" in metrics
    assert "dataset_limitations" in metrics


def test_predictor_segment_inference():
    predictor = TrafficPredictor()
    predictor.load_artifacts()

    features = {
        "road_id": "RD_BLR_01",
        "vehicle_count": 28000,
        "average_speed": 34.5,
        "capacity_utilization": 55.0,
        "congestion_level": "Moderate",
        "hour": 17,
        "day_of_week": 2,
        "is_weekend": 0,
        "city_zone": "Indiranagar",
        "intersection_id": "INT_BLR_01"
    }

    pred_class, prob_dist = predictor.predict_segment(features)
    assert pred_class in ("Low", "Moderate", "High", "Severe")
    assert isinstance(prob_dist, dict)
    assert sum(prob_dist.values()) > 0.95
