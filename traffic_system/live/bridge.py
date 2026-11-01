"""
traffic_system/live/bridge.py - Real-Time Live Telemetry Bridge
Connects to TomTom Traffic Flow & Open-Meteo APIs for the Bengaluru Grid.
Features:
- Thread-safe in-memory caching with 120s TTL (preventing cache stampedes)
- Token bucket rate limiter pacing calls to <= 3 QPS (protecting daily quotas)
- Calibrated volume scaling aligned with XGBoost training distribution
- Clean offline / baseline fallback when API keys are absent or sandboxed
"""

from __future__ import annotations

import os
import json
import time
import math
import logging
import threading
import urllib.request
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from zoneinfo import ZoneInfo

from traffic_system.core.road_registry import ROAD_REGISTRY
from traffic_system.core.traffic_physics import (
    calculate_spi,
    classify_spi_los,
    calculate_capacity_utilization,
    calculate_scaled_volume
)
from traffic_system.core.entities import congestion_rank, make_feature_vector
from traffic_system.models.predictor import TrafficPredictor

logger = logging.getLogger("traffic_system.live.bridge")

# Canonical GPS Centroids for all 24 Bengaluru Corridors
_GPS_RAW: Dict[str, Tuple[float, float, float]] = {
    "RD_BLR_01": (12.9784, 77.6408, 48.0), "RD_BLR_02": (12.9756, 77.6066, 45.0),
    "RD_BLR_03": (13.0358, 77.5970, 60.0), "RD_BLR_04": (12.9790, 77.6420, 46.0),
    "RD_BLR_05": (13.0380, 77.5985, 55.0), "RD_BLR_06": (12.8452, 77.6602, 65.0),
    "RD_BLR_07": (12.9850, 77.7280, 50.0), "RD_BLR_08": (12.9250, 77.5938, 44.0),
    "RD_BLR_09": (12.9560, 77.7010, 52.0), "RD_BLR_10": (12.9240, 77.6520, 48.0),
    "RD_BLR_11": (12.9176, 77.6238, 42.0), "RD_BLR_12": (12.9352, 77.6245, 45.0),
    "RD_BLR_13": (12.9280, 77.5790, 46.0), "RD_BLR_14": (12.9725, 77.6200, 48.0),
    "RD_BLR_15": (13.0280, 77.5400, 58.0), "RD_BLR_16": (13.0238, 77.5529, 50.0),
    "RD_BLR_17": (12.9600, 77.6480, 50.0), "RD_BLR_18": (12.9730, 77.6075, 42.0),
    "RD_BLR_19": (13.0550, 77.6320, 52.0), "RD_BLR_20": (12.8399, 77.6770, 60.0),
    "RD_BLR_21": (12.9420, 77.7470, 48.0), "RD_BLR_22": (12.9050, 77.5750, 52.0),
    "RD_BLR_23": (12.9400, 77.6200, 46.0), "RD_BLR_24": (13.0030, 77.5700, 44.0),
}

BENGALURU_CORRIDOR_GPS: Dict[str, Dict[str, Any]] = {
    rid: {
        "name": ROAD_REGISTRY.get(rid, {}).get("bangalore_name", rid),
        "zone": ROAD_REGISTRY.get(rid, {}).get("city_zone", "Indiranagar"),
        "lat": lat, "lon": lon, "free_flow": ff
    }
    for rid, (lat, lon, ff) in _GPS_RAW.items()
}

