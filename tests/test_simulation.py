"""
tests/test_simulation.py - Test Suite for Counterfactual Policy Simulator & Directives
"""

import pytest
from traffic_system.events.event_manager import EventManager
from traffic_system.models.predictor import TrafficPredictor
from traffic_system.simulation.counterfactual import PolicySimulator
from traffic_system.dispatch.recommender import generate_action_directive

def test_counterfactual_simulation():
    predictor = TrafficPredictor()
    predictor.load_artifacts()
    evt_mgr = EventManager()
    simulator = PolicySimulator(predictor, evt_mgr)

    sim = simulator.simulate_zone_policy(
        zone="Indiranagar",
        alpha_demand=0.20,
        beta_speed=0.10,
        hour=17,
        day_of_week=3
    )

    assert sim["total_segments_evaluated"] > 0, "Should evaluate segments in Indiranagar"
    assert sim["policy_parameters"]["alpha_demand_reduction"] == 0.20
    assert sim["summary"]["improved_segments"] >= 0
    assert "Low" in sim["distribution_after"]

def test_action_directives():
    directive = generate_action_directive("RD_BLR_01", "Indiranagar", "Severe", True, "Stadium Match")
    assert directive["directive_code"] == "DIR-SEV-01"
    assert directive["priority_level"] == "URGENT_PRIORITY_1"
    assert "ALERT: SEVERE DELAYS" in directive["vms_broadcast_message"]
    assert "STADIUM MATCH" in directive["vms_broadcast_message"]
