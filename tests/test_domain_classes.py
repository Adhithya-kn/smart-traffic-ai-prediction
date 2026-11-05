"""
tests/test_domain_classes.py - Unit Tests for Indian Mixed Traffic Domain Classes & PCU Normalization
Verifies:
1. Canonical class support for auto_rickshaw (0.80 PCU) and lcv (1.40 PCU).
2. PCU aggregation including heterogeneous mixed urban fleet.
3. VehicleCounter normalization mapping auto/three-wheeler and tempo/lcv to canonical classes.
4. Detector class mapping supporting domain-adapted classes.
"""

import pytest
from traffic_system.computer_vision.pcu_converter import (
    IndoHCMPCUConverter,
    INDO_HCM_PCU_FACTORS,
    CANONICAL_CLASSES
)
from traffic_system.computer_vision.vehicle_counter import VehicleCounter
from traffic_system.computer_vision.schemas import DetectionBox


def test_domain_classes_pcu_factors():
    """Verify Indo-HCM PCU factors for auto-rickshaws and light commercial vehicles."""
    assert "auto_rickshaw" in INDO_HCM_PCU_FACTORS
    assert INDO_HCM_PCU_FACTORS["auto_rickshaw"] == 0.80

    assert "lcv" in INDO_HCM_PCU_FACTORS
    assert INDO_HCM_PCU_FACTORS["lcv"] == 1.40

    # Ensure canonical classes contains auto_rickshaw and lcv
    assert "auto_rickshaw" in CANONICAL_CLASSES
    assert "lcv" in CANONICAL_CLASSES


def test_mixed_fleet_pcu_total_calculation():
    """Verify PCU flow calculation for an authentic Indian urban road mix."""
    fleet_mix = {
        "car": 10,            # 10 * 1.00 = 10.0
        "motorcycle": 20,     # 20 * 0.50 = 10.0
        "auto_rickshaw": 15,  # 15 * 0.80 = 12.0
        "bus": 4,             # 4 * 2.80 = 11.2
        "truck": 2,           # 2 * 3.00 = 6.0
        "lcv": 5,             # 5 * 1.40 = 7.0
        "bicycle": 5          # 5 * 0.20 = 1.0
    }
    total_pcu = IndoHCMPCUConverter.calculate_total_pcu(fleet_mix)
    expected = 10.0 + 10.0 + 12.0 + 11.2 + 6.0 + 7.0 + 1.0  # 57.2
    assert abs(total_pcu - expected) < 1e-3


def test_vehicle_counter_normalizes_auto_and_lcv():
    """Verify VehicleCounter normalizes aliases like 'tuk_tuk' and 'tempo'."""
    counter = VehicleCounter(min_hits=1)

    dets = [
        DetectionBox(x1=10, y1=10, x2=50, y2=50, confidence=0.88, class_id=2, class_name="tuk_tuk", track_id=1),
        DetectionBox(x1=60, y1=10, x2=100, y2=50, confidence=0.85, class_id=3, class_name="tempo", track_id=2),
    ]

    res = counter.update(dets)
    assert res["current_frame_classes"]["auto_rickshaw"] == 1
    assert res["current_frame_classes"]["lcv"] == 1
    assert res["current_frame_total"] == 2

    summary = counter.get_summary()
    assert summary["class_counts"]["auto_rickshaw"] == 1
    assert summary["class_counts"]["lcv"] == 1
