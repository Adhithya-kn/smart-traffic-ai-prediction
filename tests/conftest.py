# tests/conftest.py - Pytest Root Hook
# CRITICAL FOR MACOS APPLE SILICON: Pre-initialize YOLO model before XGBoost
# to prevent OpenMP symbol/thread collision deadlocks during test runs.
import os
import urllib.request
import pytest

try:
    from ultralytics import YOLO
    from traffic_system.config import BASE_DIR
    weights = BASE_DIR / "yolo11n.pt"
    if weights.exists():
        _warmup = YOLO(str(weights))
except Exception:
    pass


@pytest.fixture(autouse=True)
def prevent_unmocked_external_network_requests(request, monkeypatch):
    """
    In accordance with scientific testing governance:
    Hermetic and deterministic unit tests MUST NOT execute outbound network requests.
    Live external provider calls are permitted only for tests explicitly marked with
    @pytest.mark.integration AND with environment flag RUN_LIVE_API_TESTS=1.
    """
    is_live_integration = (
        request.node.get_closest_marker("integration") is not None
        and os.environ.get("RUN_LIVE_API_TESTS", "").lower() in ("1", "true", "yes")
    )
    if is_live_integration:
        return

    orig_urlopen = urllib.request.urlopen

    def hermetic_urlopen(req, *args, **kwargs):
        if hasattr(req, "full_url"):
            url = req.full_url
        elif hasattr(req, "get_full_url"):
            url = req.get_full_url()
        else:
            url = str(req)

        # Allow local test servers / loopback
        if "127.0.0.1" in url or "localhost" in url:
            return orig_urlopen(req, *args, **kwargs)

        raise RuntimeError(
            f"Blocked unmocked external network request to '{url}' during unit test execution! "
            f"All external providers (TomTom, Open-Meteo, Google Maps) must be mocked in unit tests. "
            f"For genuine live network tests, mark with @pytest.mark.integration and set RUN_LIVE_API_TESTS=1."
        )

    monkeypatch.setattr(urllib.request, "urlopen", hermetic_urlopen)
