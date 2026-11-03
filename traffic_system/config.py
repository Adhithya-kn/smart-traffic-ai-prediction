"""
traffic_system/config.py - Centralized Configuration & Environment Management
Manages file paths, API credentials, upload limits, timeouts, and security policies.
"""

import os
import shutil
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
ENV = os.environ.get("ENV", "development").lower()
IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
IS_PRODUCTION = ENV == "production"

# Storage Directories
ARTIFACTS_DIR = BASE_DIR / "traffic_system" / "artifacts"
DATASET_PATH = BASE_DIR / "Dataset" / "Banglore_traffic_Dataset.csv"

if IS_VERCEL:
    TMP_DIR = Path("/tmp/traffic_system")
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    USERS_DB_PATH = TMP_DIR / "users.json"
    EVENTS_DB_PATH = TMP_DIR / "events.json"
    VIDEO_STORAGE_DIR = TMP_DIR / "videos"
    for orig, tmp_dest in (
        (ARTIFACTS_DIR / "users.json", USERS_DB_PATH),
        (ARTIFACTS_DIR / "events.json", EVENTS_DB_PATH),
    ):
        if not tmp_dest.exists() and orig.exists():
            shutil.copyfile(orig, tmp_dest)
else:
    USERS_DB_PATH = ARTIFACTS_DIR / "users.json"
    EVENTS_DB_PATH = ARTIFACTS_DIR / "events.json"
    VIDEO_STORAGE_DIR = BASE_DIR / "traffic_system" / "storage" / "videos"

VIDEO_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Machine Learning Artifacts
MODEL_FILE = ARTIFACTS_DIR / "xgboost_model.joblib"
MODEL_TREES_FILE = ARTIFACTS_DIR / "model_trees.json"
PREPROCESSOR_FILE = ARTIFACTS_DIR / "preprocessor.joblib"
LABEL_ENCODER_FILE = ARTIFACTS_DIR / "label_encoder.joblib"
TRAINING_METRICS_FILE = ARTIFACTS_DIR / "training_metrics.json"
NETWORK_TOPOLOGY_FILE = ARTIFACTS_DIR / "network_topology.json"

# External API Integrations (TomTom & Weather)
TOMTOM_API_KEY = os.environ.get("TOMTOM_API_KEY", "").strip()
TOMTOM_BASE_URL = os.environ.get("TOMTOM_BASE_URL", "https://api.tomtom.com").rstrip("/")
TOMTOM_TIMEOUT_SECONDS = float(os.environ.get("TOMTOM_TIMEOUT_SECONDS", "6.0"))

WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "").strip()
WEATHER_BASE_URL = os.environ.get("WEATHER_BASE_URL", "https://api.open-meteo.com/v1/forecast").rstrip("/")
WEATHER_TIMEOUT_SECONDS = float(os.environ.get("WEATHER_TIMEOUT_SECONDS", "6.0"))

API_CACHE_TTL_SECONDS = float(os.environ.get("API_CACHE_TTL_SECONDS", "60.0"))
API_MAX_RETRIES = int(os.environ.get("API_MAX_RETRIES", "3"))

# Upload & Request Limits
MAX_REQUEST_BODY_SIZE = int(os.environ.get("MAX_REQUEST_BODY_SIZE", 10 * 1024 * 1024))      # 10 MB default for general JSON/payloads
MAX_VIDEO_UPLOAD_SIZE = int(os.environ.get("MAX_VIDEO_UPLOAD_SIZE", 100 * 1024 * 1024))   # 100 MB max for MP4 video
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}

# Security & Session Settings
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "traffic_admin").strip()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "").strip()
ALLOW_DEMO_ACCOUNTS = os.environ.get("ALLOW_DEMO_ACCOUNTS", "false" if IS_PRODUCTION else "true").lower() in ("true", "1")
ENFORCE_ADMIN_AUTH = os.environ.get("ENFORCE_ADMIN_AUTH", "true" if IS_PRODUCTION else "false").lower() in ("true", "1")
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", "86400"))
CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "*")

# Computer Vision Configuration
CV_CONFIDENCE_THRESHOLD = float(os.environ.get("CV_CONFIDENCE_THRESHOLD", "0.30"))
CV_IOU_THRESHOLD = float(os.environ.get("CV_IOU_THRESHOLD", "0.45"))
CV_MAX_PROCESSING_FRAMES = int(os.environ.get("CV_MAX_PROCESSING_FRAMES", "1800"))
CV_JOB_TIMEOUT_SECONDS = int(os.environ.get("CV_JOB_TIMEOUT_SECONDS", "300"))

# Domain Constants
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
