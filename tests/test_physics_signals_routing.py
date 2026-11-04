"""
tests/test_physics_signals_routing.py - Verification of Traffic Physics, Signals, Routing & Disclaimers
Validates all 24 Bengaluru corridors, Webster signal cycle bounds, Greenshields continuity,
counterfactual simulation assumptions, dispatch recommendations, and required advisory disclaimers.
"""

import pytest
import math
from traffic_system.core.road_registry import (
    ROAD_REGISTRY,
    CORRIDOR_GEO_REGISTRY,
    get_road_repository,
    get_road_name,
    get_corridor_lane_info,
    match_places_to_corridors
)
from traffic_system.core.traffic_physics import (
    calculate_spi,
    classify_spi_los,
    classify_speed_los,
    classify_vc_los,
    calculate_capacity_utilization,
    greenshields_speed_from_density,
    greenshields_flow_from_density,
    calculate_maximum_capacity,
    bpr_travel_time,
    speed_to_travel_time_minutes
)
from traffic_system.simulation.signal_optimizer import (
    WebsterSignalOptimizer,
    get_hcm_los,
    MINIMUM_GREEN_TIME_SEC,
    MAXIMUM_CYCLE_SEC,
    MINIMUM_CYCLE_SEC
)
from traffic_system.simulation.counterfactual import (
    PolicySimulator,
    compute_pcu,
    greenshields_equilibrium
)
from traffic_system.dispatch.recommender import generate_action_directive
from traffic_system.junction.junction_service import JunctionService
from traffic_system.routing.navigator import RouteNavigator, UrbanTopologyGraph
from traffic_system.computer_vision.incident_detector import IncidentDetector
from traffic_system.computer_vision.schemas import DetectionBox
from traffic_system.models.predictor import TrafficPredictor
from traffic_system.events.event_manager import EventManager


class TestRoadRegistryAndCorridors:
    """Verifies all 24 corridor IDs, coordinates, names, zones, lane counts and connectivity."""

    def test_all_24_corridors_registered(self):
        expected_ids = [f"RD_BLR_{i:02d}" for i in range(1, 25)]
        assert len(expected_ids) == 24
        for r_id in expected_ids:
            assert r_id in ROAD_REGISTRY, f"Missing {r_id} in ROAD_REGISTRY"
            assert r_id in CORRIDOR_GEO_REGISTRY, f"Missing {r_id} in CORRIDOR_GEO_REGISTRY"

            info = ROAD_REGISTRY[r_id]
            geo = CORRIDOR_GEO_REGISTRY[r_id]

            # Names and zones
            assert info["bangalore_name"], f"Empty bangalore_name for {r_id}"
            assert info["city_zone"], f"Empty city_zone for {r_id}"
            assert info["intersection_name"], f"Empty intersection_name for {r_id}"

            # Geometry and limits
            assert geo["lanes"] >= 2, f"Invalid lanes {geo['lanes']} for {r_id}"
            assert len(geo["lane_breakdown"]) >= 2
            assert geo["speed_limit_kmh"] > 0
            assert len(geo["coordinates"]) >= 2
            for lat, lon in geo["coordinates"]:
                assert 12.80 <= lat <= 13.15, f"Latitude {lat} out of Bengaluru bounds for {r_id}"
                assert 77.45 <= lon <= 77.85, f"Longitude {lon} out of Bengaluru bounds for {r_id}"

    def test_repository_pattern_and_fuzzy_search(self):
        repo = get_road_repository()
        all_corridors = repo.list_all()
        assert len(all_corridors) == 24

        corr_01 = repo.get_by_id("RD_BLR_01")
        assert corr_01 is not None
        assert corr_01.bangalore_name == "100 Feet Road"
        assert corr_01.city_zone == "Indiranagar"

        # Fuzzy search
        matches = match_places_to_corridors("Silk Board", limit=3)
        assert len(matches) > 0
        assert matches[0]["road_id"] == "RD_BLR_11"


