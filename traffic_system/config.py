"""
traffic_system/config.py - Centralized Configuration & Environment Management
Manages file paths, API credentials, upload limits, timeouts, and security policies.
"""

import os
import shutil
from pathlib import Path

# Set Ultralytics config dir to writable /tmp to eliminate permission errors in sandboxed & production environments
os.environ.setdefault("YOLO_CONFIG_DIR", "/tmp/ultralytics")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# CRITICAL FOR MACOS APPLE SILICON & OPENMP RUNTIMES:
# Initialize PyTorch runtime before any OpenMP / XGBoost / SciPy imports
# to eliminate dynamic linker symbol collision segfaults (SIGSEGV / code 139).
try:
    import torch
    _ = torch.zeros(1)
except ImportError:
    pass

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

ENV = (os.environ.get("APP_ENV") or os.environ.get("ENV") or "development").lower()
IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
IS_PRODUCTION = ENV == "production"

# Network Host & Port Binding
HOST = os.environ.get("HOST", "0.0.0.0").strip()
PORT = int(os.environ.get("PORT", "8080"))

# Storage Directories
# Supports mounted persistent disk (e.g. Render Persistent Disk at PERSISTENT_DATA_DIR, e.g. /var/data)
REPO_ARTIFACTS_DIR = BASE_DIR / "traffic_system" / "artifacts"
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

# Runtime state (users, sessions, events, jobs, incidents) must never be written
# into tracked source artifacts. Keep immutable model/topology seeds in
# traffic_system/artifacts/, and put mutable state under var/ (local) or
# <PERSISTENT_DATA_DIR>/runtime (deployed). Tests may override RUNTIME_DATA_DIR.
if IS_VERCEL:
    DEFAULT_RUNTIME_DIR = Path("/tmp/traffic_system/runtime")
elif DATA_STORAGE_ROOT != (BASE_DIR / "traffic_system"):
    DEFAULT_RUNTIME_DIR = DATA_STORAGE_ROOT / "runtime"
else:
    DEFAULT_RUNTIME_DIR = BASE_DIR / "var"
RUNTIME_DATA_DIR = Path(os.environ.get("RUNTIME_DATA_DIR", str(DEFAULT_RUNTIME_DIR))).resolve()
RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)
RUNTIME_SEED_DIR = REPO_ARTIFACTS_DIR / "seeds"


def seed_runtime_file(filename: str, default_content: str = "{}") -> None:
    """Seed a mutable runtime JSON file from tracked artifacts if absent."""
    target = RUNTIME_DATA_DIR / filename
    if target.exists():
        return
    source = RUNTIME_SEED_DIR / filename
    try:
        if source.exists():
            shutil.copyfile(source, target)
        else:
            target.write_text(default_content, encoding="utf-8")
    except Exception:
        pass


# Seed baseline ML artifacts and datasets to persistent disk if fresh/empty
if DATA_STORAGE_ROOT != (BASE_DIR / "traffic_system") and REPO_ARTIFACTS_DIR.exists():
    for seed_fname in (
        "xgboost_model.joblib",
        "preprocessor.joblib",
        "label_encoder.joblib",
        "model_trees.json",
        "training_metrics.json",
        "network_topology.json",
        "events.json",
        "users.json"
    ):
        src_path = REPO_ARTIFACTS_DIR / seed_fname
        dst_path = ARTIFACTS_DIR / seed_fname
        if src_path.exists() and not dst_path.exists():
            try:
                shutil.copyfile(src_path, dst_path)
            except Exception:
                pass

