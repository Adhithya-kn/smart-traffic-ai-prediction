
import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
DATASET_PATH = BASE_DIR / "Dataset" / "Banglore_traffic_Dataset.csv"
ARTIFACTS_DIR = BASE_DIR / "traffic_system" / "artifacts"

if IS_VERCEL:
    TMP_DIR = Path("/tmp/traffic_system")
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    USERS_DB_PATH = TMP_DIR / "users.json"
    EVENTS_DB_PATH = TMP_DIR / "events.json"
    for orig, tmp_dest in (
        (ARTIFACTS_DIR / "users.json", USERS_DB_PATH),
        (ARTIFACTS_DIR / "events.json", EVENTS_DB_PATH),
    ):
        if not tmp_dest.exists() and orig.exists():
            shutil.copyfile(orig, tmp_dest)
else:
    USERS_DB_PATH = ARTIFACTS_DIR / "users.json"
    EVENTS_DB_PATH = ARTIFACTS_DIR / "events.json"

MODEL_FILE = ARTIFACTS_DIR / "xgboost_model.joblib"
MODEL_TREES_FILE = ARTIFACTS_DIR / "model_trees.json"
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
