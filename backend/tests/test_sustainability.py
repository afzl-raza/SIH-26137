import sys
import os

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import main as main_module
from sustainability import estimate_savings, FUEL_L_PER_100KM, CO2_KG_PER_LITRE_DIESEL


def test_estimate_matches_hand_calculation():
    est = estimate_savings(baseline_km=100.0, optimized_km=80.0)
    assert est.km_saved == 20.0
    assert est.pct_km_saved == 20.0
    # 20 km * 9 L/100km = 1.8 L ; 1.8 L * 2.68 kg/L = 4.824 kg
    assert est.fuel_l_saved == pytest.approx(20.0 * FUEL_L_PER_100KM / 100.0)
    assert est.co2_kg_saved == pytest.approx(1.8 * CO2_KG_PER_LITRE_DIESEL, abs=0.01)
    assert est.is_estimate is True


def test_longer_optimized_plan_is_reported_as_negative_not_clamped():
    est = estimate_savings(baseline_km=50.0, optimized_km=55.0)
    assert est.km_saved == -5.0
    assert est.fuel_l_saved < 0
    assert est.co2_kg_saved < 0


def test_zero_baseline_does_not_divide_by_zero():
    assert estimate_savings(0.0, 0.0).pct_km_saved == 0.0


def test_negative_distance_rejected():
    with pytest.raises(ValueError):
        estimate_savings(-1.0, 5.0)


def test_endpoint_uses_real_greedy_baseline_on_the_stored_scenario():
    client = TestClient(main_module.app)
    gen = client.post("/api/problem/generate", json={
        "source": "synthetic", "num_nodes": 20, "num_jobs": 8, "num_vehicles": 2, "seed": 3
    }).json()
    config = {"algorithm": "qpso", "population_size": 6, "max_iterations": 6, "seed": 3}

    greedy = client.post("/api/optimize", json={
        "scenario_id": gen["scenario_id"], "config": {**config, "algorithm": "greedy"}
    }).json()

    resp = client.post("/api/sustainability", json={
        "scenario_id": gen["scenario_id"], "config": config,
        "optimized_distance_km": greedy["total_distance"] * 0.8,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["baseline_km"] == pytest.approx(greedy["total_distance"], abs=0.01)
    assert body["pct_km_saved"] == pytest.approx(20.0, abs=0.1)
    assert body["is_estimate"] is True
    assert body["fuel_l_per_100km"] == FUEL_L_PER_100KM


def test_endpoint_unknown_scenario_is_404():
    client = TestClient(main_module.app)
    resp = client.post("/api/sustainability", json={
        "scenario_id": "nope", "config": {"algorithm": "greedy"}, "optimized_distance_km": 10.0,
    })
    assert resp.status_code == 404
