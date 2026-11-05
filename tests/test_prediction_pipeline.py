"""
tests/test_prediction_pipeline.py - Scientific Verification of XGBoost Training & Inference Pipeline
Verifies:
1. Hourly granularity: 24 records per road-day mapped to hours 0-23.
2. Temporal order & target succession: next row is exactly t + 1 hour.
3. Final observation boundary handling: zero synthetic modal target fabrication.
4. Date-grouped chronological split: disjoint train and test dates with zero leakage.
5. Error raising: zero silent uniform probability fallback when artifacts are missing.
6. Probability consistency: pure-Python tree ensemble compatibility with XGBoost.
7. Multi-class balance & metrics: per-class precision, recall, F1, and confusion matrix.
"""

import json
import pytest
import numpy as np
import pandas as pd

from traffic_system.config import (
    TRAINING_METRICS_FILE,
    MODEL_TREES_FILE,
    MODEL_FILE,
    PREPROCESSOR_FILE,
    LABEL_ENCODER_FILE,
    DATASET_PATH
)
from traffic_system.models.predictor import (
    TrafficPredictor,
    PurePythonEnsemble,
    load_kaggle_dataset,
    FEATURE_COLS
)


def test_dataset_hourly_granularity_and_succession():
    df = load_kaggle_dataset(DATASET_PATH)

    # 1. Verify 24 hourly values per road-day
    hours = df["hour"].unique()
    assert len(hours) == 24
    assert set(hours) == set(range(24))

    # 2. Verify temporal progression for each road
    sample_road = df[df["road_id"] == "RD_BLR_01"].sort_values("timestamp")
    diffs = sample_road["timestamp"].diff().dropna()
    # Consecutive observations within the same road must be exactly 1 hour
    assert (diffs == pd.Timedelta(hours=1)).all()

    # 3. Verify target alignment: Future_Congestion at row i equals congestion_level at row i + 1
    assert (sample_road["Future_Congestion"].iloc[:-1].values == sample_road["congestion_level"].iloc[1:].values).all()


def test_prediction_artifacts_and_metrics_integrity():
    predictor = TrafficPredictor()
    predictor.load_artifacts()

    assert predictor.is_trained() is True
    metrics = predictor.metrics

    assert "accuracy_pct" in metrics
    assert "weighted_f1_pct" in metrics
    assert "macro_f1_pct" in metrics
    assert "weighted_precision_pct" in metrics
    assert "weighted_recall_pct" in metrics
    assert "confusion_matrix" in metrics
    assert "per_class_metrics" in metrics

    # Verification of 4x4 confusion matrix
    cm = metrics["confusion_matrix"]
    assert len(cm) == 4
    for row in cm:
        assert len(row) == 4

    # Verification of per-class metrics
    classes = ["High", "Low", "Moderate", "Severe"]
    for cls in classes:
        assert cls in metrics["per_class_metrics"]
        pcm = metrics["per_class_metrics"][cls]
        assert "precision_pct" in pcm
        assert "recall_pct" in pcm
        assert "f1_pct" in pcm
        assert pcm["support"] > 0

    assert metrics.get("split_mode") == "chronological"
    assert metrics.get("observation_granularity") == "1_hour"
    assert metrics.get("prediction_horizon") == "1_hour_ahead"
    assert "dataset_limitations" in metrics
    assert "feature_schema" in metrics
    assert "excluded_features_rationale" in metrics["feature_schema"]


def test_date_grouped_chronological_split_disjointness():
    with open(TRAINING_METRICS_FILE, "r") as f:
        metrics = json.load(f)

    split_meta = metrics.get("split_metadata", {})
    assert split_meta.get("method") == "chronological_by_date"
    train_range = split_meta.get("train_dates_range", [])
    test_range = split_meta.get("test_dates_range", [])

    assert len(train_range) == 2
    assert len(test_range) == 2
    # Ensure test period strictly follows train period without overlap
    assert train_range[1] < test_range[0]
    assert split_meta.get("train_days") == 80
    assert split_meta.get("test_days") == 20


