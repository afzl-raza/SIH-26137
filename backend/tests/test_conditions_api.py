"""Integration tests for the dynamic-condition API surface.

Covers the part of Phase 5 that is easy to get subtly wrong: a condition
change must reach the optimizer through the route matrix, and the
content-addressed cache must never hand back a matrix computed under different
conditions.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import main as main_module
from models import OptimizationConfig
from problem_generator import compute_route_matrix, generate_synthetic_scenario
from realdata.cache import DiskCache
from realdata.conditions import ConditionRequest, apply_conditions, apply_incidents
from realdata.traffic_model import MODE_HEAVY, MODE_MODERATE, MODE_NORMAL, MODE_SEVERE
from realdata.weather import OpenMeteoProvider
from route_cache import ROUTE_MATRIX_CACHE, RouteMatrixCache, route_matrix_key

client = TestClient(main_module.app)


@pytest.fixture(autouse=True)
def isolated_route_cache():
    ROUTE_MATRIX_CACHE.clear()
    ROUTE_MATRIX_CACHE.reset_stats()
    yield
    ROUTE_MATRIX_CACHE.clear()
    ROUTE_MATRIX_CACHE.reset_stats()


@pytest.fixture
def offline_weather(monkeypatch):
    """Points the API's weather provider at a fake transport, so no test ever
    reaches Open-Meteo. Returns the call log."""
    calls = []

    def transport(url, params, timeout):
        calls.append(params)
        return {
            "current": {
                "time": "2026-09-19T10:00",
                "temperature_2m": 24.0,
                "precipitation": 3.0,
                "wind_speed_10m": 9.0,
                "weather_code": 65,  # heavy rain
            }
        }

    provider = OpenMeteoProvider(
        cache=DiskCache(root=Path(tempfile.mkdtemp(prefix="wxapi_"))),
        fetch_json=transport,
    )
    monkeypatch.setattr(main_module, "DEFAULT_WEATHER_PROVIDER", provider)
    import realdata.conditions as conditions_module
    monkeypatch.setattr(conditions_module, "DEFAULT_WEATHER_PROVIDER", provider)
    return calls


@pytest.fixture
def broken_weather(monkeypatch):
    """A weather provider whose upstream is down and which has nothing cached."""
    provider = OpenMeteoProvider(
        cache=DiskCache(root=Path(tempfile.mkdtemp(prefix="wxdead_"))),
        fetch_json=lambda url, params, timeout: (_ for _ in ()).throw(
            ConnectionError("open-meteo unreachable")
        ),
    )
    monkeypatch.setattr(main_module, "DEFAULT_WEATHER_PROVIDER", provider)
    import realdata.conditions as conditions_module
    monkeypatch.setattr(conditions_module, "DEFAULT_WEATHER_PROVIDER", provider)
    return provider


def _generate(**overrides):
    body = {"num_nodes": 24, "num_jobs": 10, "num_vehicles": 3, "seed": 42}
    body.update(overrides)
    response = client.post("/api/problem/generate", json=body)
    assert response.status_code == 200
    return response.json()


def _conditions(scenario_id, **overrides):
    body = {"scenario_id": scenario_id}
    body.update(overrides)
    return client.post("/api/scenario/conditions", json=body)


def _optimize(scenario_id, algorithm="qpso"):
    response = client.post("/api/optimize", json={
        "scenario_id": scenario_id,
        "config": {"algorithm": algorithm, "population_size": 15,
                   "max_iterations": 15, "seed": 42},
    })
    assert response.status_code == 200
    return response.json()


# =========================================== 13. condition metadata on the API

def test_generate_reports_condition_metadata_with_honest_defaults():
    body = _generate()

    assert body["traffic_source"] == "simulated"
    assert body["traffic_mode"] == MODE_NORMAL
    assert body["weather_source"] is None
    assert body["fallback_used"] is False


def test_applying_conditions_returns_full_condition_metadata(offline_weather):
    generated = _generate()

    response = _conditions(
        generated["scenario_id"], traffic_mode=MODE_HEAVY, weather_enabled=True
    )
    assert response.status_code == 200
    body = response.json()

    assert body["traffic_mode"] == MODE_HEAVY
    assert body["traffic_source"] == "simulated"
    assert body["weather_source"] == "network"
    assert body["weather_condition"] == "heavy_rain"
    assert body["fallback_used"] is False

    conditions = body["conditions"]
    assert conditions["traffic_is_simulated"] is True
    assert conditions["weather"]["multiplier"] > 1.0
    assert conditions["weather"]["is_real_observation"] is True
    assert conditions["updated_at"]
    assert conditions["signature"]


def test_simulated_traffic_is_never_labelled_live(offline_weather):
    generated = _generate()
    body = _conditions(generated["scenario_id"], traffic_mode=MODE_HEAVY).json()

    blob = str(body).lower()
    assert "live traffic" not in blob
    assert body["conditions"]["traffic_source"] == "simulated"
    assert "simulated" in body["conditions"]["traffic_provider"]


def test_condition_metadata_travels_on_the_scenario(offline_weather):
    generated = _generate()
    body = _conditions(generated["scenario_id"], traffic_mode=MODE_MODERATE).json()

    # The frontend reads conditions off the scenario it already holds.
    assert body["scenario"]["conditions"]["traffic_mode"] == MODE_MODERATE


def test_an_unknown_traffic_mode_is_a_client_error():
    generated = _generate()
    response = _conditions(generated["scenario_id"], traffic_mode="apocalyptic")

    assert response.status_code == 400
    assert "apocalyptic" in response.json()["detail"]


def test_the_external_traffic_provider_refuses_rather_than_fabricating():
    generated = _generate()
    response = _conditions(generated["scenario_id"], traffic_source="external")

    assert response.status_code == 400
    assert "external" in response.json()["detail"].lower()


# ================================================= 14. weather API + fallback

def test_weather_endpoint_returns_a_real_observation(offline_weather):
    response = client.get("/api/weather", params={"latitude": 26.83, "longitude": 80.93})

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "network"
    assert body["condition"] == "heavy_rain"
    assert body["fallback_used"] is False
    assert body["multiplier"] > 1.0


def test_weather_endpoint_locates_a_stored_scenario(offline_weather):
    generated = _generate()

    response = client.get("/api/weather", params={"scenario_id": generated["scenario_id"]})

    assert response.status_code == 200
    depot = next(n for n in generated["scenario"]["nodes"]
                 if n["id"] == generated["scenario"]["depot_node_id"])
    assert response.json()["latitude"] == pytest.approx(depot["lat"], abs=1e-3)


def test_weather_endpoint_requires_a_location():
    assert client.get("/api/weather").status_code == 422


def test_a_weather_outage_is_reported_as_a_fallback_not_as_fair_weather(broken_weather):
    generated = _generate()

    response = _conditions(
        generated["scenario_id"], traffic_mode=MODE_MODERATE, weather_enabled=True
    )
    assert response.status_code == 200
    body = response.json()

    assert body["weather_source"] == "fallback"
    assert body["fallback_used"] is True
    assert body["conditions"]["weather"]["is_real_observation"] is False
    assert body["conditions"]["weather"]["temperature_c"] is None
    # No weather effect is applied when there is no observation.
    assert body["conditions"]["weather_multiplier"] == 1.0


def test_optimization_still_works_when_weather_is_unavailable(broken_weather):
    """A weather outage must degrade to "no weather", never to "no routes"."""
    generated = _generate()
    _conditions(generated["scenario_id"], traffic_mode=MODE_HEAVY, weather_enabled=True)

    result = _optimize(generated["scenario_id"])

    assert result["routes"]
    assert result["total_cost"] > 0


# ============================= 7-9. conditions reach the optimizer, no stale cache

def test_a_traffic_level_change_changes_the_routing_costs():
    generated = _generate()
    scenario_id = generated["scenario_id"]

    before = _optimize(scenario_id)
    _conditions(scenario_id, traffic_mode=MODE_HEAVY)
    after = _optimize(scenario_id)

    assert after["total_travel_time"] > before["total_travel_time"]
    assert after["total_cost"] > before["total_cost"]


def test_a_weather_change_changes_the_routing_costs(offline_weather):
    generated = _generate()
    scenario_id = generated["scenario_id"]

    before = _optimize(scenario_id)
    _conditions(scenario_id, weather_enabled=True)
    after = _optimize(scenario_id)

    assert after["total_travel_time"] > before["total_travel_time"]


def test_an_incident_still_changes_the_routing_costs():
    """The pre-Phase-5 incident flow, unchanged from the client's side."""
    generated = _generate()
    scenario_id = generated["scenario_id"]

    before = _optimize(scenario_id)
    edge = generated["scenario"]["edges"][0]
    response = client.post("/api/traffic/update", json={
        "scenario_id": scenario_id,
        "updates": [{"source": edge["source"], "destination": edge["destination"],
                     "traffic_factor": 20.0}],
    })
    assert response.status_code == 200
    assert response.json()["updated_edges"] == 2

    after = _optimize(scenario_id)
    assert after["total_cost"] != before["total_cost"]


