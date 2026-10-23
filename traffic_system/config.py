"""
traffic_system/config.py - Global Configuration & System Constants
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = BASE_DIR / "Dataset" / "Banglore_traffic_Dataset.csv"
ARTIFACTS_DIR = BASE_DIR / "traffic_system" / "artifacts"
USERS_DB_PATH = BASE_DIR / "traffic_system" / "artifacts" / "users.json"
EVENTS_DB_PATH = BASE_DIR / "traffic_system" / "artifacts" / "events.json"

MODEL_FILE = ARTIFACTS_DIR / "xgboost_model.joblib"
PREPROCESSOR_FILE = ARTIFACTS_DIR / "preprocessor.joblib"
LABEL_ENCODER_FILE = ARTIFACTS_DIR / "label_encoder.joblib"
NETWORK_TOPOLOGY_FILE = ARTIFACTS_DIR / "network_topology.json"

CONGESTION_LEVELS = ["Low", "Moderate", "High", "Severe"]

CITY_ZONES = [
    "Indiranagar",
    "Whitefield",
    "Koramangala",
    "M.G. Road CBD",
    "Jayanagar",
    "Hebbal North",
    "Yeshwanthpur West",
    "Electronic City South"
]

DEFAULT_ALPHA_DEMAND_REDUCTION = 0.20
DEFAULT_BETA_SPEED_RECOVERY = 0.10
