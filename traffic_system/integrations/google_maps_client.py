"""
traffic_system/integrations/google_maps_client.py - Google Maps Platform Client
Integrates Google Maps JavaScript, Geocoding, and Places APIs for Bengaluru metropolitan grid.
Features rate limiting, exponential backoff, timeout protection, error sanitization,
strict secret masking, and distinct connectivity/provenance tracking.
"""

import os
import json
import time
import socket
import logging
import threading
import urllib.parse
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Tuple, List

from traffic_system.config import (
    GOOGLE_MAPS_API_KEY,
    GOOGLE_MAPS_BASE_URL,
    GOOGLE_MAPS_TIMEOUT_SECONDS,
    API_MAX_RETRIES
)
from traffic_system.core.time_utils import now_iso

logger = logging.getLogger("traffic_system.integrations.google_maps")


class GoogleMapsClient:
    """
    Client for Google Maps Platform Services:
    1. Geocoding API: Address/coordinate resolution and reverse geocoding.
    2. Places API (Find Place / Text Search): Landmark, corridor, and transit hub search.
    3. Directions API: Macroscopic routing, distance, duration in traffic, and polyline geometry.
    4. Maps JavaScript API: Frontend rendering layer (backend preserves key isolation).

    Features thread-safe token-bucket pacing, key masking, restriction diagnosis,
    quota error categorization, and bounded exponential backoff.
    """
    REQUIRED_SERVICES = [
        "Geocoding API",
        "Places API",
        "Directions API",
        "Maps JavaScript API"
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = GOOGLE_MAPS_TIMEOUT_SECONDS,
        max_retries: int = API_MAX_RETRIES
    ):
        self.api_key = (api_key if api_key is not None else GOOGLE_MAPS_API_KEY).strip()
        self.base_url = (base_url or GOOGLE_MAPS_BASE_URL).rstrip("/")
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
        self.last_restriction_error: Optional[str] = None

        # Thread-safe Token Bucket Rate Limiter (Capacity: 10, Rate: 5 tokens/s)
        self._lock = threading.Lock()
        self._rate_limit = 5.0
        self._capacity = 10.0
        self._tokens = 10.0
        self._last_token_update = time.monotonic()

    def set_api_key(self, api_key: str) -> None:
        """Dynamically updates active Google Maps API key and invalidates state."""
        with self._lock:
            self.api_key = str(api_key).strip()
            self.connection_tested = False
            self.currently_reachable = False
            self.supplying_data = False
            self.last_successful_retrieval = None
            self.last_error = None
            self.last_restriction_error = None

    def is_configured(self) -> bool:
        """Returns True if a valid Google Maps key is configured."""
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
        Diagnoses Google Maps Platform status codes: OK, ZERO_RESULTS, OVER_QUERY_LIMIT, REQUEST_DENIED, etc.
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
                        "User-Agent": "SmartTrafficAI-GoogleMapsClient/2.0",
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

                    # Check Google Maps Platform JSON-level status
                    api_status = data.get("status", "OK")
                    if api_status in ("OK", "ZERO_RESULTS"):
                        return True, data, resp.status, ""

                    # Specific Google Error Diagnoses
                    err_msg = data.get("error_message", api_status)
                    sanitized_err = self._sanitize_error(err_msg)

                    if api_status == "REQUEST_DENIED":
                        self.currently_reachable = False
                        self.supplying_data = False
                        if "referer restrictions" in sanitized_err.lower():
                            self.last_restriction_error = "HTTP_REFERER_RESTRICTION_ERROR: Backend server requests cannot use keys restricted by HTTP referrer."
                        elif "not authorized" in sanitized_err.lower():
                            self.last_restriction_error = "API_SERVICE_NOT_ENABLED: The requested Google Maps API service is not enabled in Google Cloud Console."
                        elif "billing" in sanitized_err.lower():
                            self.last_restriction_error = "BILLING_NOT_ACTIVE: Google Cloud project requires an active billing account."
                        else:
                            self.last_restriction_error = f"REQUEST_DENIED: {sanitized_err}"

                        self.last_error = self.last_restriction_error
                        return False, data, 403, self.last_error

                    if api_status == "OVER_QUERY_LIMIT":
                        self.currently_reachable = False
                        self.last_error = f"Google Maps quota or billing limit exceeded (OVER_QUERY_LIMIT): {sanitized_err}"
                        if attempt == self.max_retries:
                            return False, data, 429, self.last_error
                        time.sleep(min(1.0 * (2 ** (attempt - 1)), 3.0))
                        continue

                    self.last_error = f"Google Maps Platform error ({api_status}): {sanitized_err}"
                    return False, data, 400, self.last_error

            except urllib.error.HTTPError as e:
                self.last_latency_ms = round((time.perf_counter() - start) * 1000, 2)
                self.currently_reachable = False

                if e.code in (401, 403):
                    self.supplying_data = False
                    self.last_error = self._sanitize_error(f"Invalid or unauthorized Google Maps credentials (HTTP {e.code}).")
                    return False, None, e.code, self.last_error

                if e.code == 429:
                    self.last_error = "Google Maps API rate limit exceeded (HTTP 429)."
                    if attempt == self.max_retries:
                        self.supplying_data = False
                        return False, None, e.code, self.last_error
                    time.sleep(min(1.0 * (2 ** (attempt - 1)), 3.0))
                    continue

                if 500 <= e.code <= 599:
                    self.last_error = f"Google Maps API server error (HTTP {e.code})."
                    if attempt == self.max_retries:
                        self.supplying_data = False
                        return False, None, e.code, self.last_error
                    time.sleep(min(0.4 * (2 ** (attempt - 1)), 3.0))
                    continue

                self.last_error = self._sanitize_error(f"Google Maps API HTTP error {e.code}.")
                self.supplying_data = False
                return False, None, e.code, self.last_error

            except (json.JSONDecodeError, ValueError):
                self.last_latency_ms = round((time.perf_counter() - start) * 1000, 2)
                self.currently_reachable = False
                self.supplying_data = False
                self.last_error = "Malformed JSON received from Google Maps API."
                return False, None, 502, self.last_error

            except (urllib.error.URLError, TimeoutError, OSError, socket.timeout):
                self.last_latency_ms = round((time.perf_counter() - start) * 1000, 2)
                self.currently_reachable = False
                if attempt == self.max_retries:
                    self.supplying_data = False
                    self.last_error = "Network or timeout error contacting Google Maps API."
                    return False, None, 0, self.last_error
                time.sleep(min(0.3 * (2 ** (attempt - 1)), 3.0))

        return False, None, 0, self.last_error or "Unknown error"

    def test_connection(self) -> Tuple[bool, str, float]:
        """
        Tests whether the Google Maps Platform is reachable and authenticated with current credentials.
        Returns (reachable, message, latency_ms).
        """
        if not self.is_configured():
            self.connection_tested = True
            self.currently_reachable = False
            self.supplying_data = False
            return False, "Google Maps API key is not configured.", 0.0

        # Query central Bengaluru coordinate (Vidhana Soudha / MG Road)
        encoded_address = urllib.parse.quote("Bengaluru, Karnataka, India")
        url = f"{self.base_url}/maps/api/geocode/json?address={encoded_address}&key={self.api_key}"
        ok, data, code, err = self._execute_request(url)
        if ok and data:
            status = data.get("status", "")
            if status in ("OK", "ZERO_RESULTS"):
                self.currently_reachable = True
                return True, "Google Maps API is reachable and authenticated.", self.last_latency_ms

        self.currently_reachable = False
        return False, f"Google Maps API test failed: {err or self.last_error} (HTTP {code})", self.last_latency_ms

    def search_places(self, query: str) -> List[Dict[str, Any]]:
        """
        Searches Google Geocoding API for place matches within the Bengaluru bounding box.
        Returns normalized list of candidate locations.
        """
        if not self.is_configured() or not query.strip():
            self.supplying_data = False
            return []

        clean_query = query.strip()
        if "bengaluru" not in clean_query.lower() and "bangalore" not in clean_query.lower():
            clean_query = f"{clean_query}, Bengaluru, Karnataka"

        encoded = urllib.parse.quote(clean_query)
        # Bounding box for greater Bengaluru metropolitan area
        url = (
            f"{self.base_url}/maps/api/geocode/json?address={encoded}"
            f"&bounds=12.75,77.40|13.20,77.85&key={self.api_key}"
        )
        ok, data, _, _ = self._execute_request(url)
        results = []
        if ok and data and "results" in data:
            for item in data["results"][:5]:
                loc = item.get("geometry", {}).get("location", {})
                if "lat" in loc and "lng" in loc:
                    results.append({
                        "name": item.get("formatted_address", query),
                        "lat": loc["lat"],
                        "lon": loc["lng"],
                        "place_id": item.get("place_id", ""),
                        "source": "Google Maps Geocoding API"
                    })
            if results:
                self.supplying_data = True
                self.last_observation_time = now_iso()
                return results

        self.supplying_data = False
        return results

    def find_place(self, query: str, location_bias: Optional[Tuple[float, float]] = None) -> List[Dict[str, Any]]:
        """
        Uses Google Places API (Find Place from Text) to discover points of interest,
        arterial junctions, and commercial establishments in Bengaluru.
        """
        if not self.is_configured() or not query.strip():
            return []

        clean_input = urllib.parse.quote(query.strip())
        bias_param = ""
        if location_bias:
            bias_param = f"&locationbias=circle:15000@{location_bias[0]:.4f},{location_bias[1]:.4f}"
        else:
            bias_param = "&locationbias=circle:25000@12.9716,77.5946"  # Center of Bengaluru

        url = (
            f"{self.base_url}/maps/api/place/findplacefromtext/json"
            f"?input={clean_input}&inputtype=textquery"
            f"&fields=place_id,formatted_address,name,geometry,types"
            f"{bias_param}&key={self.api_key}"
        )
        ok, data, _, _ = self._execute_request(url)
        results = []
        if ok and data and "candidates" in data:
            for item in data["candidates"][:5]:
                loc = item.get("geometry", {}).get("location", {})
                if "lat" in loc and "lng" in loc:
                    results.append({
                        "name": item.get("name", query),
                        "formatted_address": item.get("formatted_address", ""),
                        "lat": loc["lat"],
                        "lon": loc["lng"],
                        "place_id": item.get("place_id", ""),
                        "types": item.get("types", []),
                        "source": "Google Places API"
                    })
            if results:
                self.supplying_data = True
                self.last_observation_time = now_iso()
                return results

        # Fallback to Geocoding if Places API is not enabled or returns no candidates
        return self.search_places(query)

    def get_directions(
        self,
        origin: Tuple[float, float] | str,
        destination: Tuple[float, float] | str,
        departure_time: str = "now"
    ) -> Optional[Dict[str, Any]]:
        """
        Queries Google Directions API for macroscopic route geometry, duration in traffic,
        and turn-by-turn guidance across the Bengaluru urban grid.
        """
        if not self.is_configured():
            return None

        orig_str = f"{origin[0]:.5f},{origin[1]:.5f}" if isinstance(origin, (tuple, list)) else urllib.parse.quote(str(origin))
        dest_str = f"{destination[0]:.5f},{destination[1]:.5f}" if isinstance(destination, (tuple, list)) else urllib.parse.quote(str(destination))

        url = (
            f"{self.base_url}/maps/api/directions/json"
            f"?origin={orig_str}&destination={dest_str}"
            f"&departure_time={departure_time}&traffic_model=best_guess"
            f"&mode=driving&key={self.api_key}"
        )
        ok, data, _, _ = self._execute_request(url)
        if ok and data and "routes" in data and len(data["routes"]) > 0:
            route = data["routes"][0]
            leg = route.get("legs", [{}])[0]
            self.supplying_data = True
            self.last_observation_time = now_iso()
            return {
                "summary": route.get("summary", ""),
                "overview_polyline": route.get("overview_polyline", {}).get("points", ""),
                "distance_meters": leg.get("distance", {}).get("value", 0),
                "distance_text": leg.get("distance", {}).get("text", ""),
                "duration_seconds": leg.get("duration", {}).get("value", 0),
                "duration_text": leg.get("duration", {}).get("text", ""),
                "duration_in_traffic_seconds": leg.get("duration_in_traffic", {}).get("value", leg.get("duration", {}).get("value", 0)),
                "duration_in_traffic_text": leg.get("duration_in_traffic", {}).get("text", leg.get("duration", {}).get("text", "")),
                "start_location": leg.get("start_location", {}),
                "end_location": leg.get("end_location", {}),
                "source": "Google Directions API"
            }

        return None

    def get_status(self) -> Dict[str, Any]:
        """Provides status inspection without revealing secrets."""
        return {
            "provider": "Google Maps Platform",
            "configured": self.is_configured(),
            "connection_tested": self.connection_tested,
            "currently_reachable": self.currently_reachable,
            "supplying_data": self.supplying_data,
            "status_code": self.get_status_code(),
            "masked_key": self.get_masked_key(),
            "required_services": self.REQUIRED_SERVICES,
            "last_attempted_request": self.last_attempted_request,
            "last_successful_retrieval": self.last_successful_retrieval,
            "last_observation_time": self.last_observation_time,
            "last_latency_ms": self.last_latency_ms,
            "last_error": self.last_error,
            "last_restriction_error": self.last_restriction_error,
            "base_url": self.base_url
        }
