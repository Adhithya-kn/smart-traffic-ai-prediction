"""
traffic_system/core/time_utils.py - Unified Temporal Parsing & Range Calculations
Eliminates duplicated 12h/24h time parsing and minute normalization (DRY Principle).
"""

from typing import Tuple

def parse_time_parts(time_str: str, default: Tuple[int, int] = (17, 0)) -> Tuple[int, int]:
    """
    Robust parser handling 24-hour ('17:30', '09:00') and 12-hour ('05:30 PM', '09:00 AM') formats.
    Returns (hour, minute) as integers (0 <= hour <= 23, 0 <= minute <= 59).
    """
    try:
        t = str(time_str).strip().upper()
        is_pm = "PM" in t
        is_am = "AM" in t
        clean = t.replace("PM", "").replace("AM", "").strip()
        parts = clean.split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0

        if is_pm and h < 12:
            h += 12
        elif is_am and h == 12:
            h = 0

        return max(0, min(23, h)), max(0, min(59, m))
    except Exception:
        return default

def time_to_minutes(time_str: str) -> int:
    """Converts a time string into elapsed minutes from midnight (0 to 1439)."""
    h, m = parse_time_parts(time_str)
    return h * 60 + m

def is_time_in_range(target_time: str, start_time: str, end_time: str) -> bool:
    """
    Checks if target_time falls within [start_time, end_time].
    Handles overnight wrap-around intervals (e.g. 22:00 to 04:00).
    """
    t_m = time_to_minutes(target_time)
    s_m = time_to_minutes(start_time)
    e_m = time_to_minutes(end_time)

    if s_m <= e_m:
        return s_m <= t_m <= e_m
    else:
        # Crosses midnight
        return t_m >= s_m or t_m <= e_m