if IS_VERCEL:
    TMP_DIR = Path("/tmp/traffic_system")
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    USERS_DB_PATH = TMP_DIR / "users.json"
    SESSIONS_DB_PATH = TMP_DIR / "sessions.json"
    EVENTS_DB_PATH = TMP_DIR / "events.json"
    INCIDENTS_HISTORY_DB_PATH = TMP_DIR / "incident_history.json"
    JOBS_DB_PATH = TMP_DIR / "vision_jobs.json"
    VIDEO_STORAGE_DIR = TMP_DIR / "videos"
    for name, tmp_dest in (
        ("users.json", USERS_DB_PATH),
        ("sessions.json", SESSIONS_DB_PATH),
        ("events.json", EVENTS_DB_PATH),
        ("incident_history.json", INCIDENTS_HISTORY_DB_PATH),
        ("vision_jobs.json", JOBS_DB_PATH),
    ):
        if not tmp_dest.exists():
            try:
                source = RUNTIME_SEED_DIR / name
                if source.exists():
                    shutil.copyfile(source, tmp_dest)
                else:
                    tmp_dest.write_text("{}", encoding="utf-8")
            except Exception:
                pass
else:
    seed_runtime_file("users.json")
    seed_runtime_file("sessions.json")
    seed_runtime_file("events.json")
    seed_runtime_file("incident_history.json")
    seed_runtime_file("vision_jobs.json")
    USERS_DB_PATH = RUNTIME_DATA_DIR / "users.json"
    SESSIONS_DB_PATH = RUNTIME_DATA_DIR / "sessions.json"
    EVENTS_DB_PATH = RUNTIME_DATA_DIR / "events.json"
    INCIDENTS_HISTORY_DB_PATH = RUNTIME_DATA_DIR / "incident_history.json"
    JOBS_DB_PATH = RUNTIME_DATA_DIR / "vision_jobs.json"
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
GOOGLE_MAPS_BROWSER_KEY = (os.environ.get("GOOGLE_MAPS_BROWSER_KEY") or GOOGLE_MAPS_API_KEY).strip()
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
if GOOGLE_MAPS_BROWSER_KEY:
    os.environ["GOOGLE_MAPS_BROWSER_KEY"] = GOOGLE_MAPS_BROWSER_KEY
if WEATHER_API_KEY:
    os.environ["WEATHER_API_KEY"] = WEATHER_API_KEY

# Application & Session Cryptographic Secrets
APP_SECRET_KEY = (os.environ.get("APP_SECRET_KEY") or os.environ.get("SECRET_KEY") or "").strip()
if not APP_SECRET_KEY:
    if IS_PRODUCTION:
        import secrets
        APP_SECRET_KEY = secrets.token_hex(32)
    else:
        APP_SECRET_KEY = "dev_insecure_app_secret_key_bengaluru_ai"
os.environ["APP_SECRET_KEY"] = APP_SECRET_KEY

SESSION_SECRET_KEY = (os.environ.get("SESSION_SECRET_KEY") or os.environ.get("JWT_SECRET") or APP_SECRET_KEY).strip()
os.environ["SESSION_SECRET_KEY"] = SESSION_SECRET_KEY

VAULT_MASTER_KEY = (os.environ.get("VAULT_MASTER_KEY") or os.environ.get("SECRETS_VAULT_KEY") or "").strip()
if VAULT_MASTER_KEY:
    os.environ["VAULT_MASTER_KEY"] = VAULT_MASTER_KEY

DEBUG = os.environ.get("DEBUG", "false" if IS_PRODUCTION else "true").lower() in ("true", "1")

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
ENFORCE_ADMIN_AUTH = os.environ.get("ENFORCE_ADMIN_AUTH", "true").lower() in ("true", "1")
# Anonymous admin mutations are never safe. Even when ENFORCE_ADMIN_AUTH is
# disabled for local demos, an explicit opt-in is required to allow them.
ALLOW_ANONYMOUS_ADMIN = os.environ.get("ALLOW_ANONYMOUS_ADMIN", "false").lower() in ("true", "1")
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", "86400"))
CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "*")

# Computer Vision Configuration
CV_DEFAULT_UVH26_PATH = BASE_DIR / "models" / "uvh26" / "UVH-26-MV-YOLOv11-S.pt"
CV_MODEL_NAME = os.environ.get(
    "CV_MODEL_NAME",
    str(CV_DEFAULT_UVH26_PATH) if CV_DEFAULT_UVH26_PATH.exists() else "yolo11n.pt"
)
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
