"""
tests/test_architecture_solid_dry.py - Verification for SOLID, DRY & Design Patterns
"""

import pytest
from traffic_system.core.traffic_physics import (
    calculate_spi,
    classify_spi_los,
    classify_speed_los,
    classify_vc_los,
    calculate_capacity_utilization,
    calculate_scaled_volume,
)
from traffic_system.core.time_utils import (
    parse_time_parts,
    time_to_minutes,
    is_time_in_range,
)
from traffic_system.core.entities import (
    CONGESTION_RANKS,
    RANK_TO_CONGESTION,
    congestion_rank,
    rank_to_congestion,
    make_feature_vector,
)
from traffic_system.core.road_registry import (
    get_road_repository,
    get_intersection_name,
    CachedRoadRepository,
)
from traffic_system.models.strategies.base import IPredictionStrategy
from traffic_system.live.adapters.base import ITelemetryAdapter, IWeatherAdapter, CorridorObservation, WeatherSnapshot


def test_traffic_physics_spi_and_los():
    spi = calculate_spi(current_speed=45.0, free_flow_speed=60.0)
    assert spi == 75.0
    assert classify_spi_los(spi) == "Low"

    assert calculate_spi(0.0, 60.0) == 0.0
    assert calculate_spi(60.0, 60.0) == 100.0

    assert classify_speed_los(45.0) == "Low"
    assert classify_speed_los(30.0) == "Moderate"
    assert classify_speed_los(20.0) == "High"
    assert classify_speed_los(8.0) == "Severe"

    assert classify_vc_los(0.3) == "Low"
    assert classify_vc_los(0.65) == "Moderate"
    assert classify_vc_los(0.85) == "High"
    assert classify_vc_los(0.95) == "Severe"


def test_time_utils_and_ranges():
    assert parse_time_parts("17:30") == (17, 30)
    assert parse_time_parts("05:30 PM") == (17, 30)
    assert parse_time_parts("12:00 AM") == (0, 0)
    assert parse_time_parts("12:00 PM") == (12, 0)
    assert parse_time_parts("invalid", default=(9, 0)) == (9, 0)

    assert time_to_minutes("01:30") == 90
    assert is_time_in_range("09:00", "08:00", "10:00") is True
    assert is_time_in_range("11:00", "08:00", "10:00") is False
    assert is_time_in_range("23:30", "22:00", "04:00") is True
    assert is_time_in_range("02:00", "22:00", "04:00") is True
    assert is_time_in_range("12:00", "22:00", "04:00") is False


def test_entities_and_congestion_ranks():
    assert congestion_rank("Low") == 0
    assert congestion_rank("Moderate") == 1
    assert congestion_rank("High") == 2
    assert congestion_rank("Severe") == 3
    assert congestion_rank("Unknown") == 1

    assert rank_to_congestion(0) == "Low"
    assert rank_to_congestion(3) == "Severe"

    vec = make_feature_vector(
        road_id="RD_BLR_01",
        intersection_id="INT_01",
        city_zone="Indiranagar",
        vehicle_count=1200,
        average_speed=32.0,
        capacity_utilization=65.0,
        congestion_level="Moderate",
        hour=17,
        day_of_week=2,
        is_weekend=0,
    )
    assert vec["road_id"] == "RD_BLR_01"
    assert vec["congestion_level"] == "Moderate"
    assert vec["hour"] == 17


def test_corridor_repository_pattern():
    repo = get_road_repository()
    assert isinstance(repo, CachedRoadRepository)

    all_corridors = repo.list_all()
    assert len(all_corridors) >= 20

    rd1 = repo.get_by_id("RD_BLR_01")
    assert rd1 is not None
    assert rd1.road_id == "RD_BLR_01"

    int_name = get_intersection_name(rd1.intersection_id)
    assert int_name == rd1.intersection_name

    indi_corridors = repo.list_by_zone("Indiranagar")
    assert len(indi_corridors) > 0
    assert all(c.city_zone == "Indiranagar" for c in indi_corridors)


def test_interfaces_and_abstract_contracts():
    class MockStrategy(IPredictionStrategy):
        def predict(self, features):
            return "Moderate", {"Moderate": 1.0}

        def predict_batch(self, batch_features):
            return [self.predict(f) for f in batch_features]

        def explain(self, features):
            return [{"feature": "speed", "contribution": 0.5}]

    strategy = MockStrategy()
    cls, probs = strategy.predict({})
    assert cls == "Moderate"
    batch_res = strategy.predict_batch([{}, {}])
    assert len(batch_res) == 2
