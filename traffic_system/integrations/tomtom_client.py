"""
traffic_system/integrations/tomtom_client.py - Hardened TomTom Traffic API Client
Retrieves real-time traffic flow segments and incident feeds for the Bengaluru Grid.
Features rate limiting, exponential backoff, timeout protection, error sanitization,
strict secret masking, and granular connectivity/provenance state tracking.
"""

import os
import json
import time
import socket
import logging
import threading
import urllib.request
import urllib.error
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, Any, Optional, Tuple, List

from traffic_system.config import (
    TOMTOM_API_KEY,
    TOMTOM_BASE_URL,
    TOMTOM_TIMEOUT_SECONDS,
    API_MAX_RETRIES
)
from traffic_system.core.time_utils import now_iso

logger = logging.getLogger("traffic_system.integrations.tomtom")


class TomTomClient:
    """
    Client for TomTom Traffic Flow and Incident Services.
    Zero raw API key leakage in responses, logs, or exceptions.
    Distinguishes configured, connection_tested, currently_reachable, and supplying_data states.
    Employs thread-safe token bucket pacing, bounded exponential backoff, and robust error classification.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = TOMTOM_TIMEOUT_SECONDS,
        max_retries: int = API_MAX_RETRIES
    ):
        self.api_key = (api_key if api_key is not None else TOMTOM_API_KEY).strip()
        self.base_url = (base_url or TOMTOM_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

        # Provenance and connectivity states
        self.connection_tested: bool = False
        self.currently_reachable: bool = False
        self.supplying_data: bool = False

        self.last_attempted_request: Optional[str] = None
        self.last_successful_retrieval: Optional[str] = None
        self.last_observation_time: Optional[str] = None
        self.last_latency_ms: float = 0.0
        self.last_error: Optional[str] = None

        # Thread-safe Token Bucket Rate Limiter (Capacity: 5, Rate: 5 tokens/s)
        self._lock = threading.Lock()
        self._rate_limit = 5.0
        self._capacity = 5.0
        self._tokens = 5.0
        self._last_token_update = time.monotonic()

    def set_api_key(self, api_key: str) -> None:
        """Dynamically updates active TomTom API key and invalidates state/caches."""
        with self._lock:
            self.api_key = str(api_key).strip()
            # Invalidate connection and supply states on credential alteration
            self.connection_tested = False
            self.currently_reachable = False
            self.supplying_data = False
            self.last_successful_retrieval = None
            self.last_error = None

    def is_configured(self) -> bool:
        """Returns True if a plausible non-empty TomTom key is configured."""
        return bool(self.api_key and len(self.api_key) >= 12)

    def get_masked_key(self) -> str:
        """Returns safely masked key string (e.g. '****7f4a') without disclosing secrets."""
        if not self.api_key:
            return ""
        if len(self.api_key) <= 6:
            return "******"
        return f"****{self.api_key[-4:]}"

    def get_status_code(self) -> str:
        """Derives explicit state identifier."""
        if not self.is_configured():
            return "UNCONFIGURED"
        if self.supplying_data and self.currently_reachable:
            return "LIVE_SUPPLYING_DATA"
        if self.currently_reachable:
            return "CONNECTED_NO_DATA"
        if self.connection_tested and not self.currently_reachable:
            return "CONFIGURED_UNREACHABLE"
        return "CONFIGURED_UNTESTED"

    def _acquire_token(self) -> None:
        """Thread-safe token bucket acquiring 1 token with micro-sleep if empty."""
        while True:
            with self._lock:
                now = time.monotonic()
                delta = now - self._last_token_update
                self._last_token_update = now
                self._tokens = min(self._capacity, self._tokens + delta * self._rate_limit)

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                # Calculate sleep duration until 1 token is available
                needed = 1.0 - self._tokens
                sleep_sec = min(0.2, needed / self._rate_limit)
            time.sleep(sleep_sec)

    def _sanitize_error(self, message: str) -> str:
        """Strips raw API key from error strings before emission."""
        if self.api_key and self.api_key in message:
            return message.replace(self.api_key, self.get_masked_key())
        return message

    def _execute_request(self, url: str) -> Tuple[bool, Optional[Dict[str, Any]], int, str]:
        """
        Executes HTTP request with bounded retries, exponential backoff, and distinct timestamp tracking.
        Handles HTTP 401, 403, 429, and 5xx responses with specific retry policies.
        Returns (success, parsed_json, status_code, error_message).
        """
        self._acquire_token()
        self.connection_tested = True
        self.last_attempted_request = now_iso()
        start = time.perf_counter()

        for attempt in range(1, self.max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "SmartTrafficAI-TomTomClient/2.0",
                        "Accept": "application/json"
                    }
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    self.last_latency_ms = round((time.perf_counter() - start) * 1000, 2)
                    self.last_successful_retrieval = now_iso()
                    self.currently_reachable = True
                    self.last_error = None

                    # Extract HTTP Date header as provider timestamp fallback if available
                    date_header = resp.headers.get("Date")
                    if date_header:
                        try:
                            dt = parsedate_to_datetime(date_header)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            self._last_http_date = dt.isoformat()
                        except Exception:
                            self._last_http_date = None
                    else:
                        self._last_http_date = None

                    return True, data, resp.status, ""
            except urllib.error.HTTPError as e:
                self.last_latency_ms = round((time.perf_counter() - start) * 1000, 2)
                self.currently_reachable = False

                # 401 / 403: Authentication / Permission failure -> fail immediately without retry
                if e.code in (401, 403):
                    self.supplying_data = False
                    self.last_error = self._sanitize_error(f"Invalid or unauthorized TomTom API key (HTTP {e.code}).")
                    return False, None, e.code, self.last_error

                # 429: Rate Limit Exceeded -> check Retry-After header with bounded backoff
                if e.code == 429:
                    self.last_error = "TomTom API rate limit exceeded (HTTP 429)."
                    if attempt == self.max_retries:
                        self.supplying_data = False
                        return False, None, e.code, self.last_error
                    retry_header = e.headers.get("Retry-After") if hasattr(e, "headers") and e.headers else None
                    if retry_header and retry_header.isdigit():
                        backoff = min(float(retry_header), 3.0)
                    else:
                        backoff = min(0.5 * (2 ** (attempt - 1)), 3.0)
                    time.sleep(backoff)
                    continue

                # 5xx: Server errors (500, 502, 503, 504) -> retry with bounded backoff
                if 500 <= e.code <= 599:
                    self.last_error = f"TomTom API server error (HTTP {e.code})."
                    if attempt == self.max_retries:
                        self.supplying_data = False
                        return False, None, e.code, self.last_error
                    backoff = min(0.3 * (2 ** (attempt - 1)), 3.0)
                    time.sleep(backoff)
                    continue

                # Other 4xx client errors (e.g. 400, 404) -> do not retry
                self.last_error = self._sanitize_error(f"TomTom API client error (HTTP {e.code}).")
                self.supplying_data = False
                return False, None, e.code, self.last_error

            except (json.JSONDecodeError, ValueError):
                self.last_latency_ms = round((time.perf_counter() - start) * 1000, 2)
                self.currently_reachable = False
                self.supplying_data = False
                self.last_error = "Malformed JSON received from TomTom API."
                return False, None, 502, self.last_error

            except (urllib.error.URLError, TimeoutError, OSError, socket.timeout):
                self.last_latency_ms = round((time.perf_counter() - start) * 1000, 2)
                self.currently_reachable = False
                if attempt == self.max_retries:
                    self.supplying_data = False
                    self.last_error = "Network or timeout error contacting TomTom."
                    return False, None, 0, self.last_error
                backoff = min(0.3 * (2 ** (attempt - 1)), 3.0)
                time.sleep(backoff)

        return False, None, 0, self.last_error or "Unknown error"

    def test_connection(self) -> Tuple[bool, str, float]:
        """
        Tests whether the TomTom API endpoint is reachable with current credentials.
        Returns (reachable, message, latency_ms).
        """
        if not self.is_configured():
            self.connection_tested = True
            self.currently_reachable = False
            self.supplying_data = False
            return False, "TomTom API key is not configured.", 0.0

        # Query a point in Central Bengaluru (M.G. Road)
        url = (
            f"{self.base_url}/traffic/services/4/flowSegmentData/relative0/10/json"
            f"?point=12.9756,77.6066&unit=KMPH&key={self.api_key}"
        )
        ok, data, code, err = self._execute_request(url)
        if ok and data:
            self.currently_reachable = True
            return True, "TomTom Traffic API is reachable and authenticated.", self.last_latency_ms
        self.currently_reachable = False
        return False, f"TomTom API test failed: {err} (HTTP {code})", self.last_latency_ms

    def get_flow_segment(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """
        Retrieves real-time traffic flow data for given GPS coordinates.
        Speeds are in km/h ('unit=KMPH').
        Validates structure and separates observation time from retrieval time.
        """
        if not self.is_configured():
            self.supplying_data = False
            return None

        # Validate coordinate boundaries for sanity
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            logger.warning("Invalid coordinate passed to get_flow_segment: lat=%s, lon=%s", lat, lon)
            return None

        url = (
            f"{self.base_url}/traffic/services/4/flowSegmentData/relative0/10/json"
            f"?point={lat:.5f},{lon:.5f}&unit=KMPH&key={self.api_key}"
        )
        ok, data, _, _ = self._execute_request(url)
        if ok and data and "flowSegmentData" in data:
            flow = data["flowSegmentData"]
            if not isinstance(flow, dict):
                self.supplying_data = False
                return None

            # Validate that currentSpeed and freeFlowSpeed are present and numeric
            try:
                cur_spd = float(flow.get("currentSpeed", -1))
                ff_spd = float(flow.get("freeFlowSpeed", -1))
                if cur_spd < 0 or ff_spd < 0:
                    logger.warning("TomTom returned non-positive flow speeds: current=%s, freeFlow=%s", cur_spd, ff_spd)
            except (ValueError, TypeError):
                logger.warning("TomTom returned non-numeric speeds: %s", flow)
                self.supplying_data = False
                return None

            self.supplying_data = True
            # Extract provider observation timestamp if present (never treat @version as timestamp)
            provider_ts = flow.get("timestamp") or flow.get("observationTime")
            if provider_ts and str(provider_ts).strip() and not str(provider_ts).startswith("1."):
                self.last_observation_time = str(provider_ts).strip()
            elif getattr(self, "_last_http_date", None):
                self.last_observation_time = self._last_http_date
            else:
                self.last_observation_time = self.last_successful_retrieval or now_iso()

            flow["_observation_time"] = self.last_observation_time
            flow["_retrieved_time"] = self.last_successful_retrieval or now_iso()
            return flow

        self.supplying_data = False
        return None

    def get_incident_details(
        self,
        min_lat: float = 12.80,
        min_lon: float = 77.50,
        max_lat: float = 13.10,
        max_lon: float = 77.75
    ) -> List[Dict[str, Any]]:
        """Retrieves raw incident records for the bounding box."""
        if not self.is_configured():
            return []

        bbox = f"{min_lon:.4f},{min_lat:.4f},{max_lon:.4f},{max_lat:.4f}"
        url = (
            f"{self.base_url}/traffic/services/5/incidentDetails"
            f"?bbox={bbox}&fields={{incidents{{type,geometry{{type,coordinates}},properties{{id,iconCategory,magnitudeOfDelay,startTime,endTime,delay,events{{description,code}}}}}}}}"
            f"&language=en-GB&key={self.api_key}"
        )
        ok, data, _, _ = self._execute_request(url)
        if ok and data and "incidents" in data:
            incidents = data["incidents"]
            if isinstance(incidents, list):
                self.supplying_data = True
                return incidents
        return []

    def get_status(self) -> Dict[str, Any]:
        """Provides status inspection without revealing secrets."""
        return {
            "provider": "TomTom Traffic",
            "configured": self.is_configured(),
            "connection_tested": self.connection_tested,
            "currently_reachable": self.currently_reachable,
            "supplying_data": self.supplying_data,
            "status_code": self.get_status_code(),
            "masked_key": self.get_masked_key(),
            "last_attempted_request": self.last_attempted_request,
            "last_successful_retrieval": self.last_successful_retrieval,
            "last_observation_time": self.last_observation_time,
            "last_latency_ms": self.last_latency_ms,
            "last_error": self.last_error,
            "base_url": self.base_url
        }