def test_traffic_update_sets_the_incident_axis_not_the_traffic_axis():
    generated = _generate()
    edge = generated["scenario"]["edges"][0]

    body = client.post("/api/traffic/update", json={
        "scenario_id": generated["scenario_id"],
        "updates": [{"source": edge["source"], "destination": edge["destination"],
                     "traffic_factor": 4.0}],
    }).json()

    disrupted = [e for e in body["scenario"]["edges"]
                 if {e["source"], e["destination"]} == {edge["source"], edge["destination"]}]
    assert disrupted
    for e in disrupted:
        assert e["incident_multiplier"] == 4.0
        assert e["traffic_multiplier"] == 1.0
        # With no traffic level and no weather applied, the effective factor is
        # exactly the number the client asked for - identical to pre-Phase-5.
        assert e["traffic_factor"] == 4.0


def test_an_incident_composes_with_an_active_traffic_level():
    generated = _generate()
    scenario_id = generated["scenario_id"]
    edge = generated["scenario"]["edges"][0]

    _conditions(scenario_id, traffic_mode=MODE_HEAVY)
    body = client.post("/api/traffic/update", json={
        "scenario_id": scenario_id,
        "updates": [{"source": edge["source"], "destination": edge["destination"],
                     "traffic_factor": 3.0}],
    }).json()

    disrupted = next(e for e in body["scenario"]["edges"]
                     if {e["source"], e["destination"]} == {edge["source"], edge["destination"]})
    assert disrupted["incident_multiplier"] == 3.0
    assert disrupted["traffic_multiplier"] > 1.0
    assert disrupted["traffic_factor"] == pytest.approx(
        disrupted["traffic_multiplier"] * disrupted["weather_multiplier"] * 3.0, abs=1e-5
    )