class TestTrafficPhysicsCalculations:
    """Verifies physical units, capacity bounds, and macroscopic traffic formulas."""

    def test_speed_performance_index(self):
        assert calculate_spi(50.0, 50.0) == 100.0
        assert calculate_spi(25.0, 50.0) == 50.0
        assert calculate_spi(0.0, 50.0) == 0.0
        assert classify_spi_los(85.0) == "Low"
        assert classify_spi_los(60.0) == "Moderate"
        assert classify_spi_los(40.0) == "High"
        assert classify_spi_los(20.0) == "Severe"

    def test_greenshields_continuity_models(self):
        vf = 60.0
        kj = 120.0

        # At zero density, speed is free flow speed
        assert greenshields_speed_from_density(0.0, vf, kj) == vf

        # At jam density, speed is 0
        assert greenshields_speed_from_density(kj, vf, kj) == 0.0

        # Flow at k=0 is 0
        assert greenshields_flow_from_density(0.0, vf, kj) == 0.0

        # Flow at k=kj is 0
        assert greenshields_flow_from_density(kj, vf, kj) == 0.0

        # Maximum flow occurs at critical density kc = kj / 2 = 60.0 veh/km
        flow_mid = greenshields_flow_from_density(60.0, vf, kj)
        flow_below = greenshields_flow_from_density(40.0, vf, kj)
        flow_above = greenshields_flow_from_density(80.0, vf, kj)
        assert flow_mid > flow_below
        assert flow_mid > flow_above

        # Theoretical capacity per lane
        q_max = calculate_maximum_capacity(vf, kj, lanes=1)
        # q_max = (vf * kj) / 4 = (60 * 120) / 4 = 1800 veh/h
        assert q_max == 1800.0

    def test_bpr_and_travel_time(self):
        t0 = 60.0  # seconds
        # At zero volume, travel time is t0
        t_free = bpr_travel_time(t0, volume=0.0, capacity=1000.0)
        assert t_free == 60.0

        # At V/C = 1.0 with alpha=0.15, T = 60 * (1 + 0.15) = 69.0s
        t_cap = bpr_travel_time(t0, volume=1000.0, capacity=1000.0, alpha=0.15, beta=4.0)
        assert t_cap == 69.0

        # Travel time in minutes
        assert speed_to_travel_time_minutes(distance_km=10.0, speed_kmh=60.0) == 10.0


class TestWebsterSignalOptimizer:
    """Verifies Webster cycle calculations, phase allocations, minimum green times and maximum cycle limits."""

    def test_webster_optimal_cycle_and_phase_splits(self):
        optimizer = WebsterSignalOptimizer(saturation_flow_per_lane=1800.0)
        res = optimizer.optimize_intersection_signals(
            ns_volume_pcu=800.0,
            ew_volume_pcu=600.0,
            ns_lanes=2,
            ew_lanes=2
        )

        assert MINIMUM_CYCLE_SEC <= res["optimal_cycle_sec"] <= MAXIMUM_CYCLE_SEC
        assert res["ns_green_sec"] >= MINIMUM_GREEN_TIME_SEC
        assert res["ew_green_sec"] >= MINIMUM_GREEN_TIME_SEC
        assert res["amber_sec"] == 3.0
        assert res["all_red_sec"] == 1.0

        # Verify simulation tags and advisory disclaimer (no claim of direct physical control)
        assert res["is_simulated"] is True
        assert res["is_recommendation_only"] is True
        assert "advisory recommendations" in res["disclaimer"].lower()

    def test_webster_minimum_green_enforcement_under_asymmetry(self):
        optimizer = WebsterSignalOptimizer()
        # High asymmetry: tiny EW volume, heavy NS volume
        res = optimizer.optimize_intersection_signals(
            ns_volume_pcu=2500.0,
            ew_volume_pcu=50.0,
            ns_lanes=2,
            ew_lanes=1
        )
        assert res["ew_green_sec"] >= MINIMUM_GREEN_TIME_SEC
        assert res["ns_green_sec"] >= MINIMUM_GREEN_TIME_SEC

    def test_webster_maximum_cycle_clamping_under_oversaturation(self):
        optimizer = WebsterSignalOptimizer()
        # Extreme oversaturation: volumes far exceeding capacity (Y >= 1.0)
        res = optimizer.optimize_intersection_signals(
            ns_volume_pcu=5000.0,
            ew_volume_pcu=4000.0,
            ns_lanes=1,
            ew_lanes=1
        )
        assert res["optimal_cycle_sec"] <= MAXIMUM_CYCLE_SEC
        assert res["level_of_service"].startswith("LOS")


class TestJunctionServiceTelemetryAndDisclaimers:
    """Verifies telemetry inputs and clearly labeled simulated values without claiming automatic control."""

    def test_junction_telemetry_simulation_metadata(self):
        predictor = TrafficPredictor()
        event_mgr = EventManager()
        service = JunctionService(predictor, event_mgr)

        telemetry = service.get_junction_telemetry(
            road_id="RD_BLR_01",
            hour=17,
            minute=30
        )

        assert telemetry["is_simulated"] is True
        assert telemetry["provenance"] == "Simulation"
        assert telemetry["is_recommendation_only"] is True
        assert "actual" in telemetry["disclaimer"].lower() or "actuation" in telemetry["disclaimer"].lower()
        assert telemetry["signals"]["optimal_cycle_sec"] >= MINIMUM_CYCLE_SEC
        assert telemetry["signals"]["ns_green_seconds"] >= MINIMUM_GREEN_TIME_SEC

        # Vehicles are explicitly simulated
        for veh in telemetry["tracked_vehicles"]:
            assert veh["is_simulated"] is True

    def test_junction_telemetry_input_clamping(self):
        predictor = TrafficPredictor()
        event_mgr = EventManager()
        service = JunctionService(predictor, event_mgr)

        # Out of bounds hour/minute should be clamped cleanly without crash
        telemetry = service.get_junction_telemetry(road_id="INVALID_ID", hour=99, minute=-10)
        assert telemetry["road_id"] in ROAD_REGISTRY


