"""API-level tests for the Phase 6 surface.

Phase 6 is about the frontend and backend agreeing on what is real: the map
draws OpenStreetMap geometry for OSM scenarios and its own straight lines for
synthetic ones, traffic colours come from a backend-declared state rather than
thresholds re-invented in React, and a run's provenance can be read back from
the server instead of being taken on trust.

Everything remote is mocked. Overpass is served from the recorded extract and
Open-Meteo from a fake transport, so no test reaches the network.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import main as main_module
import realdata.osm_loader as osm_loader_module
from realdata.cache import DiskCache
from realdata.conditions import CONGESTION_BANDS, CONGESTION_LEVELS, classify_congestion
from realdata.weather import OpenMeteoProvider
from route_cache import ROUTE_MATRIX_CACHE

client = TestClient(main_module.app)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "overpass_real_extract.json"
REAL_PAYLOAD = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

SOLVER = {"algorithm": "qpso", "population_size": 12, "max_iterations": 12, "seed": 42}


@pytest.fixture(autouse=True)
def isolated_route_cache():
    ROUTE_MATRIX_CACHE.clear()
    ROUTE_MATRIX_CACHE.reset_stats()
    yield
    ROUTE_MATRIX_CACHE.clear()
    ROUTE_MATRIX_CACHE.reset_stats()


@pytest.fixture
def mock_overpass(monkeypatch):
    cache = DiskCache(root=Path(tempfile.mkdtemp(prefix="p6osm_")))
    original = osm_loader_module.load_osm_graph

    def patched(location, **kwargs):
        kwargs.setdefault("cache", cache)
        kwargs.setdefault("post_overpass", lambda url, query, timeout: REAL_PAYLOAD)
        return original(location, **kwargs)

    monkeypatch.setattr(main_module, "load_osm_graph", patched)


@pytest.fixture
def offline_weather(monkeypatch):
    """A deterministic Open-Meteo stand-in reporting heavy rain."""
    def transport(url, params, timeout):
        return {
            "current": {
                "time": "2026-09-19T10:00",
                "temperature_2m": 24.0,
                "precipitation": 3.0,
                "wind_speed_10m": 9.0,
                "weather_code": 65,
            }
        }

    provider = OpenMeteoProvider(
        cache=DiskCache(root=Path(tempfile.mkdtemp(prefix="p6wx_"))),
        fetch_json=transport,
    )
    monkeypatch.setattr(main_module, "DEFAULT_WEATHER_PROVIDER", provider)
    import realdata.conditions as conditions_module
    monkeypatch.setattr(conditions_module, "DEFAULT_WEATHER_PROVIDER", provider)
    return provider


@pytest.fixture
def broken_weather(monkeypatch):
    provider = OpenMeteoProvider(
        cache=DiskCache(root=Path(tempfile.mkdtemp(prefix="p6wxdead_"))),
        fetch_json=lambda url, params, timeout: (_ for _ in ()).throw(
            ConnectionError("open-meteo unreachable")
        ),
    )
    monkeypatch.setattr(main_module, "DEFAULT_WEATHER_PROVIDER", provider)
    import realdata.conditions as conditions_module
    monkeypatch.setattr(conditions_module, "DEFAULT_WEATHER_PROVIDER", provider)
    return provider


def _generate_synthetic(**overrides):
    body = {"num_nodes": 24, "num_jobs": 8, "num_vehicles": 3, "seed": 42}
    body.update(overrides)
    response = client.post("/api/problem/generate", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _generate_osm(**overrides):
    body = {
        "source": "osm",
        "latitude": 26.8381,
        "longitude": 80.9346,
        "radius_m": 600,
        "num_jobs": 8,
        "num_vehicles": 2,
        "seed": 42,
    }
    body.update(overrides)
    response = client.post("/api/problem/generate", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _optimize(scenario_id, **config_overrides):
    config = dict(SOLVER)
    config.update(config_overrides)
    response = client.post(
        "/api/optimize", json={"scenario_id": scenario_id, "config": config}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _geometry(scenario_id, result):
    response = client.post("/api/routes/geometry", json={
        "scenario_id": scenario_id,
        "routes": result["routes"],
    })
    assert response.status_code == 200, response.text
    return response.json()


def _conditions(scenario_id, **overrides):
    body = {"scenario_id": scenario_id}
    body.update(overrides)
    return client.post("/api/scenario/conditions", json=body)


def _manifest(scenario_id, **params):
    query = {
        "algorithm": SOLVER["algorithm"],
        "population_size": SOLVER["population_size"],
        "max_iterations": SOLVER["max_iterations"],
    }
    query.update(params)
    response = client.get(f"/api/scenario/{scenario_id}/manifest", params=query)
    assert response.status_code == 200, response.text
    return response.json()


# ================================================= 1. OSM geometry over the API

def test_generate_declares_its_geometry_source(mock_overpass):
    assert _generate_synthetic()["geometry_source"] == "straight-line"
    assert _generate_osm()["geometry_source"] == "openstreetmap"


def test_osm_scenario_edges_reach_the_client_with_geometry(mock_overpass):
    scenario = _generate_osm()["scenario"]
    edges = scenario["edges"]

    assert all(e["geometry"] and len(e["geometry"]) >= 2 for e in edges)
    # At least some roads have shape points beyond their two junctions -
    # otherwise the map would gain nothing from drawing geometry.
    assert any(len(e["geometry"]) > 2 for e in edges)
    assert all(e["osm_way_id"] is not None for e in edges)


def test_synthetic_scenario_edges_carry_no_geometry():
    """Synthetic edges must stay geometry-free so the client can tell the two
    network kinds apart without being told."""
    scenario = _generate_synthetic()["scenario"]
    assert all(e["geometry"] is None for e in scenario["edges"])
    assert all(e["osm_way_id"] is None for e in scenario["edges"])


# ================================================ 2. route geometry endpoint

def test_route_geometry_returns_osm_shapes_for_an_osm_scenario(mock_overpass):
    body = _generate_osm()
    result = _optimize(body["scenario_id"])
    geometry = _geometry(body["scenario_id"], result)

    assert geometry["data_source"] == "openstreetmap"
    assert geometry["geometry_source"] == "openstreetmap"
    assert len(geometry["routes"]) == len(result["routes"])

    for drawn, route in zip(geometry["routes"], result["routes"]):
        assert drawn["vehicle_id"] == route["vehicle_id"]
        assert drawn["node_count"] == len(route["node_path"])
        # Real road shapes contain at least as many points as junctions.
        assert drawn["point_count"] >= len(route["node_path"])


def test_route_geometry_is_more_detailed_than_the_node_path(mock_overpass):
    """The whole point: the drawn route follows the road, not the crow."""
    body = _generate_osm()
    result = _optimize(body["scenario_id"])
    geometry = _geometry(body["scenario_id"], result)

    working = [r for r in result["routes"] if len(r["node_path"]) > 3]
    assert working, "no vehicle was assigned a multi-stop route"

    by_vehicle = {r["vehicle_id"]: r for r in geometry["routes"]}
    assert any(
        by_vehicle[r["vehicle_id"]]["point_count"] > len(r["node_path"])
        for r in working
    )


def test_route_geometry_falls_back_to_straight_lines_for_synthetic():
    body = _generate_synthetic()
    result = _optimize(body["scenario_id"])
    geometry = _geometry(body["scenario_id"], result)

    assert geometry["data_source"] == "synthetic"
    assert geometry["geometry_source"] == "straight-line"
    for drawn, route in zip(geometry["routes"], result["routes"]):
        assert drawn["geometry_source"] in ("straight-line", "none")
        assert drawn["point_count"] == len(route["node_path"])


def test_route_geometry_segments_name_the_real_roads(mock_overpass):
    body = _generate_osm()
    result = _optimize(body["scenario_id"])
    geometry = _geometry(body["scenario_id"], result)

    segments = [s for r in geometry["routes"] for s in r["segments"]]
    assert segments
    assert all(s["osm_way_id"] is not None for s in segments)
    assert all(s["geometry_source"] == "openstreetmap" for s in segments)
    assert all(s["congestion_level"] in CONGESTION_LEVELS for s in segments)


def test_route_geometry_rejects_an_unknown_scenario():
    response = client.post("/api/routes/geometry", json={
        "scenario_id": "does-not-exist", "routes": [],
    })
    assert response.status_code == 404


# ============================================ 3. traffic visualization data

def test_a_fresh_scenario_reports_free_flow_on_every_edge():
    scenario = _generate_synthetic()["scenario"]
    assert all(e["congestion_level"] == "free_flow" for e in scenario["edges"])
    assert all(e["has_incident"] is False for e in scenario["edges"])


@pytest.mark.parametrize("mode,expected_levels", [
    ("normal", {"free_flow"}),
    ("moderate", {"moderate", "light"}),
    ("heavy", {"heavy", "moderate"}),
    ("severe", {"severe", "heavy"}),
])
def test_traffic_levels_reach_the_client_as_backend_declared_states(mode, expected_levels):
    """The map colours a road from `congestion_level`, so raising the traffic
    level has to move edges into the matching band - and must do so on the
    backend, not by the client re-deriving it from a multiplier."""
    body = _generate_synthetic()
    response = _conditions(body["scenario_id"], traffic_mode=mode)
    assert response.status_code == 200

    edges = response.json()["scenario"]["edges"]
    observed = {e["congestion_level"] for e in edges}
    assert observed <= set(CONGESTION_LEVELS)
    assert observed & expected_levels, f"{mode} produced {observed}"


def test_congestion_level_always_agrees_with_the_multiplier_it_describes():
    """The state and the cost are written by the same function, so they can
    never disagree. This is the check that keeps them honest."""
    body = _generate_synthetic()
    response = _conditions(body["scenario_id"], traffic_mode="heavy")
    assert response.status_code == 200

    for edge in response.json()["scenario"]["edges"]:
        assert edge["congestion_level"] == classify_congestion(edge["traffic_factor"])


def test_traffic_varies_across_roads_on_a_real_network(mock_overpass):
    """A single uniform multiplier would leave every shortest path exactly
    where it was. Road-class susceptibility is what makes congestion
    re-route - so more than one band must actually appear."""
    body = _generate_osm()
    response = _conditions(body["scenario_id"], traffic_mode="heavy")
    assert response.status_code == 200

    levels = {e["congestion_level"] for e in response.json()["scenario"]["edges"]}
    assert len(levels) > 1, f"congestion was uniform across the network: {levels}"


def test_an_incident_is_flagged_separately_from_the_traffic_level():
    """The map distinguishes 'this road is congested' from 'an operator
    disrupted this road'; the backend has to tell them apart."""
    body = _generate_synthetic()
    scenario_id = body["scenario_id"]
    assert _conditions(scenario_id, traffic_mode="moderate").status_code == 200

    edge = body["scenario"]["edges"][0]
    response = client.post("/api/traffic/update", json={
        "scenario_id": scenario_id,
        "updates": [{
            "source": edge["source"],
            "destination": edge["destination"],
            "traffic_factor": 4.0,
        }],
    })
    assert response.status_code == 200

    edges = response.json()["scenario"]["edges"]
    disrupted = [e for e in edges if e["has_incident"]]
    assert len(disrupted) == 2  # applied symmetrically, both directions
    assert all(e["congestion_level"] == "severe" for e in disrupted)
    # Roads that were merely congested are not mislabelled as incidents.
    assert any(e["congestion_level"] != "free_flow" and not e["has_incident"] for e in edges)


