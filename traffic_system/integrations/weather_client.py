"""
traffic_system/integrations/weather_client.py - Meteorological Data Client
Retrieves real-time atmospheric data via Open-Meteo forecast API for the Bengaluru metropolitan region.
Maintains strict separation between live data, cached API responses, and calibrated historical baselines.
"""

import os
import json
import time
import socket
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Tuple

from traffic_system.config import (
    WEATHER_API_KEY,
    WEATHER_BASE_URL,
    WEATHER_TIMEOUT_SECONDS,
    API_CACHE_TTL_SECONDS,
    API_MAX_RETRIES
)
from traffic_system.core.time_utils import now_iso
from traffic_system.core.entities import DataProvenance

logger = logging.getLogger("traffic_system.integrations.weather")


class WeatherClient:
    """
    Client for Open-Meteo Weather API.
    Provides meteorological factors (temperature, precipitation, condition, fog/rain).
    Distinguishes configured, connection_tested, currently_reachable, and supplying_data states.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = WEATHER_TIMEOUT_SECONDS,
        cache_ttl: float = API_CACHE_TTL_SECONDS,
        max_retries: int = API_MAX_RETRIES
    ):
        self.api_key = (api_key if api_key is not None else WEATHER_API_KEY).strip()
        self.base_url = (base_url or WEATHER_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self.max_retries = max_retries

        # Caching layer
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: float = 0.0

        # Provenance and connectivity states
        self.connection_tested: bool = False
        self.currently_reachable: bool = False
        self.supplying_data: bool = False

        self.last_attempted_request: Optional[str] = None
        self.last_successful_retrieval: Optional[str] = None
        self.last_observation_time: Optional[str] = None
        self.last_latency_ms: float = 0.0
        self.last_error: Optional[str] = None

    def set_config(self, api_key: Optional[str] = None, base_url: Optional[str] = None) -> None:
        """Dynamically configures weather provider attributes and flushes caches."""
        if api_key is not None:
            self.api_key = str(api_key).strip()
        if base_url is not None:
            self.base_url = str(base_url).rstrip("/")
        # Invalidate cache and status flags on reconfiguration
        self._cache = None
        self._cache_timestamp = 0.0
        self.connection_tested = False
        self.currently_reachable = False
        self.supplying_data = False
        self.last_successful_retrieval = None
        self.last_error = None

    def is_configured(self) -> bool:
        """Open-Meteo requires no mandatory key, so base service is always configured."""
        return bool(self.base_url)

    def get_masked_key(self) -> str:
        """Returns masked API key representation."""
        if not self.api_key or self.api_key == "none_required":
            return "none_required"
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

    def _execute_request(self, url: str) -> Tuple[bool, Optional[Dict[str, Any]], int, str]:
        self.connection_tested = True
        self.last_attempted_request = now_iso()
        start = time.perf_counter()

        for attempt in range(1, self.max_retries + 1):
            try:
                headers = {
                    "User-Agent": "SmartTrafficAI-WeatherClient/2.0",
                    "Accept": "application/json"
                }
                if self.api_key and self.api_key != "none_required":
                    headers["X-Api-Key"] = self.api_key
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    self.last_latency_ms = round((time.perf_counter() - start) * 1000, 2)
                    self.last_successful_retrieval = now_iso()
                    self.currently_reachable = True
                    self.last_error = None
                    return True, data, resp.status, ""
            except urllib.error.HTTPError as e:
                self.last_latency_ms = round((time.perf_counter() - start) * 1000, 2)
                self.currently_reachable = False
                if e.code in (401, 403):
                    self.last_error = "Invalid or unauthorized weather service credentials."
                    return False, None, e.code, self.last_error
                if e.code == 429:
                    self.last_error = "Open-Meteo weather API rate limit exceeded (HTTP 429)."
                    if attempt == self.max_retries:
                        return False, None, e.code, self.last_error
                else:
                    self.last_error = f"Weather API HTTP error {e.code}."
                    if attempt == self.max_retries:
                        return False, None, e.code, self.last_error
            except (json.JSONDecodeError, ValueError) as e:
                self.last_latency_ms = round((time.perf_counter() - start) * 1000, 2)
                self.currently_reachable = False
                self.last_error = "Malformed JSON received from weather service."
                return False, None, 502, self.last_error
            except (urllib.error.URLError, TimeoutError, OSError, socket.timeout) as e:
                self.last_latency_ms = round((time.perf_counter() - start) * 1000, 2)
                self.currently_reachable = False
                if attempt == self.max_retries:
                    self.last_error = "Network or timeout error contacting weather service."
                    return False, None, 0, self.last_error

            time.sleep(0.3 * (2 ** (attempt - 1)))

        return False, None, 0, self.last_error or "Unknown error"

    def test_connection(self) -> Tuple[bool, str, float]:
        """Tests whether the Open-Meteo API endpoint is reachable."""
        url = (
            f"{self.base_url}?latitude=12.9716&longitude=77.5946"
            f"&current=temperature_2m,precipitation,weather_code&timezone=Asia%2FKolkata"
        )
        ok, data, code, err = self._execute_request(url)
        if ok and data and "current" in data:
            self.currently_reachable = True
            return True, "Open-Meteo Weather API is reachable and responsive.", self.last_latency_ms
        self.currently_reachable = False
        return False, f"Weather API test failed: {err} (HTTP {code})", self.last_latency_ms

    def get_weather(self, lat: float = 12.9716, lon: float = 77.5946, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Retrieves weather observation with TTL caching and robust fallback semantics.
        Strictly categorizes and tags live data, cached API responses, stale responses, and baseline fallbacks.
        Validates GPS coordinate bounds and payload fields.
        """
        # 1. Validate coordinate boundaries
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            raise ValueError(f"Invalid GPS coordinates: lat={lat}, lon={lon}. Coordinates must be valid geographic values.")

        now = time.time()
        # 2. Return unexpired cached response if available
        if not force_refresh and self._cache and (now - self._cache_timestamp) < self.cache_ttl:
            cached = dict(self._cache)
            cached["is_live"] = False
            cached["is_cached"] = True
            cached["is_stale"] = False
            cached["is_historical_fallback"] = False
            cached["source"] = "Open-Meteo Live API (Cached)"
            cached["provenance"] = DataProvenance.CACHED_API_RESPONSE.value
            return cached

        # 3. Attempt live query to Open-Meteo
        url = (
            f"{self.base_url}?latitude={lat:.4f}&longitude={lon:.4f}"
            f"&current=temperature_2m,precipitation,weather_code,wind_speed_10m&timezone=Asia%2FKolkata"
        )

        ok, raw, _, _ = self._execute_request(url)
        if ok and raw and isinstance(raw.get("current"), dict):
            cur = raw["current"]
            try:
                precip = float(cur.get("precipitation", 0.0))
                temp = float(cur.get("temperature_2m", 27.0))
                wind = float(cur.get("wind_speed_10m", 12.0))
                code = int(cur.get("weather_code", 1))
            except (ValueError, TypeError):
                precip, temp, wind, code = 0.0, 27.0, 12.0, 1

            cond = (
                "Rainy" if (precip > 0.2 or code in [51, 53, 55, 61, 63, 65, 80, 81, 82])
                else "Foggy" if code in [45, 48]
                else "Overcast" if code in [2, 3]
                else "Clear"
            )

            # Use actual provider observation timestamp if available
            provider_time = str(cur.get("time", "")).strip()
            obs_time = provider_time if provider_time else now_iso()
            self.last_observation_time = obs_time

            reading = {
                "condition": cond,
                "temperature": temp,
                "precipitation_mm": precip,
                "wind_speed_kmh": wind,
                "weather_code": code,
                "source": "Open-Meteo Live API",
                "is_live": True,
                "is_cached": False,
                "is_stale": False,
                "is_historical_fallback": False,
                "provenance": DataProvenance.OPEN_METEO_LIVE_API.value,
                "observation_time": obs_time,
                "request_time": self.last_attempted_request,
                "retrieved_time": now_iso()
            }
            self.supplying_data = True
            self._cache = dict(reading)
            self._cache_timestamp = now
            return reading

        # 4. If live request failed, check if previous cache exists and mark it as stale
        self.supplying_data = False
        if self._cache is not None:
            stale_cached = dict(self._cache)
            stale_cached["is_live"] = False
            stale_cached["is_cached"] = True
            stale_cached["is_stale"] = True
            stale_cached["is_historical_fallback"] = False
            stale_cached["source"] = "Open-Meteo Live API (Stale Cache)"
            stale_cached["provenance"] = DataProvenance.CACHED_API_RESPONSE.value
            return stale_cached

        # 5. Fallback calibrated baseline when offline/sandboxed (never report as live)
        baseline_reading = {
            "condition": "Clear",
            "temperature": 27.5,
            "precipitation_mm": 0.0,
            "wind_speed_kmh": 10.5,
            "weather_code": 1,
            "source": "Empirical Bengaluru Climate Baseline",
            "is_live": False,
            "is_cached": False,
            "is_stale": False,
            "is_historical_fallback": True,
            "provenance": DataProvenance.HISTORICAL_DATASET.value,
            "observation_time": now_iso(),
            "request_time": self.last_attempted_request,
            "retrieved_time": now_iso()
        }
        return baseline_reading

    def get_status(self) -> Dict[str, Any]:
        """Provides status inspection without revealing secrets."""
        return {
            "provider": "Open-Meteo",
            "configured": self.is_configured(),
            "connection_tested": self.connection_tested,
            "currently_reachable": self.currently_reachable,
            "supplying_data": self.supplying_data,
            "status_code": self.get_status_code(),
            "key_required": False,
            "masked_key": self.get_masked_key(),
            "last_attempted_request": self.last_attempted_request,
            "last_successful_retrieval": self.last_successful_retrieval,
            "last_observation_time": self.last_observation_time,
            "last_latency_ms": self.last_latency_ms,
            "last_error": self.last_error,
            "base_url": self.base_url
        }
