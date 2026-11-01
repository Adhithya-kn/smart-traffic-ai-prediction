

import json
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import xgboost as xgb

from traffic_system.config import (
    DATASET_PATH,
    ARTIFACTS_DIR,
    MODEL_FILE,
    PREPROCESSOR_FILE,
    LABEL_ENCODER_FILE,
    NETWORK_TOPOLOGY_FILE
)
from traffic_system.core.traffic_physics import calculate_capacity_utilization

# Essential feature schema: physics-grounded traffic dynamics (volume, speed, capacity utilization, LOS, time)
FEATURE_COLS = [
    "vehicle_count",
    "average_speed",
    "capacity_utilization",
    "congestion_level",
    "hour",
    "day_of_week",
    "is_weekend"
]
CATEGORICAL_COLS = ["congestion_level"]
NUMERIC_COLS = ["vehicle_count", "average_speed", "capacity_utilization", "hour", "day_of_week", "is_weekend"]
TARGET_COL = "Future_Congestion"

ORDINAL_RANKS = {"Low": 1.0, "Moderate": 2.0, "High": 3.0, "Severe": 4.0}

def compute_confidence_margin(probabilities: List[float]) -> float:
    """Computes difference between top-1 and top-2 class probability."""
    if len(probabilities) < 2:
        return 1.0
    sorted_p = sorted(probabilities, reverse=True)
    return round(float(sorted_p[0] - sorted_p[1]), 4)

def compute_shannon_entropy(probabilities: List[float]) -> float:
    """Normalized Shannon entropy H(p) in [0, 1] for schema compatibility."""
    p = np.array(probabilities, dtype=float)
    p = p[p > 0]
    k = len(probabilities)
    if k <= 1 or len(p) <= 1:
        return 0.0
    entropy = -np.sum(p * np.log2(p))
    max_entropy = math.log2(k) if k > 1 else 1.0
    return round(float(entropy / max_entropy), 3)

def load_kaggle_dataset(dataset_path: Path) -> pd.DataFrame:
    """Ingests raw Bangalore Traffic Pulse dataset from Kaggle directly and formats features in memory."""
    from traffic_system.core.road_registry import ROAD_REGISTRY
    raw_df = pd.read_csv(dataset_path)

    # Check if raw Kaggle format
    if "Road/Intersection Name" in raw_df.columns:
        name_to_road = {info["bangalore_name"].lower().strip(): r_id for r_id, info in ROAD_REGISTRY.items()}
        df = pd.DataFrame()
        df["timestamp"] = pd.to_datetime(raw_df["Date"], format="%d-%m-%Y", errors="coerce")
        df["hour"] = 18  # Evening commute observation window
        df["day_of_week"] = df["timestamp"].dt.dayofweek

        road_names = raw_df["Road/Intersection Name"].str.strip()
        df["road_name"] = road_names
        df["road_id"] = road_names.str.lower().map(name_to_road)
        df["city_zone"] = df["road_id"].map(lambda r: ROAD_REGISTRY.get(r, {}).get("city_zone", "Bengaluru Central"))
        df["intersection_id"] = df["road_id"].map(lambda r: ROAD_REGISTRY.get(r, {}).get("intersection_id", f"INT_{r}"))

        df["vehicle_count"] = pd.to_numeric(raw_df["Traffic Volume"], errors="coerce").fillna(1000).astype(int)
        df["average_speed"] = pd.to_numeric(raw_df["Average Speed"], errors="coerce").round(1)
        df["capacity_utilization"] = pd.to_numeric(raw_df["Road Capacity Utilization"], errors="coerce").fillna(70.0).round(1)
        df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

        def score_to_los(val):
            v = float(val)
            if v < 50.0: return "Low"
            elif v < 75.0: return "Moderate"
            elif v < 90.0: return "High"
            else: return "Severe"

        df["congestion_level"] = raw_df["Congestion Level"].apply(score_to_los)
        df = df.sort_values(by=["road_id", "timestamp"]).reset_index(drop=True)
        df["Future_Congestion"] = df.groupby("road_id")["congestion_level"].shift(-1)
        for r_id in df["road_id"].unique():
            mask = df["road_id"] == r_id
            last_idx = df[mask].index[-1]
            df.loc[last_idx, "Future_Congestion"] = df.loc[mask, "congestion_level"].mode().iloc[0]
        return df
    else:
        df = raw_df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df["hour"] = df["timestamp"].dt.hour.fillna(18).astype(int)
        df["day_of_week"] = df["timestamp"].dt.dayofweek.fillna(3).astype(int)
        df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
        if "capacity_utilization" not in df.columns:
            df["capacity_utilization"] = 70.0
        return df

