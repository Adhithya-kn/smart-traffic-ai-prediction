"""
traffic_system/config.py - Centralized Configuration & Environment Management
Manages file paths, API credentials, upload limits, timeouts, and security policies.
"""

import os
import shutil
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env via python-dotenv before reading settings
try:
    from dotenv import load_dotenv
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
    else:
        load_dotenv()
except ImportError:
    # Graceful manual fallback if python-dotenv is not installed
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip("'\"")
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

ENV = os.environ.get("ENV", "development").lower()
IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
IS_PRODUCTION = ENV == "production"

# Storage Directories
# Supports mounted persistent disk (e.g. Render Persistent Disk or AWS EBS at PERSISTENT_DATA_DIR)
PERSISTENT_DATA_DIR = Path(os.environ.get("PERSISTENT_DATA_DIR", "")).resolve() if os.environ.get("PERSISTENT_DATA_DIR") else None

if PERSISTENT_DATA_DIR and PERSISTENT_DATA_DIR.exists():
    DATA_STORAGE_ROOT = PERSISTENT_DATA_DIR
else:
    DATA_STORAGE_ROOT = BASE_DIR / "traffic_system"

ARTIFACTS_DIR = DATA_STORAGE_ROOT / "artifacts"
SNAPSHOT_BACKUP_DIR = ARTIFACTS_DIR / "backups"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
DATASET_PATH = BASE_DIR / "Dataset" / "Banglore_traffic_Dataset.csv"

if IS_VERCEL:
    TMP_DIR = Path("/tmp/traffic_system")
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    USERS_DB_PATH = TMP_DIR / "users.json"
    SESSIONS_DB_PATH = TMP_DIR / "sessions.json"
    EVENTS_DB_PATH = TMP_DIR / "events.json"
    INCIDENTS_HISTORY_DB_PATH = TMP_DIR / "incident_history.json"
    JOBS_DB_PATH = TMP_DIR / "vision_jobs.json"
    VIDEO_STORAGE_DIR = TMP_DIR / "videos"
    for orig, tmp_dest in (
        (ARTIFACTS_DIR / "users.json", USERS_DB_PATH),
        (ARTIFACTS_DIR / "sessions.json", SESSIONS_DB_PATH),
        (ARTIFACTS_DIR / "events.json", EVENTS_DB_PATH),
        (ARTIFACTS_DIR / "incident_history.json", INCIDENTS_HISTORY_DB_PATH),
        (ARTIFACTS_DIR / "vision_jobs.json", JOBS_DB_PATH),
    ):
        if not tmp_dest.exists() and orig.exists():
            shutil.copyfile(orig, tmp_dest)
else:
    USERS_DB_PATH = ARTIFACTS_DIR / "users.json"
    SESSIONS_DB_PATH = ARTIFACTS_DIR / "sessions.json"
    EVENTS_DB_PATH = ARTIFACTS_DIR / "events.json"
    INCIDENTS_HISTORY_DB_PATH = ARTIFACTS_DIR / "incident_history.json"
    JOBS_DB_PATH = ARTIFACTS_DIR / "vision_jobs.json"
    VIDEO_STORAGE_DIR = DATA_STORAGE_ROOT / "storage" / "videos"

VIDEO_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Machine Learning Artifacts
MODEL_FILE = ARTIFACTS_DIR / "xgboost_model.joblib"
MODEL_TREES_FILE = ARTIFACTS_DIR / "model_trees.json"
PREPROCESSOR_FILE = ARTIFACTS_DIR / "preprocessor.joblib"
LABEL_ENCODER_FILE = ARTIFACTS_DIR / "label_encoder.joblib"
TRAINING_METRICS_FILE = ARTIFACTS_DIR / "training_metrics.json"
NETWORK_TOPOLOGY_FILE = ARTIFACTS_DIR / "network_topology.json"

# Secure Secrets Vault & Persistence
SECRETS_VAULT_PATH = ARTIFACTS_DIR / ".secrets.vault"
try:
    if SECRETS_VAULT_PATH.exists():
        from traffic_system.core.secrets_manager import get_secrets_manager
        get_secrets_manager()  # Populates os.environ from persistent encrypted vault
except Exception:
    pass

# External API Integrations (Canonical environment names with legacy aliases supported)
TOMTOM_API_KEY = (os.environ.get("TOMTOM_API_KEY") or os.environ.get("API_KEY_TOMTOM") or "").strip()
TOMTOM_BASE_URL = os.environ.get("TOMTOM_BASE_URL", "https://api.tomtom.com").rstrip("/")
TOMTOM_TIMEOUT_SECONDS = float(os.environ.get("TOMTOM_TIMEOUT_SECONDS", "6.0"))

GOOGLE_MAPS_API_KEY = (os.environ.get("GOOGLE_MAPS_API_KEY") or os.environ.get("API_KEY_GOOGLE_MAPS") or "").strip()
GOOGLE_MAPS_MAP_ID = os.environ.get("GOOGLE_MAPS_MAP_ID", "").strip()
GOOGLE_MAPS_BASE_URL = os.environ.get("GOOGLE_MAPS_BASE_URL", "https://maps.googleapis.com").rstrip("/")
GOOGLE_MAPS_TIMEOUT_SECONDS = float(os.environ.get("GOOGLE_MAPS_TIMEOUT_SECONDS", "6.0"))

WEATHER_API_KEY = (os.environ.get("WEATHER_API_KEY") or os.environ.get("API_KEY_WEATHER") or "").strip()
WEATHER_BASE_URL = os.environ.get("WEATHER_BASE_URL", "https://api.open-meteo.com/v1/forecast").rstrip("/")
WEATHER_TIMEOUT_SECONDS = float(os.environ.get("WEATHER_TIMEOUT_SECONDS", "6.0"))

# Synchronize canonical names back to os.environ
if TOMTOM_API_KEY:
    os.environ["TOMTOM_API_KEY"] = TOMTOM_API_KEY
if GOOGLE_MAPS_API_KEY:
    os.environ["GOOGLE_MAPS_API_KEY"] = GOOGLE_MAPS_API_KEY
if WEATHER_API_KEY:
    os.environ["WEATHER_API_KEY"] = WEATHER_API_KEY

API_CACHE_TTL_SECONDS = float(os.environ.get("API_CACHE_TTL_SECONDS", "60.0"))
API_MAX_RETRIES = int(os.environ.get("API_MAX_RETRIES", "3"))

# Upload & Request Limits
MAX_REQUEST_BODY_SIZE = int(os.environ.get("MAX_REQUEST_BODY_SIZE", 10 * 1024 * 1024))      # 10 MB default for general JSON/payloads
MAX_VIDEO_UPLOAD_SIZE = int(os.environ.get("MAX_VIDEO_UPLOAD_SIZE", 256 * 1024 * 1024))   # 256 MB max for MP4 video
CHUNK_UPLOAD_SIZE = int(os.environ.get("CHUNK_UPLOAD_SIZE", 8 * 1024 * 1024))             # 8 MB disk-backed chunks
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

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
CV_MAX_PROCESSING_FRAMES = int(os.environ.get("CV_MAX_PROCESSING_FRAMES", "3600"))
CV_JOB_TIMEOUT_SECONDS = int(os.environ.get("CV_JOB_TIMEOUT_SECONDS", "600"))

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