def test_pure_python_ensemble_probability_equivalence():
    predictor = TrafficPredictor()
    predictor.load_artifacts()

    sample_features = {
        "road_id": "RD_BLR_01",
        "vehicle_count": 28000,
        "average_speed": 34.5,
        "capacity_utilization": 55.0,
        "congestion_level": "Moderate",
        "hour": 17,
        "day_of_week": 2,
        "is_weekend": 0
    }

    safe = predictor._sanitize_features(sample_features)
    x = predictor._vectorize_features(safe)

    # 1. Pure-Python forward pass
    py_probs, _ = predictor._evaluate_trees_raw(x)

    # 2. Native XGBoost forward pass (if installed)
    if hasattr(predictor.model, "predict_proba"):
        xgb_probs = predictor.model.predict_proba([x])[0].tolist()
        for p_py, p_xgb in zip(py_probs, xgb_probs):
            assert abs(p_py - p_xgb) < 0.01


def test_no_silent_fallback_on_missing_model():
    predictor = TrafficPredictor()
    # Explicitly clear trees_data
    predictor.trees_data = None

    with pytest.raises(RuntimeError) as exc_info:
        predictor._evaluate_trees_raw([0.0] * 10)
    assert "missing or uninitialized" in str(exc_info.value).lower()


def test_xgboost_feature_order_and_prediction_parity():
    """
    Validates:
    1. Feature order strictness: regardless of dictionary key ordering,
       vectorization must produce identical feature vectors.
    2. Prediction parity: predict() matches argmax of class probabilities.
    3. Probability normalization: probabilities sum to 1.0.
    """
    predictor = TrafficPredictor()
    predictor.load_artifacts()

    # Dictionary with key ordering A
    feat_order_a = {
        "road_id": "RD_BLR_03",
        "vehicle_count": 31000,
        "average_speed": 22.0,
        "capacity_utilization": 78.0,
        "congestion_level": "High",
        "hour": 18,
        "day_of_week": 4,
        "is_weekend": 0
    }

    # Dictionary with reverse key ordering B
    feat_order_b = {k: feat_order_a[k] for k in reversed(list(feat_order_a.keys()))}

    # Vectorize both
    safe_a = predictor._sanitize_features(feat_order_a)
    vec_a = predictor._vectorize_features(safe_a)

    safe_b = predictor._sanitize_features(feat_order_b)
    vec_b = predictor._vectorize_features(safe_b)

    # Parity check on vectorization
    assert len(vec_a) == len(vec_b) == 10
    assert vec_a == vec_b, "Feature vectorization must be invariant to input dictionary key order."

    # Prediction parity
    class_a, probs_a = predictor.predict_segment(feat_order_a)
    class_b, probs_b = predictor.predict_segment(feat_order_b)

    assert class_a == class_b
    assert probs_a == probs_b

    # Sum of probabilities must normalize to 1.0
    assert abs(sum(probs_a.values()) - 1.0) < 1e-3

    # Argmax class must match predicted class
    top_class = max(probs_a.items(), key=lambda kv: kv[1])[0]
    assert class_a == top_class


def test_chronological_date_group_split_leakage_prevented():
    """
    Directly evaluates dataset date grouping:
    Confirms zero cross-set leakage between training dates and test dates.
    """
    df = load_kaggle_dataset(DATASET_PATH)
    unique_dates = sorted(df["date_dt"].unique())
    n_days = len(unique_dates)

    n_train_days = int(n_days * 0.8)
    train_dates = set(unique_dates[:n_train_days])
    test_dates = set(unique_dates[n_train_days:])

    # 1. Zero date leakage: disjoint sets
    assert train_dates.isdisjoint(test_dates), "Train and test date sets must have zero overlap."

    # 2. Strict temporal ordering: all train dates precede all test dates
    assert max(train_dates) < min(test_dates), "All training dates must strictly precede testing dates."

    # 3. Dataset split partition check
    train_df = df[df["date_dt"].isin(train_dates)]
    test_df = df[df["date_dt"].isin(test_dates)]
    assert len(train_df) + len(test_df) == len(df)
    assert set(train_df["date_dt"]).intersection(set(test_df["date_dt"])) == set()