class TestCounterfactualPolicySimulator:
    """Verifies baseline assumptions, scenario inputs, and counterfactual simulated outcome labeling."""

    def test_counterfactual_simulation_assumptions_and_metadata(self):
        predictor = TrafficPredictor()
        simulator = PolicySimulator(predictor)

        res = simulator.simulate_zone_policy(
            zone="Indiranagar",
            alpha_demand=0.15,
            beta_speed=0.10,
            hour=18,
            day_of_week=3
        )

        assert res["is_simulated"] is True
        assert res["provenance"] == "Simulation"
        assert "disclaimer" in res
        assert "baseline_assumptions" in res
        assert "scenario_inputs" in res

        assumptions = res["baseline_assumptions"]
        assert "Greenshields" in assumptions["macroscopic_model"]
        assert assumptions["jam_density_k_jam_veh_per_km"] == 120.0
        assert assumptions["pcu_modal_weights"]["car"] == 1.0


class TestDispatchRecommender:
    """Verifies evidence, priority, recommendation rationale, and estimated benefit labeling."""

    def test_action_directive_evidence_and_benefits(self):
        directive = generate_action_directive(
            road_id="RD_BLR_01",
            zone="Indiranagar",
            congestion="Severe",
            has_active_event=True,
            event_name="Metro Construction",
            volume_vph=2100,
            lanes=2
        )

        # Priority structure
        assert directive["priority"]["rank"] == 1
        assert directive["priority"]["urgency"] == "Immediate"

        # Evidence
        assert "evidence" in directive
        assert directive["evidence"]["estimated_volume_vph"] == 2100
        assert directive["evidence"]["congestion_level"] == "Severe"

        # Rationale
        assert "recommendation_rationale" in directive
        assert "RD_BLR_01" in directive["recommendation_rationale"]

        # Estimated Benefit (clearly labeled as simulated)
        benefit = directive["estimated_benefit"]
        assert benefit["is_simulated"] is True
        assert "Simulated counterfactual estimate" in benefit["benefit_provenance"]

        # Advisory Disclaimer
        assert directive["is_simulated"] is True
        assert directive["is_recommendation_only"] is True
        assert "municipal traffic-control infrastructure" in directive["disclaimer"]


class TestRouteNavigatorAndTopology:
    """Verifies graph edges, route costs, incident penalties, and travel-time estimates."""

    def test_graph_connectivity_across_all_24_corridors(self):
        predictor = TrafficPredictor()
        if not predictor.topology:
            predictor.load_artifacts()
        graph = UrbanTopologyGraph(predictor.topology)

        roads = list(predictor.topology.keys())
        assert len(roads) == 24

        # Verify full network reachability
        for origin in roads[:6]:
            for destination in roads[18:]:
                path, time = graph.dijkstra_shortest_path(origin, destination, {})
                assert len(path) >= 2
                assert path[0] == origin
                assert path[-1] == destination
                assert time > 0.0

    def test_route_evaluation_disclaimers_and_estimated_time_saved(self):
        predictor = TrafficPredictor()
        event_mgr = EventManager()
        navigator = RouteNavigator(predictor, event_mgr)

        evaluation = navigator.evaluate_route("RD_BLR_01", "RD_BLR_11", "2026-11-04", "18:00")
        eval_dict = evaluation.to_dict()

        assert eval_dict["is_simulated"] is True
        assert "estimated_time_saved_minutes" in eval_dict
        assert eval_dict["disclaimer"]
        assert "simulated model estimates" in eval_dict["disclaimer"].lower()


class TestIncidentDetectorValidation:
    """Verifies event heuristics calibration validation and summary counting."""

    def test_heuristics_calibration_validation(self):
        detector = IncidentDetector(
            stall_dwell_sec=12.0,
            stall_speed_threshold_kmh=2.0,
            wrong_way_angle_deg=130.0,
            decel_shockwave_threshold_mps2=-3.8
        )
        report = detector.validate_heuristics_calibration()
        assert report["is_calibrated"] is True
        assert len(report["issues"]) == 0

    def test_incident_summary_counts(self):
        detector = IncidentDetector()
        box = DetectionBox(x1=100.0, y1=100.0, x2=150.0, y2=150.0, confidence=0.9, class_id=2, class_name="car")

        # Trigger deceleration incident
        detector.update(track_id=1, box=box, speed_kmh=60.0, frame_idx=0, fps=10.0)
        detector.update(track_id=1, box=box, speed_kmh=10.0, frame_idx=3, fps=10.0)

        summary = detector.get_summary()
        assert summary["total_incidents"] >= 1
        assert summary["deceleration_shockwaves"] >= 1
