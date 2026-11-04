#!/usr/bin/env python3
"""
run_system.py - Production Runtime & Diagnostic Bootstrap Engine
Performs rigorous pre-flight validation of dependencies, ML model artifacts,
dataset integrity, storage directories, environment variables, and port handling.
"""

# CRITICAL FOR MACOS APPLE SILICON: Initialize PyTorch before XGBoost/OpenMP to prevent symbol collision segfaults
try:
    import torch
except ImportError:
    pass

import sys
import os
import argparse
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from traffic_system.config import (
    BASE_DIR,
    DATASET_PATH,
    ARTIFACTS_DIR,
    VIDEO_STORAGE_DIR,
    MODEL_FILE,
    PREPROCESSOR_FILE,
    LABEL_ENCODER_FILE,
    MODEL_TREES_FILE,
    TRAINING_METRICS_FILE,
    NETWORK_TOPOLOGY_FILE,
    ENV,
    IS_PRODUCTION
)


def validate_environment() -> bool:
    """Pre-flight check of dependencies, storage paths, datasets, environment variables and model artifacts."""
    print("-------------------------------------------------------------------------")
    print("  PRE-FLIGHT DIAGNOSTIC AND INTEGRITY AUDIT                              ")
    print("-------------------------------------------------------------------------")
    all_ok = True

    # 1. Environment Variables Audit
    print(f"  [INFO] Environment: {ENV.upper()} (Production Mode: {IS_PRODUCTION})")
    persistent_dir = os.environ.get("PERSISTENT_DATA_DIR", "")
    if persistent_dir:
        print(f"  [OK] Persistent Storage Mount: {persistent_dir}")
    else:
        print("  [INFO] Persistent Storage: Local filesystem default (PERSISTENT_DATA_DIR not set).")

    tomtom_key = (os.environ.get("TOMTOM_API_KEY") or os.environ.get("API_KEY_TOMTOM") or "").strip()
    gmaps_key = (os.environ.get("GOOGLE_MAPS_API_KEY") or os.environ.get("API_KEY_GOOGLE_MAPS") or "").strip()
    print(f"  [{'OK' if tomtom_key else 'INFO'}] TomTom Traffic API Key: {'Configured' if tomtom_key else 'Not configured (historical fallback active)'}")
    print(f"  [{'OK' if gmaps_key else 'INFO'}] Google Maps API Key: {'Configured' if gmaps_key else 'Not configured (spatial fallback active)'}")

    # 2. Core Python Dependencies Verification
    required_packages = ["numpy", "pandas", "sklearn", "xgboost", "joblib", "scipy", "urllib3"]
    for pkg in required_packages:
        try:
            m = __import__(pkg)
            ver = getattr(m, "__version__", "loaded")
            print(f"  [OK] Dependency: {pkg} (v{ver})")
        except ImportError as e:
            print(f"  [FAIL] Missing required Python dependency: {pkg} ({e})")
            all_ok = False

    # 3. Storage & Directory Writeability
    from traffic_system.config import SNAPSHOT_BACKUP_DIR
    for path, name in [
        (ARTIFACTS_DIR, "Artifacts Directory"),
        (VIDEO_STORAGE_DIR, "Video Storage Directory"),
        (SNAPSHOT_BACKUP_DIR, "Snapshot Backup Directory"),
    ]:
        try:
            path.mkdir(parents=True, exist_ok=True)
            test_file = path / ".write_test.tmp"
            test_file.write_text("test")
            test_file.unlink(missing_ok=True)
            print(f"  [OK] Storage: {name} ({path})")
        except Exception as e:
            print(f"  [FAIL] Storage not writeable: {name} ({path}): {e}")
            all_ok = False

    # 4. Dataset Integrity
    if DATASET_PATH.exists() and DATASET_PATH.is_file():
        size_mb = DATASET_PATH.stat().st_size / (1024 * 1024)
        print(f"  [OK] Benchmark Dataset: {DATASET_PATH.name} ({size_mb:.2f} MB)")
    else:
        print(f"  [WARN] Dataset file not found at {DATASET_PATH}. Synthetic / fallback telemetry active.")

    # 5. Machine Learning Artifacts
    artifacts_present = all([
        MODEL_FILE.exists(),
        PREPROCESSOR_FILE.exists(),
        LABEL_ENCODER_FILE.exists(),
        MODEL_TREES_FILE.exists(),
        TRAINING_METRICS_FILE.exists(),
        NETWORK_TOPOLOGY_FILE.exists()
    ])

    explicit_retrain = "--retrain" in sys.argv

    if artifacts_present and not explicit_retrain:
        print("  [OK] ML Model Artifacts: Serialized XGBoost model, preprocessors, and tree ensembles present.")
    else:
        reason = "Explicit --retrain flag passed" if explicit_retrain else "Missing ML artifacts"
        print(f"  [INFO] {reason}. Initiating chronological date-grouped XGBoost training...")
        try:
            from traffic_system.models.predictor import TrafficPredictor
            predictor = TrafficPredictor()
            metrics = predictor.train_and_persist(split_mode="chronological")
            print(f"  [OK] Model successfully trained & persisted via chronological validation: Acc {metrics.get('accuracy_pct', 0)}%")
        except Exception as e:
            print(f"  [FAIL] Failed to train & persist model artifacts: {e}")
            if IS_PRODUCTION:
                all_ok = False

    # 6. Computer Vision & YOLO Model Runtime
    try:
        from traffic_system.computer_vision.detector import get_vehicle_detector
        detector = get_vehicle_detector()
        if detector.is_yolo_active:
            print(f"  [OK] Computer Vision: Ultralytics YOLO active ({detector.model_name}).")
        else:
            print(f"  [WARN] Computer Vision: YOLO unavailable ({detector.load_error or 'Weights not loaded'}).")
    except Exception as e:
        print(f"  [WARN] Computer Vision init notice: {e}")

    print("-------------------------------------------------------------------------")
    return all_ok


