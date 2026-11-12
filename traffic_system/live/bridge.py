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
from traffic_system.core.road_registry import (
    ROAD_REGISTRY,
    get_corridor_lane_info,
    get_corridor_coordinates,
    get_road_name
)
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
        self._live_route_cache: Dict[Tuple[str, str], Tuple[float, Dict[str, Any]]] = {}
        self.last_attempted_request: Optional[str] = None
        self.last_successful_retrieval: Optional[str] = None

    def is_live_key_configured(self) -> bool:
        return bool(self.tomtom_key and len(self.tomtom_key) >= 12)

    def clear_cache(self) -> None:
        """Flushes telemetry, route and weather caches."""
        with self._lock:
            self._telemetry_cache.clear()
            self._telemetry_cache_time = 0.0
            self._live_route_cache.clear()
            self.last_successful_retrieval = None
            self.tomtom_client.supplying_data = False
            self.weather_client.set_config()

    def fetch_live_weather(self, lat: float = 12.9716, lon: float = 77.5946) -> Dict[str, Any]:
        """Fetches live weather from weather integration client."""
        return self.weather_client.get_weather(lat=lat, lon=lon)

    def _fetch_tomtom_flow(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Invokes TomTom Flow Segment API for a specific coordinate."""
        if not self.is_live_key_configured():
            return None
        self.last_attempted_request = now_iso()
        self.tomtom_client.set_api_key(self.tomtom_key)
        flow = self.tomtom_client.get_flow_segment(lat, lon)
        if flow:
            self.last_successful_retrieval = now_iso()
        return flow

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
                cached_list = []
                for c in self._telemetry_cache.values():
                    item = dict(c)
                    item["is_live"] = False
                    item["is_cached"] = True
                    item["is_stale"] = False
                    item["has_valid_live_observation"] = bool(c.get("has_valid_live_observation", False))
                    item["is_historical_fallback"] = bool(c.get("is_historical_fallback", False))
                    item["provenance"] = DataProvenance.CACHED_API_RESPONSE.value
                    if "(Cached)" not in str(item.get("source", "")):
                        item["source"] = f"{item.get('source', 'Telemetry')} (Cached)"
                    cached_list.append(item)
                if road_ids:
                    return [c for c in cached_list if c["road_id"] in road_ids]
                return cached_list

        target_ids = road_ids if road_ids else list(BENGALURU_CORRIDOR_GPS.keys())
        weather_info = self.fetch_live_weather()
        is_live_provider = self.is_live_key_configured()

        # Parallel flow pre-fetching: Avoid sequential requests creating excessive refresh latency
        flow_map: Dict[str, Any] = {}
        if is_live_provider:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            def _fetch_worker(rid: str, lat: float, lon: float):
                return rid, self._fetch_tomtom_flow(lat, lon)

            worker_count = min(6, max(1, len(target_ids)))
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = [
                    executor.submit(_fetch_worker, r_id, BENGALURU_CORRIDOR_GPS[r_id]["lat"], BENGALURU_CORRIDOR_GPS[r_id]["lon"])
                    for r_id in target_ids if r_id in BENGALURU_CORRIDOR_GPS
                ]
                for fut in as_completed(futures):
                    try:
                        rid, flow = fut.result()
                        if flow:
                            flow_map[rid] = flow
                    except Exception as ex:
                        logger.warning("Parallel TomTom fetch error: %s", ex)

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

            tomtom_flow = flow_map.get(r_id) if is_live_provider else None

            if tomtom_flow:
                cur_speed = float(tomtom_flow.get("currentSpeed", baseline_avg_speed))
                # Corridors have calibrated metropolitan design speeds (42-65 km/h); maintain physical lower bound
                ff_speed = max(free_flow, float(tomtom_flow.get("freeFlowSpeed", free_flow)))
                confidence = float(tomtom_flow.get("confidence", 0.95))
                is_road_closed = bool(tomtom_flow.get("roadClosure", False))
                source_label = "TomTom Live Telemetry"
                provenance = DataProvenance.TOMTOM_LIVE_API.value
                is_live_data = True
                is_cached_data = False
                is_historical = False
                has_valid_live_obs = True
                corridor_obs = (
                    tomtom_flow.get("_observation_time")
                    or tomtom_flow.get("timestamp")
                    or self.tomtom_client.last_observation_time
                    or observed_iso
                )
                retrieval_time = tomtom_flow.get("_retrieved_time") or observed_iso
                self.last_successful_retrieval = observed_iso
            else:
                # Environmental physical friction factor (rainfall reduces effective road velocity)
                weather_speed_friction = 0.88 if weather_info["condition"] == "Rainy" else 1.0
                cur_speed = round(baseline_avg_speed * diurnal_factor * weather_speed_friction, 1)
                ff_speed = free_flow
                confidence = 0.90
                is_road_closed = False
                source_label = "Empirical Live Baseline"
                provenance = DataProvenance.EMPIRICAL_BASELINE.value
                is_live_data = False
                is_cached_data = False
                is_historical = True
                has_valid_live_obs = False
                corridor_obs = observed_iso
                retrieval_time = observed_iso

            if is_road_closed:
                cur_speed = 0.0
                spi = 0.0
                congestion_level = "Severe"
            else:
                spi = calculate_spi(cur_speed, ff_speed)
                if cur_speed < 15.0 or spi < 30.0:
                    congestion_level = "Severe"
                elif cur_speed < 23.0 or spi < 50.0:
                    congestion_level = "High"
                elif cur_speed < 34.0 or spi < 75.0:
                    congestion_level = "Moderate"
                else:
                    congestion_level = "Low"

            # Dynamic capacity utilization matching physical traffic density
            speed_ratio = min(1.0, max(0.0, cur_speed / max(ff_speed, 1.0)))
            if congestion_level == "Severe":
                util_pct = min(98.0, max(90.0, (1.0 - speed_ratio * 0.5) * 100.0))
            elif congestion_level == "High":
                util_pct = min(88.0, max(75.0, (1.0 - speed_ratio * 0.4) * 100.0))
            elif congestion_level == "Moderate":
                util_pct = min(72.0, max(45.0, (1.0 - speed_ratio * 0.3) * 100.0))
            else:
                util_pct = min(42.0, max(15.0, (1.0 - speed_ratio * 0.2) * 100.0))

            capacity_util = calculate_capacity_utilization(
                (util_pct / 100.0) * baseline_cap,
                baseline_cap
            )
            scaled_volume = calculate_scaled_volume(baseline_cap * 0.5, capacity_util)

            # Feature schema compliance: next-hour horizon transition
            next_hour = (hour + 1) % 24
            next_dow = (dow + (1 if hour == 23 else 0)) % 7
            next_weekend = 1 if next_dow >= 5 else 0

            feat_dict = make_feature_vector(
                road_id=r_id,
                vehicle_count=scaled_volume,
                average_speed=cur_speed,
                capacity_utilization=capacity_util,
                congestion_level=congestion_level,
                hour=next_hour,
                day_of_week=next_dow,
                is_weekend=next_weekend,
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
                "is_cached": is_cached_data,
                "is_stale": False,
                "is_historical_fallback": is_historical,
                "has_valid_live_observation": has_valid_live_obs,
                "vehicle_count_source": "Topological Baseline Calibration",
                "provenance": provenance,
                "source": source_label,
                "request_time": self.last_attempted_request,
                "observation_time": corridor_obs,
                "retrieved_time": retrieval_time,
                "timestamp": now_ist.strftime("%Y-%m-%d %H:%M:%S IST")
            }
            results.append(item)

        with self._lock:
            for item in results:
                self._telemetry_cache[item["road_id"]] = item
            self._telemetry_cache_time = time.time()

        return results

    def get_live_status(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Returns provider status, key presence, reachability, cache status, and weather summary."""
        weather = self.fetch_live_weather()
        has_key = self.is_live_key_configured()
        has_live_cache = any(c.get("is_live", False) for c in self._telemetry_cache.values())
        is_live_supplying = bool(has_key and (self.tomtom_client.currently_reachable or has_live_cache) and (self.tomtom_client.supplying_data or has_live_cache))

        if is_live_supplying:
            status_code = "LIVE_READY"
            status_label = "Live TomTom Probe Ingestion Active"
            is_live_api = True
        elif has_key and self.tomtom_client.connection_tested and not self.tomtom_client.currently_reachable:
            status_code = "CONFIGURED_UNREACHABLE"
            status_label = f"TomTom API Configured but Unreachable: {self.tomtom_client.last_error or 'Connection failed'}"
            is_live_api = False
        elif has_key:
            status_code = "CONFIGURED_UNTESTED"
            status_label = "TomTom API Key Configured (Awaiting Ingestion Verification)"
            is_live_api = False
        else:
            status_code = "BASELINE_SNAPSHOT"
            status_label = "Calibrated Live Baseline (API Key Optional)"
            is_live_api = False

        return {
            "status": "success",
            "provider": "TomTom Traffic + Open-Meteo" if is_live_api else "Empirical Bengaluru Topology + Open-Meteo",
            "status_code": status_code,
            "status_label": status_label,
            "is_live_api": is_live_api,
            "provenance": DataProvenance.TOMTOM_LIVE_API.value if is_live_api else DataProvenance.EMPIRICAL_BASELINE.value,
            "weather": weather,
            "monitored_corridors": len(BENGALURU_CORRIDOR_GPS),
            "last_sync": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S IST"),
            "last_attempted_request": self.last_attempted_request or self.tomtom_client.last_attempted_request,
            "last_successful_retrieval": self.last_successful_retrieval or self.tomtom_client.last_successful_retrieval,
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
        Evaluates real-time routing using TomTom Calculate Route API and active Bengaluru disruptions.
        Includes shared backend caching (60s TTL), live traffic delay, route geometry, and available alternatives.
        Falls back cleanly to calibrated empirical topology if TomTom is unavailable.
        """
        cache_key = f"{origin_id}:{dest_id}:{date}:{time_str}:{published_only}"
        now_ts = time.time()
        with self._lock:
            if cache_key in self._live_route_cache:
                cached_time, cached_res = self._live_route_cache[cache_key]
                if (now_ts - cached_time) < self._cache_ttl:
                    res_copy = dict(cached_res)
                    res_copy["is_cached"] = True
                    return res_copy

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

        # Attempt genuine TomTom Calculate Route if configured
        tomtom_route = None
        orig_gps = BENGALURU_CORRIDOR_GPS.get(origin_id, {"lat": 12.9784, "lon": 77.6408, "name": origin_id})
        dest_gps = BENGALURU_CORRIDOR_GPS.get(dest_id, {"lat": 12.9756, "lon": 77.6066, "name": dest_id})

        if self.is_live_key_configured():
            try:
                tomtom_route = self.tomtom_client.calculate_route(
                    float(orig_gps["lat"]), float(orig_gps["lon"]),
                    float(dest_gps["lat"]), float(dest_gps["lon"]),
                    max_alternatives=2
                )
            except Exception as ex:
                logger.warning("TomTom calculate_route error: %s", ex)
                tomtom_route = None

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

        # Multi-Lane Guidance and Polyline Geometry Generation
        primary_polylines: List[List[float]] = []
        primary_lane_guidance: List[Dict[str, Any]] = []
        for r_id in primary_route:
            coords = get_corridor_coordinates(r_id)
            if coords:
                primary_polylines.extend(coords)
            lane_meta = get_corridor_lane_info(r_id)
            c_info = all_live.get(r_id, {})
            c_los = c_info.get("congestion_level", primary_los)
            
            lane_rec = "Assign through express lane (Lane 2+); avoid curbside delay" if c_los in ("High", "Severe") else "All lanes flowing nominal"
            primary_lane_guidance.append({
                "road_id": r_id,
                "road_name": road_names.get(r_id, r_id),
                "lanes": lane_meta.get("lanes", 4),
                "lane_breakdown": lane_meta.get("lane_breakdown", []),
                "congestion": c_los,
                "recommended_lane": lane_rec,
                "speed_kmh": c_info.get("current_speed", avg_primary_speed),
                "speed_limit_kmh": lane_meta.get("speed_limit_kmh", 50.0)
            })

        recommended_polylines: List[List[float]] = []
        recommended_lane_guidance: List[Dict[str, Any]] = []
        for r_id in recommended_route:
            coords = get_corridor_coordinates(r_id)
            if coords:
                recommended_polylines.extend(coords)
            lane_meta = get_corridor_lane_info(r_id)
            c_info = all_live.get(r_id, {})
            c_los = rec_los if is_rerouted else c_info.get("congestion_level", primary_los)
            
            lane_rec = f"Optimal bypass lane: proceed via {lane_meta.get('lane_breakdown', ['Lane 2'])[1 if len(lane_meta.get('lane_breakdown', [])) > 1 else 0]}" if is_rerouted else "Follow primary route lanes"
            recommended_lane_guidance.append({
                "road_id": r_id,
                "road_name": road_names.get(r_id, r_id),
                "lanes": lane_meta.get("lanes", 4),
                "lane_breakdown": lane_meta.get("lane_breakdown", []),
                "congestion": c_los,
                "recommended_lane": lane_rec,
                "speed_kmh": c_info.get("current_speed", alt_speed if is_rerouted else avg_primary_speed),
                "speed_limit_kmh": lane_meta.get("speed_limit_kmh", 50.0)
            })

        transit_dist_km = 8.5
        topological_est_time = round((transit_dist_km / max(avg_primary_speed, 5.0)) * 60.0, 1)
        topological_delay = round(max(0.0, topological_est_time - ((transit_dist_km / 50.0) * 60.0)), 1)

        if tomtom_route:
            result = {
                "origin_road": orig["road_id"],
                "origin_name": orig["road_name"],
                "destination_road": dest["road_id"],
                "destination_name": dest["road_name"],
                "status": "LIVE_ROUTE_SUCCESS",
                "status_code": "LIVE_READY",
                "provider": "TomTom Calculate Route API",
                "is_live": True,
                "is_cached": False,
                "is_fallback": False,
                "travel_time_minutes": tomtom_route["travel_time_minutes"],
                "travel_time_seconds": tomtom_route["travel_time_seconds"],
                "traffic_delay_minutes": tomtom_route["traffic_delay_minutes"],
                "traffic_delay_seconds": tomtom_route["traffic_delay_seconds"],
                "distance_km": round(tomtom_route["length_meters"] / 1000.0, 2),
                "departure_time": tomtom_route.get("departure_time"),
                "arrival_time": tomtom_route.get("arrival_time"),
                "observation_time": tomtom_route.get("observation_time"),
                "retrieved_time": tomtom_route.get("retrieved_time"),
                "confidence": 0.95,
                "route_points": tomtom_route.get("points", primary_polylines),
                "alternatives": tomtom_route.get("alternatives", []),
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
                "source": "TomTom Calculate Route API",
                "provenance": DataProvenance.TOMTOM_LIVE_API.value,
                "active_events": active_events,
                "has_active_events": len(active_events) > 0,
                "horizon_date": target_date,
                "horizon_time": target_time,
                "primary_lane_guidance": primary_lane_guidance,
                "recommended_lane_guidance": recommended_lane_guidance,
                "primary_polylines": tomtom_route.get("points", primary_polylines),
                "recommended_polylines": recommended_polylines,
                "evaluated_at": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S IST")
            }
        else:
            fallback_err = self.tomtom_client.last_error or "TomTom Routing API unreachable or credentials unauthorized."
            result = {
                "origin_road": orig["road_id"],
                "origin_name": orig["road_name"],
                "destination_road": dest["road_id"],
                "destination_name": dest["road_name"],
                "status": "FALLBACK_TOPOLOGICAL",
                "status_code": "CONFIGURED_UNREACHABLE" if self.is_live_key_configured() else "BASELINE_SNAPSHOT",
                "provider": "Empirical Bengaluru Topology (Fallback)",
                "is_live": False,
                "is_cached": False,
                "is_fallback": True,
                "fallback_reason": f"{fallback_err} Displaying calibrated Bengaluru topology route.",
                "travel_time_minutes": topological_est_time,
                "travel_time_seconds": int(topological_est_time * 60),
                "traffic_delay_minutes": topological_delay,
                "traffic_delay_seconds": int(topological_delay * 60),
                "distance_km": transit_dist_km,
                "departure_time": f"{target_date}T{target_time}:00 IST",
                "arrival_time": None,
                "observation_time": now_iso(),
                "retrieved_time": now_iso(),
                "confidence": 0.85,
                "route_points": primary_polylines,
                "alternatives": [
                    {
                        "alternative_id": 1,
                        "name": f"Bypass via {recommended_route_names[1] if len(recommended_route_names) > 2 else 'Express Arterial'}",
                        "travel_time_minutes": round(max(5.0, topological_est_time - time_saved), 1),
                        "traffic_delay_minutes": round(max(0.0, topological_delay - time_saved), 1),
                        "points": recommended_polylines
                    }
                ] if is_rerouted else [],
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
                "source": "Empirical Live Baseline",
                "provenance": DataProvenance.EMPIRICAL_BASELINE.value,
                "active_events": active_events,
                "has_active_events": len(active_events) > 0,
                "horizon_date": target_date,
                "horizon_time": target_time,
                "primary_lane_guidance": primary_lane_guidance,
                "recommended_lane_guidance": recommended_lane_guidance,
                "primary_polylines": primary_polylines,
                "recommended_polylines": recommended_polylines,
                "evaluated_at": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S IST")
            }

        with self._lock:
            self._live_route_cache[cache_key] = (now_ts, result)

        return result

    def get_heatmap_telemetry(self) -> Dict[str, Any]:
        """
        Calculates spatial traffic density heatmap coordinates for Google Maps HeatmapLayer.
        Computes Greenshields macroscopic density k = q / v and normalized weights.
        """
        corridors = self.get_corridor_telemetry()
        heatmap_points: List[Dict[str, Any]] = []

        intensity_weights = {
            "Low": 0.25,
            "Moderate": 0.55,
            "High": 0.85,
            "Severe": 1.00
        }

        for c in corridors:
            r_id = c["road_id"]
            coords = get_corridor_coordinates(r_id)
            if not coords:
                gps = BENGALURU_CORRIDOR_GPS.get(r_id)
                if gps:
                    coords = [[gps["lat"], gps["lon"]]]

            spd = max(5.0, float(c.get("current_speed", 35.0)))
            vol = float(c.get("vehicle_count", 25000))
            # Macroscopic density k = q / v (vehicles per kilometer)
            density_k = round(vol / spd, 1)
            cap_util = float(c.get("capacity_utilization", 50.0))
            los = c.get("congestion_level", "Moderate")

            # Weight calibrated in [0.20, 1.00]
            base_w = intensity_weights.get(los, 0.5)
            norm_weight = round(min(1.0, max(0.2, (cap_util / 100.0) * 0.7 + base_w * 0.3)), 3)

            for pt in coords:
                heatmap_points.append({
                    "lat": pt[0],
                    "lng": pt[1],
                    "weight": norm_weight,
                    "intensity": base_w,
                    "density_k": density_k,
                    "congestion": los,
                    "road_id": r_id,
                    "road_name": c.get("road_name", r_id),
                    "speed_kmh": spd,
                    "vehicle_count": int(vol),
                    "capacity_utilization": cap_util
                })

        return {
            "status": "success",
            "point_count": len(heatmap_points),
            "max_weight": 1.0,
            "points": heatmap_points,
            "timestamp": now_iso()
        }

    def inject_vision_telemetry(self, corridor_id: str, vision_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Injects real-time computer vision camera telemetry into the live corridor state.
        Normalizes vehicle counts via calculate_scaled_volume to prevent XGBoost covariate shift.
        Recalculates Webster dynamic signal cycle times (C0) and triggers route advisories.
        """
        target_id = corridor_id if corridor_id in ROAD_REGISTRY else "RD_BLR_04"
        meta = ROAD_REGISTRY[target_id]

        density_info = vision_metrics.get("traffic_density", {})
        kinematics = vision_metrics.get("kinematics", {})
        pcu_info = vision_metrics.get("pcu_telemetry", {})

        topo = (self.predictor.topology or {}).get(target_id, {})
        gps = BENGALURU_CORRIDOR_GPS.get(target_id, {})
        free_flow_speed = float(gps.get("free_flow", topo.get("avg_speed", 50.0)))

        occ_pct = float(density_info.get("average_occupancy_pct", density_info.get("peak_occupancy_pct", 0.0)))
        raw_speed = float(kinematics.get("space_mean_speed_kmh", 0.0))
        speed_val = max(5.0, min(raw_speed, free_flow_speed))
        baseline_vol = float(topo.get("avg_volume", 32000.0))
        design_capacity = float(topo.get("capacity", max(baseline_vol * 1.25, 1.0)))

        # Keep this explicitly heuristic until Phase 2 replaces it with measured flow.
        scaled_vol = calculate_scaled_volume(baseline_vol, occ_pct)
        spi = calculate_spi(speed_val, free_flow_speed)
        los = classify_spi_los(spi)
        cap_util = calculate_capacity_utilization(scaled_vol, design_capacity)

        # Forward pass through XGBoost Predictor
        now_dt = datetime.now(ZoneInfo("Asia/Kolkata"))
        feats = make_feature_vector(
            road_id=target_id,
            vehicle_count=int(scaled_vol),
            average_speed=speed_val,
            capacity_utilization=cap_util,
            congestion_level=los,
            hour=now_dt.hour,
            day_of_week=now_dt.weekday(),
            is_weekend=(now_dt.weekday() >= 5)
        )
        pred_class, prob_dist = self.predictor.predict_segment(feats)

        # Dynamic Webster Signal Re-balancing
        from traffic_system.simulation.signal_optimizer import WebsterSignalOptimizer
        optimizer = WebsterSignalOptimizer()
        signal_calc = optimizer.optimize_intersection_signals(
            ns_volume_pcu=float(scaled_vol),
            ew_volume_pcu=float(scaled_vol) * 0.65,
            ns_lanes=meta.get("lanes", 4),
            ew_lanes=2
        )

        with self._lock:
            self._telemetry_cache[target_id] = {
                "road_id": target_id,
                "road_name": get_road_name(target_id),
                "city_zone": meta.get("zone", "Central Business District"),
                "current_speed": round(speed_val, 1),
                "free_flow_speed": free_flow_speed,
                "speed_deficit": round(free_flow_speed - speed_val, 1),
                "vehicle_count": int(scaled_vol),
                "congestion_level": los,
                "spi": spi,
                "capacity_utilization": cap_util,
                "data_provenance": "Uploaded-video CV measurement (advisory; uncalibrated proxy)",
                "last_updated": now_iso()
            }

        return {
            "status": "success",
            "message": f"CV metrics applied to advisory corridor state {target_id} (not a physical signal actuation)",
            "corridor_id": target_id,
            "road_name": get_road_name(target_id),
            "telemetry": {
                "proxy_speed_kmh": round(speed_val, 1),
                "scaled_volume_pcu_per_hr": int(scaled_vol),
                "occupancy_pct": occ_pct,
                "current_los": los,
                "spi": spi
            },
            "next_hour_forecast": {
                "predicted_congestion": pred_class,
                "probabilities": prob_dist
            },
            "webster_signal_actuation": signal_calc,
            "timestamp": now_iso()
        }

    def inject_traffic_measurement(self, measurement: Any) -> Dict[str, Any]:
        """
        Ingests a validated TrafficMeasurement contract object or payload
        into the live corridor telemetry state, updates metrics, executes
        XGBoost forward pass and Webster signal optimization.
        """
        from traffic_system.core.measurement import TrafficMeasurement, MeasurementValidationError
        if isinstance(measurement, dict):
            msr = TrafficMeasurement.from_dict(measurement)
        elif isinstance(measurement, TrafficMeasurement):
            msr = measurement
        else:
            raise MeasurementValidationError("Payload must be a TrafficMeasurement or valid dict.")

        target_id = msr.corridor_id if msr.corridor_id in ROAD_REGISTRY else "RD_BLR_04"
        meta = ROAD_REGISTRY[target_id]
        topo = (self.predictor.topology or {}).get(target_id, {})
        gps = BENGALURU_CORRIDOR_GPS.get(target_id, {})
        free_flow_speed = float(gps.get("free_flow", topo.get("avg_speed", 50.0)))

        speed_val = max(5.0, min(float(msr.speed.get("value_kmh") or 35.0), free_flow_speed))
        baseline_vol = float(topo.get("avg_volume", 32000.0))
        design_capacity = float(topo.get("capacity", max(baseline_vol * 1.25, 1.0)))

        flow_pcu = msr.flow.get("pcu_per_h")
        if flow_pcu is not None and flow_pcu > 0:
            effective_vol = float(flow_pcu)
        elif msr.flow.get("vph") is not None and msr.flow.get("vph") > 0:
            effective_vol = float(msr.flow["vph"])
        else:
            effective_vol = calculate_scaled_volume(baseline_vol, msr.occupancy_pct)

        spi = calculate_spi(speed_val, free_flow_speed)
        los = classify_spi_los(spi)
        cap_util = calculate_capacity_utilization(effective_vol, design_capacity)

        now_dt = datetime.now(ZoneInfo("Asia/Kolkata"))
        feats = make_feature_vector(
            road_id=target_id,
            vehicle_count=int(effective_vol),
            average_speed=speed_val,
            capacity_utilization=cap_util,
            congestion_level=los,
            hour=now_dt.hour,
            day_of_week=now_dt.weekday(),
            is_weekend=(now_dt.weekday() >= 5)
        )
        pred_class, prob_dist = self.predictor.predict_segment(feats)

        from traffic_system.simulation.signal_optimizer import WebsterSignalOptimizer
        optimizer = WebsterSignalOptimizer()
        signal_calc = optimizer.optimize_intersection_signals(
            ns_volume_pcu=float(effective_vol),
            ew_volume_pcu=float(effective_vol) * 0.65,
            ns_lanes=meta.get("lanes", 4),
            ew_lanes=2
        )

        with self._lock:
            self._telemetry_cache[target_id] = {
                "road_id": target_id,
                "road_name": get_road_name(target_id),
                "city_zone": meta.get("zone", "Central Business District"),
                "current_speed": round(speed_val, 1),
                "free_flow_speed": free_flow_speed,
                "speed_deficit": round(free_flow_speed - speed_val, 1),
                "vehicle_count": int(effective_vol),
                "congestion_level": los,
                "spi": spi,
                "capacity_utilization": cap_util,
                "data_provenance": f"Measurement {msr.measurement_id} ({msr.provenance.get('source', 'cv')})",
                "last_measurement": msr.to_dict(),
                "last_updated": now_iso()
            }

        return {
            "status": "success",
            "message": f"TrafficMeasurement ingested into corridor {target_id}",
            "corridor_id": target_id,
            "road_name": get_road_name(target_id),
            "measurement": msr.to_dict(),
            "telemetry": {
                "speed_kmh": round(speed_val, 1),
                "effective_volume_pcu_per_hr": int(effective_vol),
                "occupancy_pct": msr.occupancy_pct,
                "los": los,
                "spi": spi,
                "capacity_utilization": cap_util
            },
            "next_hour_forecast": {
                "predicted_congestion": pred_class,
                "probabilities": prob_dist
            },
            "webster_signal_actuation": signal_calc,
            "timestamp": now_iso()
        }

    def get_corridor_state(self, corridor_id: str) -> Optional[Dict[str, Any]]:
        """Returns the latest telemetry/measurement state for a specific corridor without network calls."""
        cid = str(corridor_id or "").strip().upper()
        if cid not in ROAD_REGISTRY:
            return None
        with self._lock:
            state = self._telemetry_cache.get(cid)
            if state:
                return dict(state)
        # Baseline fallback without triggering external network calls in offline/test environments
        topo = (self.predictor.topology or {}).get(cid, {})
        gps = BENGALURU_CORRIDOR_GPS.get(cid, {})
        free_flow_speed = float(gps.get("free_flow", topo.get("avg_speed", 50.0)))
        baseline_vol = float(topo.get("avg_volume", 32000.0))
        return {
            "road_id": cid,
            "road_name": get_road_name(cid),
            "city_zone": ROAD_REGISTRY[cid].get("zone", "Central Business District"),
            "current_speed": free_flow_speed,
            "free_flow_speed": free_flow_speed,
            "speed_deficit": 0.0,
            "vehicle_count": int(baseline_vol),
            "congestion_level": "Moderate",
            "spi": 100.0,
            "capacity_utilization": 50.0,
            "data_provenance": "Empirical Baseline (Offline)",
            "last_updated": now_iso()
        }


_LIVE_BRIDGE: Optional[LiveTrafficDataBridge] = None

def get_live_bridge() -> LiveTrafficDataBridge:
    global _LIVE_BRIDGE
    if _LIVE_BRIDGE is None:
        _LIVE_BRIDGE = LiveTrafficDataBridge()
    return _LIVE_BRIDGE
