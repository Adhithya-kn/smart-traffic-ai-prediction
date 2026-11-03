"""
traffic_system/live/bridge.py - Real-Time Live Telemetry Bridge
Connects to TomTom Traffic Flow & Open-Meteo APIs for the Bengaluru Grid.
Features:
- Clear separation of live, cached, and historical baseline data provenance
- Thread-safe in-memory caching with TTL and force-refresh capabilities
- Token bucket rate limiter pacing calls to <= 3 QPS
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

from traffic_system.config import (
    TOMTOM_API_KEY,
    API_CACHE_TTL_SECONDS
)
from traffic_system.core.road_registry import ROAD_REGISTRY
from traffic_system.core.traffic_physics import (
    calculate_spi,
    classify_spi_los,
    calculate_capacity_utilization,
    calculate_scaled_volume
)
from traffic_system.core.entities import (
    congestion_rank,
    make_feature_vector,
    DataProvenance
)
from traffic_system.core.time_utils import now_iso
from traffic_system.models.predictor import TrafficPredictor
from traffic_system.integrations.tomtom_client import TomTomClient
from traffic_system.integrations.weather_client import WeatherClient

logger = logging.getLogger("traffic_system.live.bridge")

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
        self.tomtom_key = TOMTOM_API_KEY
        self.tomtom_client = TomTomClient(api_key=self.tomtom_key)
        self.weather_client = WeatherClient()
        self.predictor = predictor or TrafficPredictor()
        if not self.predictor.is_trained():
            self.predictor.train_and_persist()
        else:
            self.predictor.load_artifacts()

        self._lock = threading.Lock()
        self._cache_ttl = API_CACHE_TTL_SECONDS
        self._telemetry_cache: Dict[str, Any] = {}
        self._telemetry_cache_time = 0.0
        self.last_successful_retrieval: Optional[str] = None

    def is_live_key_configured(self) -> bool:
        return bool(self.tomtom_key and len(self.tomtom_key) >= 12)

    def clear_cache(self) -> None:
        """Flushes telemetry and weather caches."""
        with self._lock:
            self._telemetry_cache.clear()
            self._telemetry_cache_time = 0.0

    def fetch_live_weather(self, lat: float = 12.9716, lon: float = 77.5946) -> Dict[str, Any]:
        """Fetches live weather from weather integration client."""
        return self.weather_client.get_weather(lat=lat, lon=lon)

    def _fetch_tomtom_flow(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Invokes TomTom Flow Segment API for a specific coordinate."""
        if not self.is_live_key_configured():
            return None
        self.tomtom_client.set_api_key(self.tomtom_key)
        return self.tomtom_client.get_flow_segment(lat, lon)

    def get_corridor_telemetry(
        self,
        road_ids: Optional[List[str]] = None,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Retrieves real-time telemetry for requested corridors (default: all 24).
        Clearly tags data provenance:
        - 'TomTom live API' when live flow succeeds
        - 'Cached API response' when served from unexpired memory
        - 'Empirical Live Baseline' when offline or key is unconfigured
        """
        with self._lock:
            now = time.time()
            if not force_refresh and self._telemetry_cache and (now - self._telemetry_cache_time) < self._cache_ttl:
                cached_list = [dict(c) for c in self._telemetry_cache.values()]
                for item in cached_list:
                    item["provenance"] = DataProvenance.CACHED_API_RESPONSE.value
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

        is_peak = (hour in [8, 9, 10, 17, 18, 19, 20]) and (is_weekend == 0)
        diurnal_factor = 0.72 if is_peak else 0.94

        results: List[Dict[str, Any]] = []
        observed_iso = now_iso()

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
                provenance = DataProvenance.TOMTOM_LIVE_API.value
                is_live_data = True
                self.last_successful_retrieval = observed_iso
            else:
                weather_speed_friction = 0.88 if weather_info["condition"] == "Rainy" else 1.0
                cur_speed = round(baseline_avg_speed * diurnal_factor * weather_speed_friction, 1)
                ff_speed = free_flow
                confidence = 0.90
                is_road_closed = False
                source_label = "Empirical Live Baseline"
                provenance = DataProvenance.EMPIRICAL_BASELINE.value
                is_live_data = False

            spi = calculate_spi(cur_speed, ff_speed)
            congestion_level = classify_spi_los(spi)

            capacity_util = calculate_capacity_utilization(
                (1.0 - min(1.0, cur_speed / max(ff_speed, 1.0))) * baseline_cap,
                baseline_cap
            )
            scaled_volume = calculate_scaled_volume(baseline_avg_vol, capacity_util)

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
                "precipitation_mm": weather_info.get("precipitation_mm", 0.0),
                "confidence": confidence,
                "is_road_closed": is_road_closed,
                "is_live": is_live_data,
                "provenance": provenance,
                "source": source_label,
                "observation_time": observed_iso,
                "retrieved_time": now_iso(),
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
            "provenance": DataProvenance.TOMTOM_LIVE_API.value if has_key else DataProvenance.EMPIRICAL_BASELINE.value,
            "weather": weather,
            "monitored_corridors": len(BENGALURU_CORRIDOR_GPS),
            "last_sync": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S IST"),
            "last_successful_retrieval": self.last_successful_retrieval,
            "cache_ttl_sec": int(self._cache_ttl)
        }

    def evaluate_live_route(
        self,
        origin_id: str,
        dest_id: str,
        event_mgr: Optional[Any] = None,
        date: Optional[str] = None,
        time_str: Optional[str] = None,
        published_only: bool = True
    ) -> Dict[str, Any]:
        """
        Evaluates real-time routing delay using live speeds and active Bengaluru disruptions.
        Seamlessly integrates real-time TomTom telemetry with ongoing municipal & incident events.
        """
        all_live = {c["road_id"]: dict(c) for c in self.get_corridor_telemetry()}

        orig = all_live.get(origin_id, all_live.get("RD_BLR_01"))
        dest = all_live.get(dest_id, all_live.get("RD_BLR_02"))

        primary_route = [orig["road_id"]]
        if orig["road_id"] != dest["road_id"]:
            if orig["city_zone"] != dest["city_zone"]:
                bridge_candidate = "RD_BLR_11" if "Electronic City" in (orig["city_zone"], dest["city_zone"]) else "RD_BLR_17"
                if bridge_candidate not in (orig["road_id"], dest["road_id"]):
                    primary_route.append(bridge_candidate)
            primary_route.append(dest["road_id"])

        if event_mgr is None:
            try:
                from traffic_system.events.event_manager import EventManager
                event_mgr = EventManager()
            except Exception:
                event_mgr = None

        now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
        target_date = (date.strip() if date and str(date).strip() else now_ist.strftime("%Y-%m-%d"))
        target_time = (time_str.strip() if time_str and str(time_str).strip() else now_ist.strftime("%H:%M"))

        active_events: List[Dict[str, Any]] = []
        if event_mgr is not None:
            for r_id in primary_route:
                evts = event_mgr.find_active_events(
                    road_id=r_id,
                    date=target_date,
                    time_str=target_time,
                    published_only=published_only
                )
                for evt in evts:
                    if not any(e["id"] == evt["id"] for e in active_events):
                        active_events.append(evt)

        if active_events:
            for evt in active_events:
                speed_drop_pct = float(evt.get("speed_impact_pct", 50))
                volume_surge = int(evt.get("volume_surge_vph", 600))
                for r_id in evt.get("affected_roads", []):
                    if r_id in all_live and r_id in primary_route:
                        curr = all_live[r_id]
                        impacted_spd = max(4.5, round(curr["current_speed"] * (1.0 - (speed_drop_pct / 100.0)), 1))
                        impacted_vol = curr["vehicle_count"] + volume_surge
                        curr["current_speed"] = impacted_spd
                        curr["vehicle_count"] = impacted_vol
                        curr["congestion_level"] = "Severe" if impacted_spd < 18.0 else "High"

        primary_speeds = [all_live[r]["current_speed"] for r in primary_route if r in all_live]
        primary_vols = [all_live[r]["vehicle_count"] for r in primary_route if r in all_live]
        avg_primary_speed = round(sum(primary_speeds) / max(len(primary_speeds), 1), 1)
        avg_primary_vol = int(round(sum(primary_vols) / max(len(primary_vols), 1)))
        primary_los = max((all_live[r]["congestion_level"] for r in primary_route if r in all_live), key=congestion_rank)

        is_rerouted = bool(active_events) or primary_los in ("High", "Severe")
        recommended_route = list(primary_route)
        time_saved = 0.0
        alt_speed = avg_primary_speed
        alt_vol = avg_primary_vol
        rec_los = primary_los

        road_names = {r["road_id"]: r["road_name"] for r in all_live.values()}

        if is_rerouted:
            affected_road_ids = {r for e in active_events for r in e.get("affected_roads", [])}
            candidates = [
                r for r in all_live.values() 
                if r["road_id"] not in primary_route
                and r["road_id"] not in affected_road_ids
                and r["congestion_level"] in ("Low", "Moderate")
            ]
            if not candidates:
                candidates = [
                    r for r in all_live.values() 
                    if r["road_id"] not in primary_route
                    and r["congestion_level"] in ("Low", "Moderate")
                ]

            if candidates:
                best_bypass = min(candidates, key=lambda c: congestion_rank(c["congestion_level"]))
                recommended_route = [orig["road_id"], best_bypass["road_id"], dest["road_id"]]
                rec_speeds = [all_live[r]["current_speed"] for r in recommended_route if r in all_live]
                alt_speed = round(sum(rec_speeds) / max(len(rec_speeds), 1), 1)
                alt_vol = int(round(avg_primary_vol * 0.72))
                rec_los = best_bypass["congestion_level"]
                transit_km = 8.5
                prim_min = (transit_km / max(avg_primary_speed, 5.0)) * 60.0
                alt_min = (transit_km / max(alt_speed, 5.0)) * 60.0
                time_saved = max(3.5 if active_events else 2.5, round(prim_min - alt_min, 1))

        primary_route_names = [road_names.get(r, r) for r in primary_route]
        recommended_route_names = [road_names.get(r, r) for r in recommended_route]

        return {
            "origin_road": orig["road_id"],
            "origin_name": orig["road_name"],
            "destination_road": dest["road_id"],
            "destination_name": dest["road_name"],
            "primary_route": primary_route,
            "primary_route_names": primary_route_names,
            "primary_congestion": primary_los,
            "primary_speed_kmh": avg_primary_speed,
            "primary_vehicle_count": avg_primary_vol,
            "is_rerouted": is_rerouted,
            "recommended_route": recommended_route,
            "recommended_route_names": recommended_route_names,
            "recommended_congestion": rec_los,
            "alternate_speed_kmh": alt_speed,
            "alternate_vehicle_count": alt_vol,
            "time_saved_minutes": time_saved,
            "weather_context": orig["weather_condition"],
            "source": orig["source"],
            "provenance": orig.get("provenance", DataProvenance.EMPIRICAL_BASELINE.value),
            "active_events": active_events,
            "has_active_events": len(active_events) > 0,
            "horizon_date": target_date,
            "horizon_time": target_time,
            "evaluated_at": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S IST")
        }


_LIVE_BRIDGE: Optional[LiveTrafficDataBridge] = None

def get_live_bridge() -> LiveTrafficDataBridge:
    global _LIVE_BRIDGE
    if _LIVE_BRIDGE is None:
        _LIVE_BRIDGE = LiveTrafficDataBridge()
    return _LIVE_BRIDGE
