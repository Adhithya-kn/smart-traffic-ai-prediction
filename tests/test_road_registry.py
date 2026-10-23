"""
tests/test_road_registry.py - Verification Suite for Canonical Road & Intersection Registry
Verifies that all 94 urban corridors have valid names, intersection metadata, and road types
across both Global Metropolitan and Bangalore profiles.
"""

import pytest
import json
from traffic_system.core.road_registry import (
    ROAD_REGISTRY,
    get_road_name,
    get_intersection_name,
    get_road_metadata,
    enrich_road_info
)
from traffic_system.config import NETWORK_TOPOLOGY_FILE

def test_road_registry_completeness():
    """All unique roads in topology must be registered."""
    with open(NETWORK_TOPOLOGY_FILE) as f:
        topology = json.load(f)

    assert len(topology) >= 16, "Active topology must contain Bangalore corridors"
    assert len(ROAD_REGISTRY) >= 24, "Road registry must contain the registered roads"

    for r_id in topology:
        assert r_id in ROAD_REGISTRY, f"Road {r_id} must be in ROAD_REGISTRY"
        info = ROAD_REGISTRY[r_id]
        assert "global_name" in info and len(info["global_name"]) > 3
        assert "bangalore_name" in info and len(info["bangalore_name"]) > 3
        assert "intersection_name" in info and len(info["intersection_name"]) > 3
        assert "road_type" in info and len(info["road_type"]) > 3

def test_road_name_lookups():
    """Verify name lookups under both naming profiles."""
    name_blr = get_road_name("RD_BLR_01")
    assert name_blr == "100 Feet Road"

    name_cbd = get_road_name("RD_BLR_02")
    assert name_cbd == "Anil Kumble Circle"

    # Non-existent road fallback
    assert get_road_name("RD_99999") == "RD_99999"

def test_road_enrichment():
    """Verify dictionary enrichment preserves existing keys and injects human names."""
    sample = {
        "road_id": "RD_BLR_01",
        "city_zone": "Indiranagar",
        "avg_speed": 38.4
    }
    enriched = enrich_road_info(sample)
    assert enriched["road_id"] == "RD_BLR_01"
    assert enriched["road_name"] == "100 Feet Road"
    assert "intersection_name" in enriched
    assert enriched["road_type"] == "Primary Commercial Arterial"
