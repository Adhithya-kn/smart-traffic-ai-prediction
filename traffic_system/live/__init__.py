"""
traffic_system.live - Real-time traffic probe and environmental telemetry subsystem.
"""

from .bridge import LiveTrafficDataBridge, get_live_bridge

__all__ = ["LiveTrafficDataBridge", "get_live_bridge"]