def test_the_congestion_bands_are_published_for_inspection():
    response = client.get("/api/conditions/model")
    assert response.status_code == 200
    simulated = response.json()["simulated"]

    assert simulated["congestion_levels"] == list(CONGESTION_LEVELS)
    published = [(b["level"], b["min_traffic_factor"]) for b in simulated["congestion_bands"]]
    assert published == [list(b) and (b[0], b[1]) for b in CONGESTION_BANDS]
    # Thresholds descend, so "first match wins" is well defined.
    thresholds = [b["min_traffic_factor"] for b in simulated["congestion_bands"]]
    assert thresholds == sorted(thresholds, reverse=True)


def test_nothing_in_the_visualization_payload_claims_live_traffic(mock_overpass):
    body = _generate_osm()
    result = _optimize(body["scenario_id"])
    blob = json.dumps(_geometry(body["scenario_id"], result)).lower()
    blob += json.dumps(body).lower()

    assert "live traffic" not in blob
    assert "real-time traffic" not in blob
    assert body["traffic_source"] == "simulated"


# ================================ 4. incident -> re-optimization, end to end

def test_incident_changes_edge_cost_state_and_the_route(mock_overpass):
    """The full chain Phase 6 step 8 asks to verify:
    incident -> condition update -> current edge cost -> cache key ->
    route matrix -> optimizer -> changed route."""
    body = _generate_osm()
    scenario_id = body["scenario_id"]

    before = _optimize(scenario_id)
    before_paths = {r["vehicle_id"]: list(r["node_path"]) for r in before["routes"]}

    # Disrupt a road the fleet is actually using, severely enough that routing
    # around it is worthwhile.
    busy = next(r for r in before["routes"] if len(r["node_path"]) > 4)
    source, destination = busy["node_path"][1], busy["node_path"][2]

    disrupted = client.post("/api/traffic/update", json={
        "scenario_id": scenario_id,
        "updates": [{"source": source, "destination": destination, "traffic_factor": 25.0}],
    })
    assert disrupted.status_code == 200
    disrupted_body = disrupted.json()
    assert disrupted_body["updated_edges"] >= 1

    # --- condition update reached the edge cost ---
    hit = [
        e for e in disrupted_body["scenario"]["edges"]
        if (e["source"], e["destination"]) == (source, destination)
    ]
    assert hit
    for edge in hit:
        assert edge["incident_multiplier"] == 25.0
        assert edge["has_incident"] is True
        assert edge["congestion_level"] == "severe"
        assert edge["current_travel_time"] > edge["base_travel_time"]

    # --- the optimizer re-plans against the new costs ---
    builds_before = client.get("/api/health").json()["route_matrix_cache"]["builds"]
    after = _optimize(scenario_id)
    builds_after = client.get("/api/health").json()["route_matrix_cache"]["builds"]

    # A changed edge cost changes the content-addressed key, so the matrix is
    # rebuilt rather than served stale.
    assert builds_after > builds_before

    after_paths = {r["vehicle_id"]: list(r["node_path"]) for r in after["routes"]}
    assert after_paths != before_paths, "the disruption did not change any route"

    # --- and the drawn route follows the new path, still over real roads ---
    geometry = _geometry(scenario_id, after)
    assert geometry["geometry_source"] == "openstreetmap"
    for drawn, route in zip(geometry["routes"], after["routes"]):
        assert drawn["node_count"] == len(route["node_path"])