def test_a_traffic_level_change_changes_actual_route_selection():
    """The point of Phase 5: conditions must change *which way vehicles go*,
    not merely what the same route costs.

    This is why the traffic model varies congestion by road class. A single
    multiplier applied uniformly would scale every path equally and leave
    every shortest path exactly where it was.
    """
    scenario = generate_synthetic_scenario(num_nodes=30, num_jobs=15, num_vehicles=3, seed=42)

    normal = compute_route_matrix(apply_conditions(scenario, ConditionRequest(traffic_mode=MODE_NORMAL)))
    heavy = compute_route_matrix(apply_conditions(scenario, ConditionRequest(traffic_mode=MODE_HEAVY)))

    changed = sum(1 for pair, path in normal.paths.items() if heavy.paths.get(pair) != path)
    assert changed > 0, "heavy traffic left every shortest path unchanged"


# ================================================== 9. the cache, specifically

def test_identical_conditions_reuse_the_cached_matrix():
    cache = RouteMatrixCache()
    scenario = generate_synthetic_scenario(num_nodes=20, num_jobs=8, num_vehicles=3, seed=42)

    a = apply_conditions(scenario, ConditionRequest(traffic_mode=MODE_HEAVY))
    b = apply_conditions(scenario, ConditionRequest(traffic_mode=MODE_HEAVY))

    first = cache.get(a)
    second = cache.get(b)

    assert second is first
    assert cache.stats()["builds"] == 1


@pytest.mark.parametrize("first_mode,second_mode", [
    (MODE_NORMAL, MODE_MODERATE),
    (MODE_MODERATE, MODE_HEAVY),
    (MODE_HEAVY, MODE_SEVERE),
])
def test_a_traffic_change_invalidates_the_cached_matrix(first_mode, second_mode):
    cache = RouteMatrixCache()
    scenario = generate_synthetic_scenario(num_nodes=20, num_jobs=8, num_vehicles=3, seed=42)

    cache.get(apply_conditions(scenario, ConditionRequest(traffic_mode=first_mode)))
    cache.get(apply_conditions(scenario, ConditionRequest(traffic_mode=second_mode)))

    assert cache.stats()["builds"] == 2, "a changed traffic level must not reuse a matrix"


