"""
tests/test_run_system_and_deployment.py - Verification of Deployment Checklist & Root Configuration
Validates run_system.py argument and port resolution, pre-flight environment checks,
requirements.txt pinned packages, render.yaml persistence/secrets, vercel.json serverless limits,
Procfile, api/index.py handler, .gitignore, .dockerignore, and LICENSE/README claims.
"""

import os
import re
import sys
import json
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_requirements_pinned_and_cv_included():
    req_file = PROJECT_ROOT / "requirements.txt"
    assert req_file.exists()
    content = req_file.read_text()

    assert "scikit-learn" in content
    assert "xgboost" in content
    assert "opencv-python-headless" in content
    assert "ultralytics" in content

    # Ensure python_version < "3.14" restriction is not blocking deployment
    assert '; python_version < "3.14"' not in content


def test_run_system_port_resolution_and_preflight(monkeypatch):
    import run_system
    from argparse import Namespace

    # 1. Flag port takes priority
    args1 = Namespace(port=9090, positional_port=8080, host="0.0.0.0", retrain=False, demo=False)
    assert run_system.resolve_port(args1) == 9090

    # 2. Positional port takes second priority
    args2 = Namespace(port=None, positional_port=8081, host="0.0.0.0", retrain=False, demo=False)
    assert run_system.resolve_port(args2) == 8081

    # 3. Environment variable PORT
    monkeypatch.setenv("PORT", "10000")
    args3 = Namespace(port=None, positional_port=None, host="0.0.0.0", retrain=False, demo=False)
    assert run_system.resolve_port(args3) == 10000

    # 4. Out-of-bounds port fallback
    args4 = Namespace(port=999999, positional_port=None, host="0.0.0.0", retrain=False, demo=False)
    assert run_system.resolve_port(args4) == 8080

    # 5. Pre-flight check passes
    assert run_system.validate_environment() is True


def test_render_yaml_persistent_disk_and_secrets():
    render_file = PROJECT_ROOT / "render.yaml"
    assert render_file.exists()
    content = render_file.read_text()

    assert "smart-traffic-persistent-disk" in content
    assert "mountPath: /var/data" in content
    assert "sizeGB: 10" in content
    assert "PERSISTENT_DATA_DIR" in content
    assert "API_KEY_TOMTOM" in content
    assert "API_KEY_GOOGLE_MAPS" in content
    assert "SECRET_KEY" in content
    assert "JWT_SECRET" in content
    assert "SECRETS_VAULT_KEY" in content


def test_vercel_json_functions_and_serverless_limits():
    vercel_file = PROJECT_ROOT / "vercel.json"
    assert vercel_file.exists()
    data = json.loads(vercel_file.read_text())

    assert "functions" in data
    fn_config = data["functions"].get("api/index.py", {})
    assert fn_config.get("maxDuration", 0) >= 30
    assert fn_config.get("memory", 0) >= 1024

    # Check api rewrite
    rewrites = data.get("rewrites", [])
    api_rewrite = any(r.get("source") == "/api/(.*)" and r.get("destination") == "/api/index.py" for r in rewrites)
    assert api_rewrite is True


def test_procfile_start_command():
    procfile = PROJECT_ROOT / "Procfile"
    assert procfile.exists()
    content = procfile.read_text().strip()
    assert "web: python3 run_system.py" in content or "web: python run_system.py" in content


def test_api_index_handler_import():
    import api.index as vercel_api
    assert hasattr(vercel_api, "handler")
    from app.server import TrafficAppServer
    assert issubclass(vercel_api.handler, TrafficAppServer)


def test_gitignore_and_dockerignore_exclusions():
    gitignore = (PROJECT_ROOT / ".gitignore").read_text()
    dockerignore = (PROJECT_ROOT / ".dockerignore").read_text()

    for item in [
        "traffic_system/artifacts/backups/*.json",
        "traffic_system/artifacts/.secrets.vault",
        "traffic_system/artifacts/sessions.json",
        "*.vault",
        "traffic_system/storage/videos/raw/*"
    ]:
        assert item in gitignore, f"Missing {item} in .gitignore"

    for item in [
        ".git",
        "tests/",
        "traffic_system/artifacts/.secrets.vault",
        "traffic_system/artifacts/backups/*.json",
        "traffic_system/storage/videos/raw/*"
    ]:
        assert item in dockerignore, f"Missing {item} in .dockerignore"


def test_license_third_party_notices():
    license_file = PROJECT_ROOT / "LICENSE"
    assert license_file.exists()
    content = license_file.read_text()

    assert "MIT License" in content
    assert "Ultralytics YOLO" in content
    assert "AGPL-3.0" in content
    assert "OpenCV" in content
    assert "XGBoost" in content
    assert "Scikit-Learn" in content


def test_readme_accuracy_and_discrepancies_resolved():
    readme_file = PROJECT_ROOT / "README.md"
    assert readme_file.exists()
    content = readme_file.read_text()

    # Outdated / misleading claims removed
    assert "10/10 Passing" not in content
    assert "Native TreeSHAP explainability" not in content
    assert "Zero Sampling Approximation" not in content
    assert "Multi-Class Softmax (0.82 ms)" not in content
    assert "Autonomous Spatio-Temporal Congestion Prediction & Intelligent Traffic Control System" not in content

    # Grounded reality present
    assert "Decision Tree Path Attribution" in content or "decision-tree path" in content.lower()
    assert "180" in content
    assert "Advisory" in content