def test_the_disrupted_road_is_avoided_by_the_new_routes(mock_overpass):
    """A road made 25x slower should not survive in the fleet's paths when an
    alternative exists."""
    body = _generate_osm()
    scenario_id = body["scenario_id"]
    before = _optimize(scenario_id)

    busy = next(r for r in before["routes"] if len(r["node_path"]) > 4)
    source, destination = busy["node_path"][1], busy["node_path"][2]

    client.post("/api/traffic/update", json={
        "scenario_id": scenario_id,
        "updates": [{"source": source, "destination": destination, "traffic_factor": 50.0}],
    })
    after = _optimize(scenario_id)

    def uses(routes):
        for route in routes:
            path = route["node_path"]
            for u, v in zip(path[:-1], path[1:]):
                if {u, v} == {source, destination}:
                    return True
        return False

    assert uses(before["routes"])
    assert not uses(after["routes"])


# ======================================================= 5. weather metadata

def test_manifest_reports_a_real_weather_observation(offline_weather):
    body = _generate_synthetic()
    scenario_id = body["scenario_id"]
    assert _conditions(scenario_id, weather_enabled=True).status_code == 200

    conditions = _manifest(scenario_id)["conditions"]
    assert conditions["weather_enabled"] is True
    assert conditions["weather_source"] in ("network", "cache", "cache-stale")
    assert conditions["weather_condition"] == "heavy_rain"
    assert conditions["weather_multiplier"] > 1.0
    assert conditions["weather_observed_at"]
    assert conditions["fallback_used"] is False


