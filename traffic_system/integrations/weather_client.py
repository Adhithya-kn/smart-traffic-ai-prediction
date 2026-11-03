"""
traffic_system/integrations/weather_client.py - Meteorological Data Client
Retrieves real-time atmospheric data via Open-Meteo forecast API for the Bengaluru metropolitan region.
No mandatory API key required for baseline operations; supports custom keys and endpoints.
"""

import os
import json
import time
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

logger = logging.getLogger("traffic_system.integrations.weather")


class WeatherClient:
    """
    Client for Open-Meteo Weather API.
    Provides meteorological factors (temperature, precipitation, condition, fog/rain).
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

        self._cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: float = 0.0
        self.last_successful_retrieval: Optional[str] = None
        self.last_latency_ms: float = 0.0
        self.last_error: Optional[str] = None

    def set_config(self, api_key: Optional[str] = None, base_url: Optional[str] = None) -> None:
        """Dynamically configures weather provider attributes."""
        if api_key is not None:
            self.api_key = str(api_key).strip()
        if base_url is not None:
            self.base_url = str(base_url).rstrip("/")
        # Invalidate cache on reconfiguration
        self._cache = None
        self._cache_timestamp = 0.0

    def get_masked_key(self) -> str:
        """Returns masked API key representation."""
        if not self.api_key:
            return "none_required"
        if len(self.api_key) <= 6:
            return "******"
        return f"****{self.api_key[-4:]}"

    def _execute_request(self, url: str) -> Tuple[bool, Optional[Dict[str, Any]], int, str]:
        start = time.perf_counter()
        for attempt in range(1, self.max_retries + 1):
            try:
                headers = {"User-Agent": "SmartTrafficAI-WeatherClient/2.0", "Accept": "application/json"}
                if self.api_key and self.api_key != "none_required":
                    headers["X-Api-Key"] = self.api_key
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw)
                    self.last_latency_ms = round((time.perf_counter() - start) * 1000, 2)
                    self.last_successful_retrieval = now_iso()
                    self.last_error = None
                    return True, data, resp.status, ""
            except urllib.error.HTTPError as e:
                self.last_latency_ms = round((time.perf_counter() - start) * 1000, 2)
                if attempt == self.max_retries:
                    self.last_error = f"HTTP {e.code}"
                    return False, None, e.code, self.last_error
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                self.last_latency_ms = round((time.perf_counter() - start) * 1000, 2)
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
            return True, "Open-Meteo Weather API is reachable and responsive.", self.last_latency_ms
        return False, f"Weather API test failed: {err} (HTTP {code})", self.last_latency_ms

    def get_weather(self, lat: float = 12.9716, lon: float = 77.5946, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Retrieves weather observation with TTL caching.
        Falls back to seasonal baseline if network is unreachable or sandboxed.
        """
        now = time.time()
        if not force_refresh and self._cache and (now - self._cache_timestamp) < self.cache_ttl:
            cached = dict(self._cache)
            cached["provenance"] = "Cached API response"
            return cached

        url = (
            f"{self.base_url}?latitude={lat:.4f}&longitude={lon:.4f}"
            f"&current=temperature_2m,precipitation,weather_code,wind_speed_10m&timezone=Asia%2FKolkata"
        )

        ok, raw, _, _ = self._execute_request(url)
        if ok and raw and "current" in raw:
            cur = raw["current"]
            precip = float(cur.get("precipitation", 0.0))
            code = int(cur.get("weather_code", 1))
            cond = (
                "Rainy" if (precip > 0.2 or code in [51, 53, 55, 61, 63, 65, 80, 81, 82])
                else "Foggy" if code in [45, 48]
                else "Overcast" if code in [2, 3]
                else "Clear"
            )
            reading = {
                "condition": cond,
                "temperature": float(cur.get("temperature_2m", 27.0)),
                "precipitation_mm": precip,
                "wind_speed_kmh": float(cur.get("wind_speed_10m", 12.0)),
                "weather_code": code,
                "source": "Open-Meteo Live API",
                "is_live": True,
                "provenance": "TomTom live API",
                "observation_time": now_iso(),
                "retrieved_time": now_iso()
            }
            self._cache = reading
            self._cache_timestamp = now
            return reading

        # Fallback calibrated baseline when offline/sandboxed
        baseline_reading = {
            "condition": "Clear",
            "temperature": 27.5,
            "precipitation_mm": 0.0,
            "wind_speed_kmh": 10.5,
            "weather_code": 1,
            "source": "Empirical Bengaluru Climate Baseline",
            "is_live": False,
            "provenance": "Historical dataset",
            "observation_time": now_iso(),
            "retrieved_time": now_iso()
        }
        self._cache = baseline_reading
        self._cache_timestamp = now
        return baseline_reading

    def get_status(self) -> Dict[str, Any]:
        """Provides status inspection without revealing secrets."""
        return {
            "provider": "Open-Meteo",
            "key_required": False,
            "masked_key": self.get_masked_key(),
            "last_successful_retrieval": self.last_successful_retrieval,
            "last_latency_ms": self.last_latency_ms,
            "last_error": self.last_error,
            "base_url": self.base_url
        }