def parse_arguments():
    """Parses CLI arguments with robust port and flag validation."""
    parser = argparse.ArgumentParser(description="Smart Traffic AI Server Runtime")
    parser.add_argument("positional_port", nargs="?", type=int, default=None, help="Server port (positional)")
    parser.add_argument("-p", "--port", type=int, default=None, help="Server port (flag)")
    parser.add_argument("--host", type=str, default=os.environ.get("HOST", "0.0.0.0"), help="Bind host address")
    parser.add_argument("--retrain", action="store_true", help="Force model retraining before launch")
    parser.add_argument("--demo", action="store_true", help="Run demonstrator before starting")
    return parser.parse_known_args()


def resolve_port(args) -> int:
    """Determines and validates the target listening port."""
    raw_port = None
    if args.port is not None:
        raw_port = args.port
    elif args.positional_port is not None:
        raw_port = args.positional_port
    else:
        env_port = os.environ.get("PORT")
        if env_port:
            try:
                raw_port = int(env_port)
            except ValueError:
                raw_port = None

    if raw_port is None:
        raw_port = 8080

    if not (1 <= raw_port <= 65535):
        print(f"  [WARN] Port {raw_port} out of range (1-65535). Falling back to 8080.")
        return 8080

    return raw_port


def main():
    print("=========================================================================")
    print("  AI-BASED SMART TRAFFIC MONITORING & CONGESTION PREDICTION SYSTEM       ")
    print("  Advisory Decision Support & Spatio-Temporal Simulation Platform        ")
    print("=========================================================================")

    args, _ = parse_arguments()

    if args.demo:
        try:
            import demonstrate_pipeline
            demonstrate_pipeline.run_pipeline()
        except ImportError:
            pass

    if not validate_environment() and IS_PRODUCTION:
        print("FATAL: Environment validation failed in production mode. Aborting startup.")
        sys.exit(1)

    from traffic_system.models.predictor import TrafficPredictor
    from traffic_system.events.event_manager import EventManager
    from app.server import run_server

    print("[1/3] Loading Traffic Predictor Engine...")
    predictor = TrafficPredictor()
    predictor.load_artifacts()
    acc = round(float(predictor.metrics.get("accuracy_pct", 0.0)), 2)
    split_mode = predictor.metrics.get("split_mode", "chronological")
    test_samples = predictor.metrics.get("split_metadata", {}).get("test_samples", predictor.metrics.get("test_samples", 11496))
    print(f"  -> Model ready ({split_mode.capitalize()} Test Accuracy: {acc}% on {test_samples:,} out-of-time test observations).")

    print("[2/3] Checking Municipal Event Engine & User Security Database...")
    evt_mgr = EventManager()
    print(f"  -> {len(evt_mgr.get_all_events())} baseline municipal events loaded.")

    port = resolve_port(args)
    host = args.host

    print(f"[3/3] Launching Obsidian Dual-Persona Server on http://{host}:{port}")
    run_server(port, predictor=predictor, event_mgr=evt_mgr)


if __name__ == "__main__":
    main()