def test_a_weather_change_invalidates_the_cached_matrix():
    cache = RouteMatrixCache()
    scenario = generate_synthetic_scenario(num_nodes=20, num_jobs=8, num_vehicles=3, seed=42)

    from realdata.weather import WeatherObservation
    rainy = WeatherObservation(latitude=1.0, longitude=1.0, source="network", condition="rain")

    dry = apply_conditions(scenario, ConditionRequest(weather_enabled=False))
    wet = apply_conditions(
        scenario, ConditionRequest(weather_enabled=True), weather_observation=rainy
    )

    cache.get(dry)
    cache.get(wet)

    assert cache.stats()["builds"] == 2


def test_an_incident_change_invalidates_the_cached_matrix():
    cache = RouteMatrixCache()
    scenario = generate_synthetic_scenario(num_nodes=20, num_jobs=8, num_vehicles=3, seed=42)
    u, v = scenario.edges[0].source, scenario.edges[0].destination

    cache.get(scenario)
    disrupted, _ = apply_incidents(scenario, {(u, v): 6.0})
    cache.get(disrupted)

    assert cache.stats()["builds"] == 2


def test_the_cache_key_separates_conditions_that_multiply_to_the_same_total():
    """Defensive: two different condition states could in principle compose to
    the same effective travel time. Keying the individual multipliers means
    the matrices still get separate entries."""
    scenario = generate_synthetic_scenario(num_nodes=12, num_jobs=5, num_vehicles=2, seed=3)

    a = scenario.model_copy(deep=True)
    b = scenario.model_copy(deep=True)
    for edge in a.edges:
        edge.traffic_multiplier, edge.weather_multiplier = 2.0, 1.0
        edge.traffic_factor = 2.0
        edge.current_travel_time = edge.base_travel_time * 2.0
    for edge in b.edges:
        edge.traffic_multiplier, edge.weather_multiplier = 1.0, 2.0
        edge.traffic_factor = 2.0
        edge.current_travel_time = edge.base_travel_time * 2.0

    assert route_matrix_key(a) != route_matrix_key(b)


def test_the_cached_matrix_equals_a_fresh_computation_under_conditions():
    """The cache must be a pure speed-up, never a source of different numbers."""
    cache = RouteMatrixCache()
    scenario = apply_conditions(
        generate_synthetic_scenario(num_nodes=18, num_jobs=7, num_vehicles=2, seed=5),
        ConditionRequest(traffic_mode=MODE_HEAVY),
    )

    cached = cache.get(scenario)
    fresh = compute_route_matrix(scenario)

    assert cached.terminals == fresh.terminals
    assert (cached.time.array == fresh.time.array).all()
    assert (cached.dist.array == fresh.dist.array).all()


# ================================== 11-12. optimizers and benchmark still run

@pytest.mark.parametrize("algorithm", ["greedy", "pso", "ga", "qpso"])
def test_every_optimizer_still_runs_after_a_condition_change(algorithm, offline_weather):
    generated = _generate()
    _conditions(generated["scenario_id"], traffic_mode=MODE_HEAVY, weather_enabled=True)

    result = _optimize(generated["scenario_id"], algorithm=algorithm)

    assert result["routes"]
    assert result["total_travel_time"] > 0


def test_benchmark_runs_all_four_on_the_same_conditioned_scenario(offline_weather):
    generated = _generate()
    _conditions(generated["scenario_id"], traffic_mode=MODE_HEAVY, weather_enabled=True)

    response = client.post("/api/benchmark", json={
        "scenario_id": generated["scenario_id"],
        "config": {"algorithm": "qpso", "population_size": 12,
                   "max_iterations": 12, "seed": 42},
    })
    assert response.status_code == 200
    results = response.json()["results"]

    assert set(results) == {"greedy", "pso", "ga", "qpso", "qpso_memetic"}
    for result in results.values():
        assert result["routes"]


def test_a_benchmark_under_conditions_builds_the_matrix_once():
    """The five-algorithm benchmark must still be one build plus five hits,
    now that conditions are in the cache key. (Memetic QPSO fetches the
    matrix twice per run - once for itself, once via its internal
    GreedyOptimizer warm start - so 5 algorithms make 6 fetches total.)"""
    scenario = apply_conditions(
        generate_synthetic_scenario(num_nodes=18, num_jobs=7, num_vehicles=2, seed=9),
        ConditionRequest(traffic_mode=MODE_HEAVY),
    )
    ROUTE_MATRIX_CACHE.clear()
    ROUTE_MATRIX_CACHE.reset_stats()

    from optimizers.benchmark import run_benchmark
    run_benchmark(scenario, OptimizationConfig(population_size=8, max_iterations=8, seed=42))

    stats = ROUTE_MATRIX_CACHE.stats()
    assert stats["builds"] == 1
    assert stats["hits"] == 5


