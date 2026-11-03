"""
traffic_system/events/event_manager.py - Traffic Event Scheduling & Impact Engine
"""

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from traffic_system.config import EVENTS_DB_PATH
from traffic_system.core.entities import TrafficEvent, EventType
from traffic_system.core.time_utils import time_to_minutes, is_time_in_range
from traffic_system.core.fs_utils import atomic_json_dump
from traffic_system.core.road_registry import get_road_name

normalize_time_to_minutes = time_to_minutes

class EventManager:
    """Manages scheduled and real-time municipal traffic events across city zones."""
    def __init__(self, db_path: Path = EVENTS_DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.events: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        self.latest_alert: Optional[Dict[str, Any]] = None
        self._load_events()

    def _load_events(self):
        with self._lock:
            if self.db_path.exists():
                try:
                    with open(self.db_path, "r", encoding="utf-8") as f:
                        self.events = json.load(f)
                        if self.events:
                            self._align_live_events_dates()
                            for e in self.events:
                                if "is_published" not in e:
                                    e["is_published"] = False
                                if "affected_roads" in e and not e.get("affected_road_names"):
                                    e["affected_road_names"] = [get_road_name(r) for r in e["affected_roads"]]
                            return
                except Exception:
                    self.events = []
        
        self.events = [
            {
                "id": "EVT_001",
                "name": "Indiranagar 100 Feet Road Cultural Procession",
                "event_type": EventType.FESTIVAL.value,
                "city_zone": "Indiranagar",
                "affected_roads": ["RD_BLR_01", "RD_BLR_04"],
                "start_time": "08:00",
                "end_time": "22:00",
                "date": "2026-03-18",
                "end_date": "2026-10-31",
                "dataset_date": "2026-03-18",
                "active_dates": ["2026-03-18", "2026-04-30"],
                "severity_boost": 2,
                "volume_surge_vph": 650,
                "capacity_constriction_pct": 45,
                "speed_impact_pct": 55,
                "is_historical": False,
                "is_published": False,
                "description": "Annual cultural procession causing localized traffic diversion along 100 Feet Road and CMH Road."
            },
            {
                "id": "EVT_002",
                "name": "Central Silk Board Metro Interchange Expansion",
                "event_type": EventType.ROADWORK.value,
                "city_zone": "Electronic City South",
                "affected_roads": ["RD_BLR_11", "RD_BLR_06"],
                "start_time": "08:00",
                "end_time": "19:00",
                "date": "2026-03-06",
                "end_date": "2026-10-31",
                "dataset_date": "2026-03-06",
                "active_dates": ["2026-03-18", "2026-03-06", "2026-04-30"],
                "severity_boost": 2,
                "volume_surge_vph": 750,
                "capacity_constriction_pct": 50,
                "speed_impact_pct": 60,
                "is_historical": False,
                "is_published": False,
                "description": "Emergency structural concrete curing and flyover expansion joint maintenance at Silk Board Junction."
            },
            {
                "id": "EVT_003",
                "name": "Koramangala Sony World Junction Monsoon Drainage",
                "event_type": EventType.ROADWORK.value,
                "city_zone": "Koramangala",
                "affected_roads": ["RD_BLR_12", "RD_BLR_10"],
                "start_time": "08:00",
                "end_time": "21:00",
                "date": "2026-03-02",
                "end_date": "2026-10-31",
                "dataset_date": "2026-03-02",
                "active_dates": ["2026-03-02", "2026-03-18", "2026-04-30"],
                "severity_boost": 2,
                "volume_surge_vph": 550,
                "capacity_constriction_pct": 40,
                "speed_impact_pct": 50,
                "is_historical": False,
                "is_published": False,
                "description": "Stormwater culvert upgrade restricting lane capacity and creating queue spillback toward Sarjapur Road."
            },
            {
                "id": "EVT_004",
                "name": "M.G. Road CBD Commercial Concourse & Event",
                "event_type": EventType.STADIUM_EVENT.value,
                "city_zone": "M.G. Road CBD",
                "affected_roads": ["RD_BLR_02", "RD_BLR_14"],
                "start_time": "08:00",
                "end_time": "20:00",
                "date": "2026-03-12",
                "end_date": "2026-10-31",
                "dataset_date": "2026-03-12",
                "active_dates": ["2026-03-12", "2026-03-18", "2026-04-30"],
                "severity_boost": 1,
                "volume_surge_vph": 500,
                "capacity_constriction_pct": 35,
                "speed_impact_pct": 45,
                "is_historical": False,
                "is_published": False,
                "description": "High-density pedestrian crossing and VIP convoy escort affecting Anil Kumble and Trinity Circles."
            },
            {
                "id": "EVT_005",
                "name": "Whitefield ITPL Tech Innovation Expo",
                "event_type": EventType.STADIUM_EVENT.value,
                "city_zone": "Whitefield",
                "affected_roads": ["RD_BLR_07", "RD_BLR_09"],
                "start_time": "08:00",
                "end_time": "20:00",
                "date": "2026-03-09",
                "end_date": "2026-10-31",
                "dataset_date": "2026-03-09",
                "active_dates": ["2026-03-09", "2026-03-18", "2026-04-30"],
                "severity_boost": 2,
                "volume_surge_vph": 600,
                "capacity_constriction_pct": 40,
                "speed_impact_pct": 55,
                "is_historical": False,
                "is_published": False,
                "description": "Heavy corporate shuttle convoy concentration and attendee arrival surge near Hope Farm Crossing."
            },
            {
                "id": "EVT_006",
                "name": "Hebbal Flyover Airport Corridor Structural Maintenance",
                "event_type": EventType.ROADWORK.value,
                "city_zone": "Hebbal North",
                "affected_roads": ["RD_BLR_05", "RD_BLR_03"],
                "start_time": "08:00",
                "end_time": "19:00",
                "date": "2026-03-17",
                "end_date": "2026-10-31",
                "dataset_date": "2026-03-17",
                "active_dates": ["2026-03-17", "2026-03-18", "2026-04-30"],
                "severity_boost": 2,
                "volume_surge_vph": 650,
                "capacity_constriction_pct": 40,
                "speed_impact_pct": 50,
                "is_historical": False,
                "is_published": False,
                "description": "Flyover cloverleaf resurfacing limiting airport expressway throughput on Ballari Road."
            },
            {
                "id": "EVT_HIST_01",
                "name": "Hebbal North Metro Construction Phase 1",
                "event_type": EventType.ROADWORK.value,
                "city_zone": "Hebbal North",
                "affected_roads": ["RD_BLR_03", "RD_BLR_05"],
                "start_time": "09:00",
                "end_time": "18:00",
                "date": "2026-01-15",
                "end_date": "2026-01-15",
                "dataset_date": "2026-01-15",
                "active_dates": ["2026-01-15"],
                "severity_boost": 2,
                "volume_surge_vph": 600,
                "capacity_constriction_pct": 45,
                "speed_impact_pct": 50,
                "is_historical": True,
                "is_published": False,
                "description": "Historical pier casting causing arterial slow down along Bellary Road."
            },
            {
                "id": "EVT_HIST_02",
                "name": "M.G. Road Republic Day Parade & Divergence",
                "event_type": EventType.FESTIVAL.value,
                "city_zone": "M.G. Road CBD",
                "affected_roads": ["RD_BLR_02", "RD_BLR_14"],
                "start_time": "06:00",
                "end_time": "14:00",
                "date": "2026-01-26",
                "end_date": "2026-01-26",
                "dataset_date": "2026-01-26",
                "active_dates": ["2026-01-26"],
                "severity_boost": 3,
                "volume_surge_vph": 850,
                "capacity_constriction_pct": 60,
                "speed_impact_pct": 70,
                "is_historical": True,
                "is_published": False,
                "description": "Historical central parade assembly causing complete diversion across Anil Kumble Circle."
            },
            {
                "id": "EVT_HIST_03",
                "name": "Electronic City Expressway Surface Milling",
                "event_type": EventType.ROADWORK.value,
                "city_zone": "Electronic City South",
                "affected_roads": ["RD_BLR_06", "RD_BLR_11"],
                "start_time": "22:00",
                "end_time": "06:00",
                "date": "2026-02-10",
                "end_date": "2026-02-10",
                "dataset_date": "2026-02-10",
                "active_dates": ["2026-02-10"],
                "severity_boost": 1,
                "volume_surge_vph": 400,
                "capacity_constriction_pct": 30,
                "speed_impact_pct": 35,
                "is_historical": True,
                "is_published": False,
                "description": "Historical nocturnal asphalt milling on elevated expressway lanes."
            },
            {
                "id": "EVT_HIST_04",
                "name": "Indiranagar 100ft Rd Underground Cable Laying",
                "event_type": EventType.ROADWORK.value,
                "city_zone": "Indiranagar",
                "affected_roads": ["RD_BLR_01", "RD_BLR_04"],
                "start_time": "10:00",
                "end_time": "17:00",
                "date": "2026-02-18",
                "end_date": "2026-02-18",
                "dataset_date": "2026-02-18",
                "active_dates": ["2026-02-18"],
                "severity_boost": 2,
                "volume_surge_vph": 550,
                "capacity_constriction_pct": 40,
                "speed_impact_pct": 45,
                "is_historical": True,
                "is_published": False,
                "description": "Historical utility conduit placement restricting curb lanes on 100 Feet Road."
            },
            {
                "id": "EVT_HIST_05",
                "name": "Whitefield Outer Ring Rd Drainage Restoration",
                "event_type": EventType.ROADWORK.value,
                "city_zone": "Whitefield",
                "affected_roads": ["RD_BLR_07", "RD_BLR_09"],
                "start_time": "08:00",
                "end_time": "18:00",
                "date": "2026-02-24",
                "end_date": "2026-02-24",
                "dataset_date": "2026-02-24",
                "active_dates": ["2026-02-24"],
                "severity_boost": 2,
                "volume_surge_vph": 580,
                "capacity_constriction_pct": 42,
                "speed_impact_pct": 48,
                "is_historical": True,
                "is_published": False,
                "description": "Historical storm-culvert repair at Hope Farm junction bottleneck."
            },
            {
                "id": "EVT_HIST_06",
                "name": "Koramangala Sony World Flyover Expansion Inspection",
                "event_type": EventType.ROADWORK.value,
                "city_zone": "Koramangala",
                "affected_roads": ["RD_BLR_10", "RD_BLR_12"],
                "start_time": "11:00",
                "end_time": "16:00",
                "date": "2026-03-01",
                "end_date": "2026-03-01",
                "dataset_date": "2026-03-01",
                "active_dates": ["2026-03-01"],
                "severity_boost": 1,
                "volume_surge_vph": 450,
                "capacity_constriction_pct": 35,
                "speed_impact_pct": 40,
                "is_historical": True,
                "is_published": False,
                "description": "Historical non-destructive structural acoustic testing on elevated flyover."
            }
        ]
        with self._lock:
            self._save_events()

    def _align_live_events_dates(self):
        """Dynamically ensures ongoing municipal events align with the current operational day."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        try:
            today_str = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
        except Exception:
            today_str = datetime.now().strftime("%Y-%m-%d")

        modified = False
        for e in self.events:
            if e.get("is_historical", False):
                continue
            e_start = e.get("date", "")
            e_end = e.get("end_date", e_start)
            if e_end and e_end >= today_str:
                active_dates = e.setdefault("active_dates", [e_start] if e_start else [])
                if today_str not in active_dates:
                    active_dates.append(today_str)
                    modified = True
                if e_start and e_start < today_str and e.get("id", "").startswith("EVT_BLR_LIVE_"):
                    e["date"] = today_str
                    modified = True
        if modified:
            self._save_events()

    def _save_events(self):
        with self._lock:
            atomic_json_dump(self.events, self.db_path)

    def get_all_events(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.events)

    def get_latest_alert(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.latest_alert

    def get_scheduled_events(self, zone: Optional[str] = None, published_only: bool = True) -> List[Dict[str, Any]]:
        """Returns upcoming/current scheduled events.
        If published_only is True (default for Commuters), only events broadcasted by Traffic Management are returned.
        If published_only is False (for Traffic Authority), all staged and published events are returned.
        """
        from datetime import datetime
        from zoneinfo import ZoneInfo
        try:
            today_str = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
        except Exception:
            today_str = datetime.now().strftime("%Y-%m-%d")

        with self._lock:
            result = []
            for e in self.events:
                if e.get("is_historical", False):
                    continue
                if published_only and not e.get("is_published", False):
                    continue
                if zone and e["city_zone"].lower() != zone.lower():
                    continue

                evt_copy = dict(e)
                e_start = evt_copy.get("date", "")
                e_end = evt_copy.get("end_date", e_start)
                if e_end and e_end >= today_str and e_start and e_start <= today_str:
                    evt_copy["date"] = today_str
                result.append(evt_copy)
            return result

    def get_historical_events(self, zone: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns last month's historical calibration events with observed volume surge data."""
        with self._lock:
            return [
                e for e in self.events 
                if e.get("is_historical", False) and (not zone or e["city_zone"].lower() == zone.lower())
            ]

    def publish_event(self, event_id: str, updates: Optional[Dict[str, Any]] = None) -> tuple[bool, str, Dict[str, Any]]:
        """Publishes or updates and broadcasts an event network-wide to all road users."""
        with self._lock:
            for evt in self.events:
                if evt.get("id") == event_id:
                    if updates:
                        for k in ["name", "event_type", "city_zone", "start_time", "end_time", "date", "description"]:
                            if k in updates and updates[k] is not None:
                                evt[k] = str(updates[k]).strip()
                        if "affected_roads" in updates and updates["affected_roads"]:
                            evt["affected_roads"] = list(updates["affected_roads"])
                            evt["affected_road_names"] = [get_road_name(r) for r in evt["affected_roads"]]
                        if "volume_surge_vph" in updates:
                            evt["volume_surge_vph"] = int(updates["volume_surge_vph"])
                        if "severity_boost" in updates:
                            evt["severity_boost"] = int(updates["severity_boost"])
                    evt["is_published"] = True
                    if "affected_roads" in evt and not evt.get("affected_road_names"):
                        evt["affected_road_names"] = [get_road_name(r) for r in evt["affected_roads"]]
                    now_iso = datetime.now(timezone.utc).isoformat()
                    evt["published_at"] = now_iso
                    evt["updated_at"] = now_iso

                    road_names = evt.get("affected_road_names") or [get_road_name(r) for r in evt.get("affected_roads", [])]
                    roads_str = ", ".join(road_names)
                    surge_str = f"+{evt.get('volume_surge_vph', 0)} veh/hr"
                    self.latest_alert = {
                        "id": evt["id"],
                        "name": evt["name"],
                        "event_type": evt["event_type"],
                        "city_zone": evt["city_zone"],
                        "affected_roads": evt["affected_roads"],
                        "affected_road_names": road_names,
                        "volume_surge_vph": evt.get("volume_surge_vph", 0),
                        "speed_impact_pct": evt.get("speed_impact_pct", 0),
                        "start_time": evt["start_time"],
                        "end_time": evt["end_time"],
                        "date": evt.get("date", ""),
                        "timestamp": now_iso,
                        "action": "PUBLISHED",
                        "headline": f"🚨 Early Warning: {evt['name']}",
                        "message": f"Traffic Management broadcasted scheduled disruption in {evt['city_zone']} affecting corridors {roads_str} ({surge_str})."
                    }
                    self._save_events()
                    return True, f"Event '{evt['name']}' published and broadcasted to road users.", evt
            return False, f"Event {event_id} not found.", {}

    def unpublish_event(self, event_id: str) -> tuple[bool, str]:
        """Retracts an event from public road user broadcast."""
        with self._lock:
            for evt in self.events:
                if evt.get("id") == event_id:
                    evt["is_published"] = False
                    now_iso = datetime.now(timezone.utc).isoformat()
                    evt["updated_at"] = now_iso
                    self.latest_alert = {
                        "id": evt["id"],
                        "name": evt["name"],
                        "action": "RETRACTED",
                        "timestamp": now_iso,
                        "headline": f"Notice: Event Retracted",
                        "message": f"Municipal event '{evt['name']}' has been retracted by Traffic Management."
                    }
                    self._save_events()
                    return True, f"Event '{evt['name']}' retracted from broadcast."
            return False, f"Event {event_id} not found."

    def add_event(self, event_data: Dict[str, Any]) -> tuple[bool, str, Dict[str, Any]]:
        required = ["name", "event_type", "city_zone", "affected_roads", "start_time", "end_time", "date"]
        for req in required:
            if req not in event_data or not event_data[req]:
                return False, f"Missing required event field: {req}", {}

        with self._lock:
            name_clean = str(event_data["name"]).strip()
            date_clean = str(event_data["date"]).strip()

            for existing in self.events:
                if existing.get("name") == name_clean and existing.get("date") == date_clean:
                    existing["affected_roads"] = list(event_data["affected_roads"])
                    existing["affected_road_names"] = [get_road_name(r) for r in existing["affected_roads"]]
                    existing["start_time"] = str(event_data["start_time"]).strip()
                    existing["end_time"] = str(event_data["end_time"]).strip()
                    existing["severity_boost"] = int(event_data.get("severity_boost", 1))
                    existing["volume_surge_vph"] = int(event_data.get("volume_surge_vph", 200))
                    existing["is_published"] = bool(event_data.get("is_published", True))
                    now_iso = datetime.now(timezone.utc).isoformat()
                    existing["updated_at"] = now_iso
                    if existing["is_published"]:
                        existing["published_at"] = now_iso
                        roads_str = ", ".join(existing["affected_road_names"])
                        self.latest_alert = {
                            "id": existing["id"],
                            "name": existing["name"],
                            "event_type": existing["event_type"],
                            "city_zone": existing["city_zone"],
                            "affected_roads": existing["affected_roads"],
                            "affected_road_names": existing["affected_road_names"],
                            "volume_surge_vph": existing.get("volume_surge_vph", 0),
                            "speed_impact_pct": existing.get("speed_impact_pct", 0),
                            "start_time": existing["start_time"],
                            "end_time": existing["end_time"],
                            "date": existing.get("date", ""),
                            "timestamp": now_iso,
                            "action": "PUBLISHED",
                            "headline": f"🚨 Early Warning: {existing['name']}",
                            "message": f"Traffic Management updated scheduled disruption in {existing['city_zone']} affecting corridors {roads_str}."
                        }
                    self._save_events()
                    return True, "Traffic event updated successfully.", existing

            event_id = f"EVT_{len(self.events) + 1:03d}"
            is_pub = bool(event_data.get("is_published", True))
            now_iso = datetime.now(timezone.utc).isoformat()
            new_roads = list(event_data["affected_roads"])
            new_road_names = [get_road_name(r) for r in new_roads]
            new_event = {
                "id": event_id,
                "name": str(event_data["name"]).strip(),
                "event_type": str(event_data["event_type"]).strip(),
                "city_zone": str(event_data["city_zone"]).strip(),
                "affected_roads": new_roads,
                "affected_road_names": new_road_names,
                "start_time": str(event_data["start_time"]).strip(),
                "end_time": str(event_data["end_time"]).strip(),
                "date": str(event_data["date"]).strip(),
                "severity_boost": int(event_data.get("severity_boost", 1)),
                "volume_surge_vph": int(event_data.get("volume_surge_vph", 200)),
                "capacity_constriction_pct": int(event_data.get("capacity_constriction_pct", 0)),
                "speed_impact_pct": int(event_data.get("speed_impact_pct", 20)),
                "is_historical": bool(event_data.get("is_historical", False)),
                "is_published": is_pub,
                "published_at": now_iso if is_pub else None,
                "updated_at": now_iso,
                "description": str(event_data.get("description", "")).strip()
            }
            if is_pub:
                roads_str = ", ".join(new_event.get("affected_roads", []))
                self.latest_alert = {
                    "id": new_event["id"],
                    "name": new_event["name"],
                    "event_type": new_event["event_type"],
                    "city_zone": new_event["city_zone"],
                    "affected_roads": new_event["affected_roads"],
                    "volume_surge_vph": new_event.get("volume_surge_vph", 0),
                    "speed_impact_pct": new_event.get("speed_impact_pct", 0),
                    "start_time": new_event["start_time"],
                    "end_time": new_event["end_time"],
                    "date": new_event.get("date", ""),
                    "timestamp": now_iso,
                    "action": "PUBLISHED",
                    "headline": f"🚨 Early Warning: {new_event['name']}",
                    "message": f"Traffic Management broadcasted scheduled disruption in {new_event['city_zone']} affecting corridors {roads_str}."
                }
            self.events.append(new_event)
            self._save_events()
            return True, "Traffic event created successfully.", new_event

    def delete_event(self, event_id: str) -> tuple[bool, str]:
        """Deletes an event by its unique ID and atomically persists the update."""
        with self._lock:
            original_len = len(self.events)
            self.events = [e for e in self.events if e.get("id") != event_id]
            if len(self.events) < original_len:
                self._save_events()
                return True, f"Event {event_id} removed successfully."
            return False, f"Event {event_id} not found."

    def upsert_events_batch(self, events_list: List[Dict[str, Any]]) -> tuple[int, int]:
        """
        Atomically upserts a batch of validated incident events into storage.
        Deduplicates primarily by 'id', falling back to (name, date).
        Returns (inserted_count, updated_count).
        """
        inserted = 0
        updated = 0
        now_iso = datetime.now(timezone.utc).isoformat()

        with self._lock:
            id_index = {e.get("id"): idx for idx, e in enumerate(self.events) if e.get("id")}
            name_date_index = {(e.get("name", "").lower(), e.get("date", "")): idx for idx, e in enumerate(self.events)}

            for evt in events_list:
                eid = evt.get("id")
                nd_key = (evt.get("name", "").lower(), evt.get("date", ""))

                target_idx = None
                if eid and eid in id_index:
                    target_idx = id_index[eid]
                elif nd_key in name_date_index:
                    target_idx = name_date_index[nd_key]

                if target_idx is not None:
                    self.events[target_idx].update(evt)
                    self.events[target_idx]["updated_at"] = now_iso
                    updated += 1
                else:
                    clean_evt = dict(evt)
                    if "id" not in clean_evt or not clean_evt["id"]:
                        clean_evt["id"] = f"EVT_{len(self.events) + 1:03d}"
                    clean_evt.setdefault("is_published", True)
                    clean_evt.setdefault("published_at", now_iso)
                    clean_evt.setdefault("updated_at", now_iso)
                    self.events.append(clean_evt)
                    id_index[clean_evt["id"]] = len(self.events) - 1
                    name_date_index[nd_key] = len(self.events) - 1
                    inserted += 1

            if inserted > 0 or updated > 0:
                self._save_events()
        return inserted, updated

    def sync_bengaluru_live_incidents(self, zone: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Non-blocking ingestion helper: fetches live Bengaluru incidents outside the lock,
        then atomically commits them in memory and on disk.
        """
        from traffic_system.events.bengaluru_incident_adapter import get_bengaluru_incident_adapter
        adapter = get_bengaluru_incident_adapter()
        incidents = adapter.fetch_live_tomtom_incidents()
        if zone and zone.lower() != "all":
            incidents = [e for e in incidents if e.get("city_zone", "").lower() == zone.strip().lower()]

        self.upsert_events_batch(incidents)
        return self.find_active_events(zone=zone, include_historical=False, published_only=False)

    def find_active_events(self, road_id: Optional[str] = None, zone: Optional[str] = None,
                           date: Optional[str] = None, time_str: Optional[str] = None,
                           include_historical: bool = False,
                           published_only: bool = False) -> List[Dict[str, Any]]:
        """Filters events active for a given date, time, road, or zone using robust time-window matching."""
        active = []
        with self._lock:
            for evt in self.events:
                if not include_historical and not date and evt.get("is_historical", False):
                    continue

                if published_only and not evt.get("is_historical", False) and not evt.get("is_published", False):
                    continue

                if date:
                    evt_start = evt.get("date", "")
                    evt_end = evt.get("end_date", evt_start)
                    active_dates = evt.get("active_dates", [evt_start])
                    date_matches = (
                        (date in active_dates) or
                        (date == evt_start) or
                        (date == evt.get("dataset_date")) or
                        (evt_end >= evt_start and evt_start <= date <= evt_end)
                    )
                    if not date_matches:
                        continue

                if time_str:
                    if not is_time_in_range(time_str, evt["start_time"], evt["end_time"]):
                        continue

                if zone and evt["city_zone"].lower() != zone.lower():
                    continue

                if road_id and road_id not in evt["affected_roads"]:
                    continue

                evt_copy = dict(evt)
                if date and not evt.get("is_historical", False):
                    evt_copy["date"] = date
                active.append(evt_copy)
        return active