def test_the_weather_payload_carries_every_field_the_ui_shows(offline_weather):
    """The UI shows condition, temperature, source, provider and timing. Each
    has to actually be present, or the panel silently degrades."""
    body = _generate_synthetic()
    response = _conditions(body["scenario_id"], weather_enabled=True)
    assert response.status_code == 200

    weather = response.json()["conditions"]["weather"]
    assert weather["condition"] == "heavy_rain"
    assert weather["description"]
    assert weather["provider"] == "open-meteo"
    assert weather["temperature_c"] == 24.0
    assert weather["precipitation_mm"] == 3.0
    assert weather["wind_speed_kph"] == 9.0
    assert weather["observed_at"]
    assert weather["retrieved_at"]
    assert weather["is_real_observation"] is True
    assert weather["multiplier"] > 1.0


def test_a_weather_outage_is_shown_as_a_fallback_with_no_invented_values(broken_weather):
    body = _generate_synthetic()
    scenario_id = body["scenario_id"]
    response = _conditions(scenario_id, weather_enabled=True)
    assert response.status_code == 200

    weather = response.json()["conditions"]["weather"]
    assert weather["fallback_used"] is True
    assert weather["source"] == "fallback"
    assert weather["temperature_c"] is None
    assert weather["multiplier"] == 1.0

    manifest = _manifest(scenario_id)
    assert manifest["conditions"]["fallback_used"] is True
    assert manifest["conditions"]["weather_multiplier"] == 1.0