def build_network_topology(df: pd.DataFrame) -> Dict[str, Any]:
    """Extracts empirical summary statistics and peak-period profiles for all Bangalore corridors."""
    topology = {}
    grouped = df.groupby("road_id")
    for road_id, group in grouped:
        cong_dist = group["congestion_level"].value_counts(normalize=True).to_dict()
        pred_dist = (
            group["Predicted_Future_Congestion"].value_counts(normalize=True).to_dict()
            if "Predicted_Future_Congestion" in group.columns
            else cong_dist
        )

        # Evening peak window (17:00 - 19:00 on weekdays)
        peak_group = group[(group["hour"].isin([17, 18, 19])) & (group["day_of_week"] < 5)]
        eval_group = peak_group if len(peak_group) > 0 else group

        peak_cong = str(eval_group["congestion_level"].mode().iloc[0])
        peak_vol = int(round(eval_group["vehicle_count"].mean()))
        peak_speed = float(round(eval_group["average_speed"].mean(), 1))

        dominant_current = str(group["congestion_level"].mode().iloc[0])
        dominant_predicted = max(pred_dist.items(), key=lambda x: x[1])[0] if pred_dist else dominant_current

        city_zone = str(group["city_zone"].iloc[0]) if "city_zone" in group.columns else "Bengaluru Central"
        intersection_id = str(group["intersection_id"].iloc[0]) if "intersection_id" in group.columns else f"INT_{road_id}"
        design_capacity = int(round(group["vehicle_count"].max() * 1.05))

        topology[road_id] = {
            "road_id": road_id,
            "city_zone": city_zone,
            "intersection_id": intersection_id,
            "avg_speed": float(round(group["average_speed"].mean(), 1)),
            "avg_volume": int(round(group["vehicle_count"].mean())),
            "peak_speed": peak_speed,
            "peak_volume": peak_vol,
            "capacity": design_capacity,
            "peak_congestion": peak_cong,
            "common_congestion": dominant_current,
            "common_predicted": dominant_predicted,
            "pred_dist": {k: float(round(v, 3)) for k, v in pred_dist.items()},
            "total_records": len(group)
        }
    return topology

