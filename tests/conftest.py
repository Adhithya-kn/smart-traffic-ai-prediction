# tests/conftest.py - Pytest root hook
#
# Responsibilities:
#   1. Hermetic runtime-state isolation: redirect every mutable runtime path
#      (artifacts, user/session/event/job ledgers, video storage) into a
#      throwaway directory BEFORE traffic_system.config is imported. The test
#      suite must never modify git-tracked runtime files or the developer's
#      real storage directories.
#   2. macOS/Apple Silicon guard: pre-initialize YOLO before XGBoost/OpenMP to
#      prevent OpenMP symbol/thread-collision deadlocks during test runs.
#   3. Hermetic network guard: block unmocked outbound HTTP requests unless a
#      test is explicitly marked `integration` AND RUN_LIVE_API_TESTS=1.
import atexit
import os
import shutil
import tempfile
import urllib.request
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# 1. Isolate runtime state BEFORE importing traffic_system.config.
# traffic_system.config resolves ARTIFACTS_DIR / USERS_DB_PATH / EVENTS_DB_PATH /
# VIDEO_STORAGE_DIR once at import time. PERSISTENT_DATA_DIR is the supported
# over-the-top override, and it takes effect only if the directory exists.
# ---------------------------------------------------------------------------
_TEST_DATA_ROOT = Path(tempfile.mkdtemp(prefix="dp01_pytest_data_")).resolve()
os.environ["PERSISTENT_DATA_DIR"] = str(_TEST_DATA_ROOT)
os.environ["RUNTIME_DATA_DIR"] = str(_TEST_DATA_ROOT / "runtime")
os.environ.setdefault("YOLO_CONFIG_DIR", str(_TEST_DATA_ROOT / "ultralytics"))
atexit.register(shutil.rmtree, str(_TEST_DATA_ROOT), True)

# ---------------------------------------------------------------------------
# 2. Import config only after the overrides are in place, then verify they took
# effect. Fail loudly instead of silently writing into the repository.
# ---------------------------------------------------------------------------
from traffic_system.config import ARTIFACTS_DIR, BASE_DIR, USERS_DB_PATH  # noqa: E402

_expected_artifacts = (_TEST_DATA_ROOT / "artifacts").resolve()
if Path(ARTIFACTS_DIR).resolve() != _expected_artifacts or Path(USERS_DB_PATH).resolve().parent == (
    BASE_DIR / "traffic_system" / "artifacts"
).resolve():
    raise RuntimeError(
        "tests/conftest.py could not isolate runtime state: traffic_system.config "
        f"was imported before PERSISTENT_DATA_DIR/RUNTIME_DATA_DIR were set "
        f"(ARTIFACTS_DIR={ARTIFACTS_DIR}, USERS_DB_PATH={USERS_DB_PATH}). "
        "tests/conftest.py must be the first conftest loaded; run pytest from the repository root."
    )

try:
    from ultralytics import YOLO

    weights = BASE_DIR / "yolo11n.pt"
    if weights.exists():
        _warmup = YOLO(str(weights))
except Exception:
    pass


@pytest.fixture(scope="session", autouse=True)
def isolated_runtime_state():
    """Session-scoped temp data root, removed after the last test."""
    yield _TEST_DATA_ROOT
    shutil.rmtree(_TEST_DATA_ROOT, ignore_errors=True)


def pytest_report_header(config):
    return f"isolated runtime data root: {_TEST_DATA_ROOT}"


# ---------------------------------------------------------------------------
# 3. Hermetic network guard.
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# 4. Deterministic, repo-independent runtime ledgers for tests.
# The application seeds its mutable ledgers from tracked artifacts in normal use;
# tests must be reproducible even after those artifacts are untracked. This
# session-scoped fixture immediately overwrites the isolated event ledger with
# the committed test fixture (EVT_001 unverified seed + verified municipal events).
# ---------------------------------------------------------------------------
_TEST_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def seed_isolated_runtime_ledgers(isolated_runtime_state):
    from traffic_system.config import EVENTS_DB_PATH

    event_seed = _TEST_FIXTURES_DIR / "seed_events.json"
    if event_seed.exists():
        shutil.copyfile(event_seed, EVENTS_DB_PATH)
    yield