# ==================================================== 6. reproducibility

def test_manifest_reports_the_run_configuration_it_was_given():
    body = _generate_synthetic()
    scenario_id = body["scenario_id"]
    _optimize(scenario_id)

    manifest = _manifest(scenario_id)
    assert manifest["scenario_id"] == scenario_id
    assert manifest["scenario_hash"] == body["scenario_hash"]
    assert manifest["seed"] == 42
    assert manifest["data_source"] == "synthetic"
    assert manifest["geometry_source"] == "straight-line"
    assert manifest["solver"] == {
        "algorithm": "qpso", "population_size": 12, "max_iterations": 12,
    }
    assert manifest["network"]["job_count"] == 8
    assert manifest["network"]["vehicle_count"] == 3


def test_manifest_reports_no_location_for_a_synthetic_network():
    """A generated network has no real place. Reporting one would misstate the
    run, so the field is null rather than filled in."""
    manifest = _manifest(_generate_synthetic()["scenario_id"])
    assert manifest["location"] is None


def test_manifest_reports_the_real_location_for_an_osm_network(mock_overpass):
    body = _generate_osm()
    manifest = _manifest(body["scenario_id"])

    assert manifest["data_source"] == "openstreetmap"
    assert manifest["geometry_source"] == "openstreetmap"
    assert manifest["location"]["location"]["latitude"] == pytest.approx(26.8381)
    assert manifest["location"]["location"]["resolver"] == "coordinates"
    assert manifest["location"]["bbox"]
    assert manifest["location"]["radius_m"] == 600.0


def test_manifest_reports_unset_solver_settings_as_null_rather_than_defaults():
    scenario_id = _generate_synthetic()["scenario_id"]
    response = client.get(f"/api/scenario/{scenario_id}/manifest")
    assert response.status_code == 200
    assert response.json()["solver"] == {
        "algorithm": None, "population_size": None, "max_iterations": None,
    }


def test_manifest_tracks_the_condition_configuration(offline_weather):
    scenario_id = _generate_synthetic()["scenario_id"]

    fresh = _manifest(scenario_id)
    assert fresh["conditions"]["applied"] is False
    assert fresh["conditions"]["signature"] is None

    assert _conditions(
        scenario_id, traffic_mode="heavy", weather_enabled=True, use_bpr=True
    ).status_code == 200

    applied = _manifest(scenario_id)["conditions"]
    assert applied["applied"] is True
    assert applied["traffic_mode"] == "heavy"
    assert applied["traffic_source"] == "simulated"
    assert applied["traffic_is_simulated"] is True
    assert applied["traffic_formulation"] == "bpr"
    assert applied["weather_enabled"] is True
    assert applied["signature"]


def test_the_same_manifest_signature_means_the_same_conditions():
    """Reproducibility claim under test: re-applying identical conditions has
    to produce an identical fingerprint, and a different level must not."""
    first = _generate_synthetic()["scenario_id"]
    second = _generate_synthetic()["scenario_id"]

    _conditions(first, traffic_mode="heavy")
    _conditions(second, traffic_mode="heavy")
    assert _manifest(first)["conditions"]["signature"] == \
        _manifest(second)["conditions"]["signature"]

    _conditions(second, traffic_mode="moderate")
    assert _manifest(first)["conditions"]["signature"] != \
        _manifest(second)["conditions"]["signature"]


def test_the_signature_distinguishes_a_fetched_reading_from_a_cached_one(offline_weather):
    """The signature fingerprints provenance, not just values: the same weather
    served from cache is a different condition state from one just fetched, and
    the manifest reports that rather than presenting them as interchangeable."""
    scenario_id = _generate_synthetic()["scenario_id"]

    _conditions(scenario_id, traffic_mode="heavy", weather_enabled=True)
    fetched = _manifest(scenario_id)["conditions"]

    _conditions(scenario_id, traffic_mode="heavy", weather_enabled=True)
    cached = _manifest(scenario_id)["conditions"]

    assert fetched["weather_source"] == "network"
    assert cached["weather_source"] == "cache"
    assert fetched["weather_condition"] == cached["weather_condition"]
    assert fetched["weather_multiplier"] == cached["weather_multiplier"]
    assert fetched["signature"] != cached["signature"]


def test_manifest_rejects_an_unknown_scenario():
    assert client.get("/api/scenario/nope/manifest").status_code == 404