class TrafficPredictor:
    
    def __init__(self, artifacts_dir: Path = ARTIFACTS_DIR):
        self.artifacts_dir = artifacts_dir
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.model: Optional[xgb.XGBClassifier] = None
        self.preprocessor: Optional[ColumnTransformer] = None
        self.label_encoder: Optional[LabelEncoder] = None
        self.topology: Dict[str, Any] = {}
        self.metrics: Dict[str, Any] = {}
        self._classes: List[str] = []
        self._feature_names: Optional[List[str]] = None
        self._booster = None

    def is_trained(self) -> bool:
        return (
            MODEL_FILE.exists() and
            PREPROCESSOR_FILE.exists() and
            LABEL_ENCODER_FILE.exists() and
            NETWORK_TOPOLOGY_FILE.exists()
        )

    def train_and_persist(self, dataset_path: Path = DATASET_PATH, split_mode: str = "stratified") -> Dict[str, Any]:
        """Trains regularized XGBoost model respecting class stratification and serializes artifacts."""
        if not dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found at {dataset_path}")

        df = load_kaggle_dataset(dataset_path)
        df = df.dropna(subset=[TARGET_COL] + FEATURE_COLS).copy()

        self.topology = build_network_topology(df)
        with open(NETWORK_TOPOLOGY_FILE, "w", encoding="utf-8") as f:
            json.dump(self.topology, f, indent=2)

        self.preprocessor = ColumnTransformer([
            ("num", SimpleImputer(strategy="median"), NUMERIC_COLS),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_COLS)
        ])

        self.label_encoder = LabelEncoder()
        y = self.label_encoder.fit_transform(df[TARGET_COL])
        X = df[FEATURE_COLS]

        if split_mode == "chronological":
            df = df.sort_values("timestamp")
            cutoff_idx = int(len(df) * 0.80)
            X_train, X_test = X.iloc[:cutoff_idx], X.iloc[cutoff_idx:]
            y_train, y_test = y[:cutoff_idx], y[cutoff_idx:]
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )

        X_train_trans = self.preprocessor.fit_transform(X_train)
        X_test_trans = self.preprocessor.transform(X_test)

        # Smooth square-root sample weights to handle minority classes without collapsing majority precision
        class_counts = np.bincount(y_train)
        sqrt_weights = np.sqrt(len(y_train) / (len(class_counts) * class_counts))
        sqrt_weights = sqrt_weights / sqrt_weights.mean()
        sample_weights = sqrt_weights[y_train]

        self.model = xgb.XGBClassifier(
            n_estimators=80,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=42,
            tree_method="hist",
            eval_metric="mlogloss",
            n_jobs=4
        )
        self.model.fit(X_train_trans, y_train, sample_weight=sample_weights)

        y_pred = self.model.predict(X_test_trans)
        acc = float(round(accuracy_score(y_test, y_pred) * 100, 2))
        f1_w = float(round(f1_score(y_test, y_pred, average="weighted") * 100, 2))
        prec_w = float(round(precision_score(y_test, y_pred, average="weighted", zero_division=0) * 100, 2))
        rec_w = float(round(recall_score(y_test, y_pred, average="weighted", zero_division=0) * 100, 2))

        self.metrics = {
            "accuracy_pct": acc,
            "weighted_f1_pct": f1_w,
            "weighted_precision_pct": prec_w,
            "weighted_recall_pct": rec_w,
            "classes": self.label_encoder.classes_.tolist(),
            "total_samples": len(df),
            "test_samples": len(y_test)
        }

        joblib.dump(self.model, MODEL_FILE)
        joblib.dump(self.preprocessor, PREPROCESSOR_FILE)
        joblib.dump(self.label_encoder, LABEL_ENCODER_FILE)

        metrics_file = ARTIFACTS_DIR / "training_metrics.json"
        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(self.metrics, f, indent=2)

        return self.metrics

    def load_artifacts(self) -> None:
       
        if not self.is_trained():
            self.train_and_persist()
            return

        self.model = joblib.load(MODEL_FILE)
        self.preprocessor = joblib.load(PREPROCESSOR_FILE)
        self.label_encoder = joblib.load(LABEL_ENCODER_FILE)
        self._classes = list(self.label_encoder.classes_)

        try:
            self._feature_names = list(self.preprocessor.get_feature_names_out())
            self._booster = self.model.get_booster()
        except Exception:
            self._feature_names = None
            self._booster = None

        with open(NETWORK_TOPOLOGY_FILE, "r", encoding="utf-8") as f:
            self.topology = json.load(f)

        metrics_file = ARTIFACTS_DIR / "training_metrics.json"
        if metrics_file.exists():
            with open(metrics_file, "r", encoding="utf-8") as f:
                self.metrics = json.load(f)

    def _sanitize_features(self, segment_features: Dict[str, Any]) -> Dict[str, Any]:
        
        safe = {}
        road_id = str(segment_features.get("road_id", "RD_BLR_01"))
        road_topo = self.topology.get(road_id, {}) if self.topology else {}

        for col in FEATURE_COLS:
            if col in segment_features and segment_features[col] is not None:
                val = segment_features[col]
                if col == "average_speed" and isinstance(val, (int, float)):
                    val = max(5.0, float(val))
                safe[col] = val
            elif col in road_topo:
                safe[col] = road_topo[col]
            elif col == "hour":
                safe[col] = 17
            elif col == "day_of_week":
                safe[col] = 2
            elif col == "is_weekend":
                dow = segment_features.get("day_of_week", road_topo.get("day_of_week", 2))
                safe[col] = 1 if dow >= 5 else 0
            elif col == "congestion_level":
                safe[col] = road_topo.get("common_congestion", "Moderate")
            elif col == "vehicle_count":
                safe[col] = road_topo.get("avg_volume", 25000)
            elif col == "average_speed":
                safe[col] = road_topo.get("avg_speed", 38.0)
            else:
                safe[col] = 0.0

        # Dynamically calculate capacity utilization if missing or zero
        vol = safe.get("vehicle_count", road_topo.get("avg_volume", 25000))
        if "capacity_utilization" not in safe or not safe["capacity_utilization"]:
            cap = road_topo.get("capacity", road_topo.get("peak_volume", 30000) * 1.10)
            safe["capacity_utilization"] = calculate_capacity_utilization(vol, cap, clamp=True)

        dow = safe.get("day_of_week", 2)
        if "is_weekend" not in safe or safe["is_weekend"] is None:
            safe["is_weekend"] = 1 if dow >= 5 else 0

        return safe

    def predict_segment(self, segment_features: Dict[str, Any], explain: bool = False) -> Any:
        """Vectorized single-segment forward pass with optional explainability."""
        if self.model is None or self.preprocessor is None or self.label_encoder is None:
            self.load_artifacts()

        safe_features = self._sanitize_features(segment_features)
        df_row = pd.DataFrame([safe_features])
        X_trans = self.preprocessor.transform(df_row)

        proba = self.model.predict_proba(X_trans)[0]
        pred_idx = int(np.argmax(proba))
        pred_class = self._classes[pred_idx]

        prob_dist = {
            cls_name: round(float(p), 4)
            for cls_name, p in zip(self._classes, proba)
        }

        if not explain:
            return pred_class, prob_dist

        confidence = round(float(np.max(proba)), 4)
        margin = compute_confidence_margin(list(proba))
        entropy = compute_shannon_entropy(list(proba))

        top_drivers = []
        try:
            if self._booster is not None and self._feature_names is not None:
                dmat = xgb.DMatrix(X_trans)
                contribs = self._booster.predict(dmat, pred_contribs=True)
                class_contribs = contribs[0, pred_idx, :-1]

                grouped_impacts = {}
                for idx, raw_feat in enumerate(self._feature_names):
                    impact = float(class_contribs[idx])
                    if "vehicle_count" in raw_feat:
                        key = "vehicle_count (Demand Volume)"
                    elif "average_speed" in raw_feat:
                        key = "average_speed (Kinematic Velocity)"
                    elif "capacity_utilization" in raw_feat:
                        key = "capacity_utilization (Volume/Capacity Stress)"
                    elif "hour" in raw_feat or "day_of_week" in raw_feat or "is_weekend" in raw_feat:
                        key = "diurnal_schedule (Temporal Peak Factor)"
                    elif "congestion_level" in raw_feat:
                        key = "current_los (Queue State)"
                    else:
                        key = "corridor_baseline (Spatial Arterial Flow)"
                    grouped_impacts[key] = grouped_impacts.get(key, 0.0) + impact

                sorted_drivers = sorted(grouped_impacts.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
                for feat, impact in sorted_drivers:
                    top_drivers.append({
                        "feature": feat,
                        "impact": round(impact, 2),
                        "direction": "elevates_risk" if impact > 0 else "suppresses_risk"
                    })
        except Exception:
            pass

        return {
            "prediction": pred_class,
            "probabilities": prob_dist,
            "confidence_score": confidence,
            "confidence_margin": margin,
            "uncertainty_entropy": entropy,
            "top_drivers": top_drivers
        }

    def predict_batch(self, segments: List[Dict[str, Any]]) -> List[Tuple[str, Dict[str, float]]]:
       
        if not segments:
            return []
        if self.model is None or self.preprocessor is None or self.label_encoder is None:
            self.load_artifacts()

        safe_rows = [self._sanitize_features(s) for s in segments]
        df_batch = pd.DataFrame(safe_rows)
        X_trans = self.preprocessor.transform(df_batch)

        proba_matrix = self.model.predict_proba(X_trans)
        pred_indices = np.argmax(proba_matrix, axis=1)

        return [
            (self._classes[int(pred_indices[i])], {c: round(float(p), 4) for c, p in zip(self._classes, row)})
            for i, row in enumerate(proba_matrix)
        ]