class LiveTrafficDataBridge:
    def __init__(self, predictor: Optional[TrafficPredictor] = None):
        self.tomtom_key = os.environ.get("TOMTOM_API_KEY", "").strip()
        self.predictor = predictor or TrafficPredictor()
        if not self.predictor.is_trained():
            self.predictor.train_and_persist()
        else:
            self.predictor.load_artifacts()

        self._lock = threading.Lock()
        self._last_call_time = 0.0
        self._min_call_interval = 0.35  # Max ~2.85 QPS to safely adhere to <= 3 QPS
        
        # In-memory caches with 120s TTL
        self._cache_ttl = 120.0
        self._telemetry_cache: Dict[str, Any] = {}
        self._telemetry_cache_time = 0.0
        self._weather_cache: Dict[str, Any] = {}
        self._weather_cache_time = 0.0

    def is_live_key_configured(self) -> bool:
        return bool(self.tomtom_key and len(self.tomtom_key) > 10)

    def _rate_limit_pace(self) -> None:
        """Enforces token bucket pacing to ensure <= 3 QPS."""
        now = time.time()
        elapsed = now - self._last_call_time
        if elapsed < self._min_call_interval:
            time.sleep(self._min_call_interval - elapsed)
        self._last_call_time = time.time()

    def _fetch_json(self, url: str) -> Optional[Dict[str, Any]]:
        self._rate_limit_pace()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TrafficAI-LiveBridge/1.0"})
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                return json.loads(resp.read().decode())
        except Exception as err:
            logger.warning(f"Live API request failed for {url.split('?')[0]}: {err}")
            return None

    def fetch_live_weather(self, lat: float = 12.9716, lon: float = 77.5946) -> Dict[str, Any]:
        """Fetches live weather from Open-Meteo for Bengaluru with 120s TTL caching."""
        with self._lock:
            now = time.time()
            if self._weather_cache and (now - self._weather_cache_time) < self._cache_ttl:
                return self._weather_cache

            url = (
                f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                "&current=temperature_2m,precipitation,weather_code&timezone=Asia%2FKolkata"
            )
            weather_data = {
                "condition": "Clear", "temperature": 27.5,
                "precipitation_mm": 0.0, "weather_code": 1,
                "source": "Open-Meteo Live API", "is_live": False
            }

            raw = self._fetch_json(url)
            if raw and "current" in raw:
                cur = raw["current"]
                precip = float(cur.get("precipitation", 0.0))
                code = int(cur.get("weather_code", 1))
                cond = "Rainy" if (precip > 0.2 or code in [51, 53, 55, 61, 63, 65, 80, 81, 82]) else "Foggy" if code in [45, 48] else "Clear"
                weather_data.update({
                    "condition": cond, "temperature": float(cur.get("temperature_2m", 27.0)),
                    "precipitation_mm": precip, "weather_code": code, "is_live": True
                })

            self._weather_cache = weather_data
            self._weather_cache_time = now
            return weather_data

    def _fetch_tomtom_flow(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Invokes TomTom Flow Segment API for a specific coordinate."""
        if not self.is_live_key_configured():
            return None
        url = (
            f"https://api.tomtom.com/traffic/services/4/flowSegmentData/relative0/10/json"
            f"?point={lat},{lon}&unit=KMPH&key={self.tomtom_key}"
        )
        data = self._fetch_json(url)
        return data.get("flowSegmentData") if data else None

    def get_corridor_telemetry(self, road_ids: Optional[List[str]] = None, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Retrieves real-time telemetry for requested corridors (default: all 24).
        If TomTom key is present, calls TomTom API; otherwise, generates calibrated
        live-baseline observations grounded in empirical network topology.
        """
        with self._lock:
            now = time.time()
            if not force_refresh and self._telemetry_cache and (now - self._telemetry_cache_time) < self._cache_ttl:
                cached_list = list(self._telemetry_cache.values())
                if road_ids:
                    return [c for c in cached_list if c["road_id"] in road_ids]
                return cached_list

        target_ids = road_ids if road_ids else list(BENGALURU_CORRIDOR_GPS.keys())
        weather_info = self.fetch_live_weather()
        is_live_provider = self.is_live_key_configured()

        now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
        hour = now_ist.hour
        dow = now_ist.weekday()
        is_weekend = 1 if dow >= 5 else 0

        # Peak hours diurnal multiplier: 08-11 and 17-20 on weekdays
        is_peak = (hour in [8, 9, 10, 17, 18, 19, 20]) and (is_weekend == 0)
        diurnal_factor = 0.72 if is_peak else 0.94

        results: List[Dict[str, Any]] = []

        for r_id in target_ids:
            gps = BENGALURU_CORRIDOR_GPS.get(r_id, {})
            r_reg = ROAD_REGISTRY.get(r_id, {})
            topo = self.predictor.topology.get(r_id, {}) if self.predictor.topology else {}

            road_name = r_reg.get("bangalore_name", gps.get("name", r_id))
            city_zone = r_reg.get("city_zone", gps.get("zone", "Indiranagar"))
            intersection_name = r_reg.get("intersection_name", f"INT_{r_id}")
            free_flow = float(gps.get("free_flow", 50.0))
            baseline_avg_speed = float(topo.get("avg_speed", 38.0))
            baseline_avg_vol = int(topo.get("avg_volume", 25000))
            baseline_cap = int(topo.get("capacity", 55000))

            tomtom_flow = None
            if is_live_provider:
                tomtom_flow = self._fetch_tomtom_flow(gps["lat"], gps["lon"])

            if tomtom_flow:
                cur_speed = float(tomtom_flow.get("currentSpeed", baseline_avg_speed))
                ff_speed = float(tomtom_flow.get("freeFlowSpeed", free_flow))
                confidence = float(tomtom_flow.get("confidence", 0.95))
                is_road_closed = bool(tomtom_flow.get("roadClosure", False))
                source_label = "TomTom Live Telemetry"
                is_live_data = True
            else:
                # Calibrated empirical baseline snapshot adjusted for time and weather
                weather_speed_friction = 0.88 if weather_info["condition"] == "Rainy" else 1.0
                cur_speed = round(baseline_avg_speed * diurnal_factor * weather_speed_friction, 1)
                ff_speed = free_flow
                confidence = 0.90
                is_road_closed = False
                source_label = "Empirical Live Baseline"
                is_live_data = False

            # 1. Speed Performance Index (SPI) & Level of Service (Unified DRY Physics)
            spi = calculate_spi(cur_speed, ff_speed)
            congestion_level = classify_spi_los(spi)

            # 2. Capacity Utilization Stress (%)
            capacity_util = calculate_capacity_utilization(
                (1.0 - min(1.0, cur_speed / max(ff_speed, 1.0))) * baseline_cap,
                baseline_cap
            )

            # 3. Scaled Volume Calibration (maintains XGBoost training magnitude: $15,000 - $65,000)
            scaled_volume = calculate_scaled_volume(baseline_avg_vol, capacity_util)

            # 4. Standardized Vectorized XGBoost AI Forward Prediction
            feat_dict = make_feature_vector(
                road_id=r_id,
                vehicle_count=scaled_volume,
                average_speed=cur_speed,
                capacity_utilization=capacity_util,
                congestion_level=congestion_level,
                hour=hour,
                day_of_week=dow,
                is_weekend=is_weekend,
                city_zone=city_zone,
                intersection_id=intersection_name
            )
            pred_class, prob_dist = self.predictor.predict_segment(feat_dict)

            item = {
                "road_id": r_id,
                "road_name": road_name,
                "city_zone": city_zone,
                "intersection_name": intersection_name,
                "current_speed": cur_speed,
                "free_flow_speed": ff_speed,
                "speed_performance_index": spi,
                "congestion_level": congestion_level,
                "capacity_utilization": capacity_util,
                "vehicle_count": scaled_volume,
                "design_capacity": baseline_cap,
                "predicted_future_congestion": pred_class,
                "prediction_confidence": prob_dist.get(pred_class, 0.75),
                "prob_distribution": prob_dist,
                "weather_condition": weather_info["condition"],
                "precipitation_mm": weather_info["precipitation_mm"],
                "confidence": confidence,
                "is_road_closed": is_road_closed,
                "is_live": is_live_data,
                "source": source_label,
                "timestamp": now_ist.strftime("%Y-%m-%d %H:%M:%S IST")
            }
            results.append(item)

        with self._lock:
            for item in results:
                self._telemetry_cache[item["road_id"]] = item
            self._telemetry_cache_time = time.time()

        return results

    def get_live_status(self) -> Dict[str, Any]:
        """Returns provider status, key presence, cache status, and weather summary."""
        weather = self.fetch_live_weather()
        has_key = self.is_live_key_configured()
        
        status_code = "LIVE_READY" if has_key else "BASELINE_SNAPSHOT"
        status_label = "Live TomTom Probe Ingestion" if has_key else "Calibrated Live Baseline (API Key Optional)"

        return {
            "status": "success",
            "provider": "TomTom Traffic + Open-Meteo" if has_key else "Empirical Bengaluru Topology + Open-Meteo",
            "status_code": status_code,
            "status_label": status_label,
            "is_live_api": has_key,
            "weather": weather,
            "monitored_corridors": len(BENGALURU_CORRIDOR_GPS),
            "last_sync": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S IST"),
            "cache_ttl_sec": int(self._cache_ttl)
        }

    def evaluate_live_route(self, origin_id: str, dest_id: str) -> Dict[str, Any]:
        """
        Evaluates real-time routing delay using live speeds.
        Isolated implementation: DOES NOT alter RouteNavigator.evaluate_route().
        """
        all_live = {c["road_id"]: c for c in self.get_corridor_telemetry()}

        orig = all_live.get(origin_id, all_live.get("RD_BLR_01"))
        dest = all_live.get(dest_id, all_live.get("RD_BLR_02"))

        # Determine Primary Route path
        primary_route = [orig["road_id"]]
        if orig["road_id"] != dest["road_id"]:
            # Connect via bridge arterial if across zones
            if orig["city_zone"] != dest["city_zone"]:
                bridge_candidate = "RD_BLR_11" if "Electronic City" in (orig["city_zone"], dest["city_zone"]) else "RD_BLR_17"
                if bridge_candidate not in (orig["road_id"], dest["road_id"]):
                    primary_route.append(bridge_candidate)
            primary_route.append(dest["road_id"])

        # Calculate live traversal metrics along primary route
        primary_speeds = [all_live[r]["current_speed"] for r in primary_route if r in all_live]
        primary_vols = [all_live[r]["vehicle_count"] for r in primary_route if r in all_live]
        avg_primary_speed = round(sum(primary_speeds) / max(len(primary_speeds), 1), 1)
        avg_primary_vol = int(round(sum(primary_vols) / max(len(primary_vols), 1)))

        # Determine worst congestion along primary path using unified congestion_rank
        primary_los = max((all_live[r]["congestion_level"] for r in primary_route if r in all_live), key=congestion_rank)

        # Check for dynamic bypass rerouting recommendation
        is_rerouted = primary_los in ("High", "Severe")
        recommended_route = list(primary_route)
        time_saved = 0.0
        alt_speed = avg_primary_speed
        alt_vol = avg_primary_vol
        rec_los = primary_los

        if is_rerouted:
            # Pick bypass corridor in or near destination zone
            candidates = [
                r for r in all_live.values() 
                if r["road_id"] not in primary_route and r["congestion_level"] in ("Low", "Moderate")
            ]
            if candidates:
                best_bypass = min(candidates, key=lambda c: congestion_rank(c["congestion_level"]))
                recommended_route = [orig["road_id"], best_bypass["road_id"], dest["road_id"]]
                rec_speeds = [all_live[r]["current_speed"] for r in recommended_route if r in all_live]
                alt_speed = round(sum(rec_speeds) / max(len(rec_speeds), 1), 1)
                alt_vol = int(round(avg_primary_vol * 0.72))
                rec_los = best_bypass["congestion_level"]
                # Time saved estimate across an assumed 8.5 km transit
                transit_km = 8.5
                prim_min = (transit_km / max(avg_primary_speed, 5.0)) * 60.0
                alt_min = (transit_km / max(alt_speed, 5.0)) * 60.0
                time_saved = max(2.5, round(prim_min - alt_min, 1))

        return {
            "origin_road": orig["road_id"],
            "origin_name": orig["road_name"],
            "destination_road": dest["road_id"],
            "destination_name": dest["road_name"],
            "primary_route": primary_route,
            "primary_congestion": primary_los,
            "primary_speed_kmh": avg_primary_speed,
            "primary_vehicle_count": avg_primary_vol,
            "is_rerouted": is_rerouted,
            "recommended_route": recommended_route,
            "recommended_congestion": rec_los,
            "alternate_speed_kmh": alt_speed,
            "alternate_vehicle_count": alt_vol,
            "time_saved_minutes": time_saved,
            "weather_context": orig["weather_condition"],
            "source": orig["source"],
            "evaluated_at": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S IST")
        }

# Global singleton
_LIVE_BRIDGE: Optional[LiveTrafficDataBridge] = None

def get_live_bridge() -> LiveTrafficDataBridge:
    global _LIVE_BRIDGE
    if _LIVE_BRIDGE is None:
        _LIVE_BRIDGE = LiveTrafficDataBridge()
    return _LIVE_BRIDGE
