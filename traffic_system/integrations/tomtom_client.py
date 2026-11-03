"""
traffic_system/integrations/tomtom_client.py - Hardened TomTom Traffic API Client
Retrieves real-time traffic flow segments and incident feeds for the Bengaluru Grid.
Features rate limiting, exponential backoff, timeout protection, error sanitization,
and strict secret masking.
"""

import os
import json
import time
import logging
import urllib.request
import urllib.error
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

        self.last_successful_retrieval: Optional[str] = None
        self.last_latency_ms: float = 0.0
        self.last_error: Optional[str] = None
        self._last_call_timestamp: float = 0.0
        self._min_interval: float = 0.35  # Token bucket pacing to prevent exceeding rate limits

    def set_api_key(self, api_key: str) -> None:
        """Dynamically updates the active TomTom API key."""
        self.api_key = str(api_key).strip()

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

    def _pace(self) -> None:
        """Paces API calls to enforce respectful QPS."""
        now = time.time()
        elapsed = now - self._last_call_timestamp
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call_timestamp = time.time()

    def _execute_request(self, url: str) -> Tuple[bool, Optional[Dict[str, Any]], int, str]:
        """
        Executes HTTP request with retries and exponential backoff.
        Returns (success, parsed_json, status_code, error_message).
        """
        self._pace()
        start = time.perf_counter()

        for attempt in range(1, self.max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "SmartTrafficAI-TomTomClient/2.0", "Accept": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    self.last_latency_ms = round((time.perf_counter() - start) * 1000, 2)
                    self.last_successful_retrieval = now_iso()
                    self.last_error = None
                    return True, data, resp.status, ""
            except urllib.error.HTTPError as e:
                self.last_latency_ms = round((time.perf_counter() - start) * 1000, 2)
                err_msg = f"HTTP {e.code}"
                if e.code == 403 or e.code == 401:
                    self.last_error = "Invalid or unauthorized TomTom API key."
                    return False, None, e.code, self.last_error
                if attempt == self.max_retries:
                    self.last_error = err_msg
                    return False, None, e.code, err_msg
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                self.last_latency_ms = round((time.perf_counter() - start) * 1000, 2)
                if attempt == self.max_retries:
                    self.last_error = "Network or timeout error contacting TomTom."
                    return False, None, 0, self.last_error
            time.sleep(0.3 * (2 ** (attempt - 1)))

        return False, None, 0, self.last_error or "Unknown error"

    def test_connection(self) -> Tuple[bool, str, float]:
        """
        Tests whether the TomTom API endpoint is reachable with current credentials.
        Returns (reachable, message, latency_ms).
        """
        if not self.is_configured():
            return False, "TomTom API key is not configured.", 0.0

        # Query a point in Central Bengaluru (M.G. Road)
        url = (
            f"{self.base_url}/traffic/services/4/flowSegmentData/relative0/10/json"
            f"?point=12.9756,77.6066&unit=KMPH&key={self.api_key}"
        )
        ok, data, code, err = self._execute_request(url)
        if ok and data:
            return True, "TomTom Traffic API is reachable and authenticated.", self.last_latency_ms
        return False, f"TomTom API test failed: {err} (HTTP {code})", self.last_latency_ms

    def get_flow_segment(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Retrieves real-time traffic flow data for given GPS coordinates."""
        if not self.is_configured():
            return None

        url = (
            f"{self.base_url}/traffic/services/4/flowSegmentData/relative0/10/json"
            f"?point={lat:.5f},{lon:.5f}&unit=KMPH&key={self.api_key}"
        )
        ok, data, _, _ = self._execute_request(url)
        if ok and data and "flowSegmentData" in data:
            return data["flowSegmentData"]
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
            f"?bbox={bbox}&fields={{incidents{{type,geometry{{type,coordinates}},properties{{iconCategory,magnitudeOfDelay,events{{description,code}}}}}}}}"
            f"&language=en-GB&key={self.api_key}"
        )
        ok, data, _, _ = self._execute_request(url)
        if ok and data and "incidents" in data:
            return data["incidents"]
        return []

    def get_status(self) -> Dict[str, Any]:
        """Provides status inspection without revealing secrets."""
        return {
            "configured": self.is_configured(),
            "masked_key": self.get_masked_key(),
            "last_successful_retrieval": self.last_successful_retrieval,
            "last_latency_ms": self.last_latency_ms,
            "last_error": self.last_error,
            "base_url": self.base_url
        }
