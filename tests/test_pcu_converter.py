"""
tests/test_pcu_converter.py - Unit Tests for Indo-HCM PCU Normalizer
Validates Indian Highway Capacity Manual vehicle factors, aggregate PCU, and hourly flow expansion.
"""

import pytest
from traffic_system.computer_vision.pcu_converter import IndoHCMPCUConverter, INDO_HCM_PCU_FACTORS


def test_pcu_factors_indo_hcm():
    assert IndoHCMPCUConverter.get_factor("car") == 1.00
    assert IndoHCMPCUConverter.get_factor("motorcycle") == 0.50
    assert IndoHCMPCUConverter.get_factor("bus") == 2.80
    assert IndoHCMPCUConverter.get_factor("truck") == 3.00
    assert IndoHCMPCUConverter.get_factor("auto") == 0.80
    assert IndoHCMPCUConverter.get_factor("unknown_vehicle") == 1.00


def test_pcu_aggregation_homogeneous_and_mixed():
    # 10 cars = 10.0 PCU
    assert IndoHCMPCUConverter.calculate_total_pcu({"car": 10}) == 10.0

    # 10 two-wheelers = 5.0 PCU
    assert IndoHCMPCUConverter.calculate_total_pcu({"motorcycle": 10}) == 5.0

    # 5 buses + 5 trucks = 5*2.8 + 5*3.0 = 14.0 + 15.0 = 29.0 PCU
    assert IndoHCMPCUConverter.calculate_total_pcu({"bus": 5, "truck": 5}) == 29.0

    # Typical Bangalore corridor mix
    mix = {"car": 20, "motorcycle": 40, "bus": 4, "truck": 2}
    # 20*1.0 + 40*0.5 + 4*2.8 + 2*3.0 = 20 + 20 + 11.2 + 6.0 = 57.2 PCU
    total_pcu = IndoHCMPCUConverter.calculate_total_pcu(mix)
    assert total_pcu == 57.2


def test_hourly_flow_expansion():
    # 60 PCU observed over 60 seconds -> 3600 PCU/hr
    flow_60s = IndoHCMPCUConverter.calculate_hourly_flow(total_pcu=60.0, duration_seconds=60.0)
    assert flow_60s == 3600.0

    # 10 PCU observed over 10 seconds -> 3600 PCU/hr
    flow_10s = IndoHCMPCUConverter.calculate_hourly_flow(total_pcu=10.0, duration_seconds=10.0)
    assert flow_10s == 3600.0


def test_mix_breakdown():
    mix = {"car": 10, "motorcycle": 20}
    breakdown = IndoHCMPCUConverter.get_mix_breakdown(mix)
    assert breakdown["total_raw_vehicles"] == 30
    assert breakdown["total_pcu"] == 20.0  # 10*1.0 + 20*0.5
    assert breakdown["classes"]["car"]["percentage_raw"] == round((10 / 30) * 100.0, 1)
    assert breakdown["classes"]["motorcycle"]["percentage_pcu"] == 50.0