# ========================================================== 10. reproducibility

def test_same_seed_same_conditions_gives_the_same_optimization_result(offline_weather):
    first_id = _generate(seed=42)["scenario_id"]
    _conditions(first_id, traffic_mode=MODE_HEAVY, weather_enabled=True)
    first = _optimize(first_id)

    second_id = _generate(seed=42)["scenario_id"]
    _conditions(second_id, traffic_mode=MODE_HEAVY, weather_enabled=True)
    second = _optimize(second_id)

    assert first["total_cost"] == second["total_cost"]
    assert first["total_travel_time"] == second["total_travel_time"]
    assert [r["job_ids"] for r in first["routes"]] == [r["job_ids"] for r in second["routes"]]


# ============================================ conditions on a real OSM network

@pytest.fixture
def osm_scenario():
    """A scenario built from the real OpenStreetMap extract fixture, so the
    road-class part of the traffic model is exercised against genuine
    `highway` tags rather than synthetic edges."""
    import json

    from realdata.geocoding import resolve_location
    from realdata.osm_loader import load_osm_graph
    from realdata.osm_scenario import osm_graph_to_scenario

    payload = json.loads(
        (Path(__file__).parent / "fixtures" / "overpass_real_extract.json")
        .read_text(encoding="utf-8")
    )
    location = resolve_location(latitude=26.8381, longitude=80.9346, radius_m=600)
    graph = load_osm_graph(
        location,
        cache=DiskCache(root=Path(tempfile.mkdtemp(prefix="osmcond_"))),
        post_overpass=lambda url, query, timeout: payload,
    )
    return osm_graph_to_scenario(graph, num_jobs=10, num_vehicles=3, seed=42)


def test_osm_road_classes_congest_in_the_documented_order(osm_scenario):
    """Arterials absorb more of the congestion level than residential streets.
    A documented model assumption - asserted so it cannot drift silently."""
    heavy = apply_conditions(osm_scenario, ConditionRequest(traffic_mode=MODE_HEAVY))

    by_class = {}
    for edge in heavy.edges:
        by_class.setdefault(edge.highway, set()).add(round(edge.traffic_multiplier, 4))

    # Each class gets exactly one multiplier, and they order as documented.
    assert all(len(v) == 1 for v in by_class.values())
    flat = {k: v.pop() for k, v in by_class.items()}
    assert flat["primary"] > flat["secondary"] > flat["tertiary"] > flat["residential"]


def test_conditions_preserve_osm_geometry_and_provenance(osm_scenario):
    """The condition layer must not disturb the real map data it sits on."""
    conditioned = apply_conditions(
        osm_scenario, ConditionRequest(traffic_mode=MODE_SEVERE)
    )

    for before, after in zip(osm_scenario.edges, conditioned.edges):
        assert after.base_travel_time == before.base_travel_time
        assert after.geometry == before.geometry
        assert after.osm_way_id == before.osm_way_id
        assert after.speed_kph == before.speed_kph
        assert after.speed_source == before.speed_source


def test_conditions_change_routing_on_a_real_osm_network(osm_scenario):
    normal = compute_route_matrix(
        apply_conditions(osm_scenario, ConditionRequest(traffic_mode=MODE_NORMAL))
    )
    heavy = compute_route_matrix(
        apply_conditions(osm_scenario, ConditionRequest(traffic_mode=MODE_HEAVY))
    )

    changed = sum(1 for pair, path in normal.paths.items() if heavy.paths.get(pair) != path)
    assert changed > 0


# ========================================================= model transparency

def test_the_condition_model_endpoint_publishes_its_own_assumptions():
    body = client.get("/api/conditions/model").json()

    assert body["simulated"]["traffic_level_multipliers"]["heavy"] == 2.5
    assert body["simulated"]["weather_impact_multipliers"]["rain"] > 1.0
    assert "assumption" in body["simulated"]["disclaimer"].lower()
    assert "OpenStreetMap" in body["real"]["road_network"]
    assert "Open-Meteo" in body["real"]["weather_observations"]
