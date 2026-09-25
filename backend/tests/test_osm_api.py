"""API-level tests for source=osm on /api/problem/generate.

Overpass is mocked at the HTTP boundary, so pytest never calls the public
service. The geocoder is bypassed by using coordinate/bbox input, which
exercises the same endpoint without a network round-trip.
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

client = TestClient(main_module.app)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "overpass_real_extract.json"
REAL_PAYLOAD = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def mock_overpass(monkeypatch):
    """Routes the loader through a private cache and a fake transport."""
    calls = []
    cache = DiskCache(root=Path(tempfile.mkdtemp(prefix="osmapi_")))

    original = osm_loader_module.load_osm_graph

    def patched(location, **kwargs):
        calls.append(location)
        kwargs.setdefault("cache", cache)
        kwargs.setdefault("post_overpass", lambda url, query, timeout: REAL_PAYLOAD)
        return original(location, **kwargs)

    monkeypatch.setattr(main_module, "load_osm_graph", patched)
    return calls


def _generate_osm(**overrides):
    body = {
        "source": "osm",
        "latitude": 26.8381,
        "longitude": 80.9346,
        "radius_m": 600,
        "num_jobs": 10,
        "num_vehicles": 3,
        "seed": 42,
    }
    body.update(overrides)
    return client.post("/api/problem/generate", json=body)


# ======================================================== response shape

def test_osm_generate_returns_full_provenance(mock_overpass):
    response = _generate_osm()
    assert response.status_code == 200
    body = response.json()

    assert body["data_source"] == "openstreetmap"
    assert body["provenance"] in ("network", "cache", "cache-stale")
    assert body["retrieved_at"]

    assert body["location"]["latitude"] == pytest.approx(26.8381)
    assert body["location"]["longitude"] == pytest.approx(80.9346)
    assert body["location"]["resolver"] == "coordinates"
    assert set(body["bbox"]) == {"min_lat", "min_lon", "max_lat", "max_lon"}
    assert body["radius_m"] == 600.0

    assert body["node_count"] > 100
    assert body["edge_count"] > 200
    assert body["job_count"] == 10
    assert body["vehicle_count"] == 3
    assert body["scenario_id"] and body["scenario_hash"]


def test_osm_response_does_not_claim_live_traffic(mock_overpass):
    """OSM gives roads, not traffic. The response must say so."""
    body = _generate_osm().json()

    assert body["traffic_source"] == "simulated"
    assert body["weather_source"] is None
    assert all(e["traffic_factor"] == 1.0 for e in body["scenario"]["edges"])

    serialised = json.dumps(body).lower()
    assert "live traffic" not in serialised
    assert "real-time" not in serialised


def test_osm_scenario_carries_geometry_and_osm_ids(mock_overpass):
    body = _generate_osm().json()
    scenario = body["scenario"]

    assert all(n["osm_id"] is not None for n in scenario["nodes"])
    assert scenario["data_source"] == "openstreetmap"

    with_geometry = [e for e in scenario["edges"] if e.get("geometry")]
    assert len(with_geometry) == len(scenario["edges"])
    curved = [e for e in with_geometry if len(e["geometry"]) > 2]
    assert len(curved) > 50

    sample = scenario["edges"][0]
    assert sample["osm_way_id"] is not None
    assert sample["highway"]
    assert sample["speed_source"]


def test_osm_stats_are_reported(mock_overpass):
    body = _generate_osm().json()
    stats = body["osm"]

    assert stats["ways_considered"] == 133
    assert stats["kept_nodes"] == body["node_count"]
    assert stats["kept_edges"] == body["edge_count"]
    assert stats["total_length_km"] > 0
    # Honest reporting of how many speeds were actually tagged.
    assert stats["ways_with_osm_maxspeed"] + stats["ways_using_speed_fallback"] == 133


# ========================================================= location modes

def test_bbox_input_mode_works(mock_overpass):
    response = _generate_osm(
        latitude=None, longitude=None,
        bbox=[26.8327, 80.9285, 26.8434, 80.9406],
    )
    assert response.status_code == 200
    assert response.json()["location"]["resolver"] == "bbox"


def test_missing_location_is_a_client_error(mock_overpass):
    response = client.post("/api/problem/generate", json={"source": "osm"})
    assert response.status_code == 400
    assert "place name" in response.json()["detail"].lower()


def test_area_above_the_limit_is_rejected(mock_overpass):
    response = _generate_osm(latitude=None, longitude=None,
                             bbox=[0.0, 0.0, 20.0, 20.0])
    assert response.status_code == 502
    assert "km2" in response.json()["detail"]


# ============================================== upstream failure handling

def test_overpass_failure_without_cache_returns_an_error_not_synthetic_data(monkeypatch):
    """The endpoint must never silently hand back a generated network and
    label it OpenStreetMap."""
    cache = DiskCache(root=Path(tempfile.mkdtemp(prefix="osmfail_")))
    original = osm_loader_module.load_osm_graph

    def dead(location, **kwargs):
        kwargs.setdefault("cache", cache)
        def boom(url, query, timeout):
            raise ConnectionError("overpass unavailable")
        kwargs.setdefault("post_overpass", boom)
        return original(location, **kwargs)

    monkeypatch.setattr(main_module, "load_osm_graph", dead)

    response = _generate_osm()
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "no cached extract" in detail

    body = response.json()
    assert "scenario" not in body


def test_cached_extract_is_served_and_labelled_when_overpass_dies(monkeypatch):
    cache = DiskCache(root=Path(tempfile.mkdtemp(prefix="osmcache_")))
    original = osm_loader_module.load_osm_graph
    state = {"alive": True}

    def toggling(location, **kwargs):
        kwargs.setdefault("cache", cache)

        def transport(url, query, timeout):
            if not state["alive"]:
                raise ConnectionError("overpass unavailable")
            return REAL_PAYLOAD

        kwargs.setdefault("post_overpass", transport)
        return original(location, **kwargs)

    monkeypatch.setattr(main_module, "load_osm_graph", toggling)

    first = _generate_osm()
    assert first.status_code == 200
    assert first.json()["provenance"] == "network"

    state["alive"] = False
    second = _generate_osm()
    assert second.status_code == 200
    assert second.json()["provenance"] == "cache"
    assert second.json()["node_count"] == first.json()["node_count"]


# =========================================== full pipeline through the API

def test_osm_scenario_optimizes_and_benchmarks_by_scenario_id(mock_overpass):
    body = _generate_osm().json()
    scenario_id = body["scenario_id"]
    config = {"algorithm": "qpso", "population_size": 8, "max_iterations": 5, "seed": 42}

    optimized = client.post("/api/optimize",
                            json={"scenario_id": scenario_id, "config": config})
    assert optimized.status_code == 200
    before = optimized.json()
    assert before["total_cost"] > 0
    assert before["total_distance"] > 0

    bench = client.post("/api/benchmark",
                        json={"scenario_id": scenario_id, "config": config})
    assert bench.status_code == 200
    assert set(bench.json()["results"].keys()) == {"greedy", "pso", "ga", "qpso", "qpso_memetic"}


def test_incident_and_reoptimize_work_on_an_osm_scenario(mock_overpass):
    body = _generate_osm().json()
    scenario_id = body["scenario_id"]
    config = {"algorithm": "greedy"}

    before = client.post("/api/optimize",
                         json={"scenario_id": scenario_id, "config": config}).json()

    path = before["routes"][0]["node_path"]
    updates = [{"source": u, "destination": v, "traffic_factor": 25.0}
               for u, v in zip(path[:-1], path[1:])]
    assert updates

    traffic = client.post("/api/traffic/update",
                          json={"scenario_id": scenario_id, "updates": updates})
    assert traffic.status_code == 200
    assert traffic.json()["updated_edges"] > 0

    after = client.post("/api/optimize",
                        json={"scenario_id": scenario_id, "config": config}).json()
    assert after["total_travel_time"] != before["total_travel_time"]


# ================================================== synthetic regression

def test_synthetic_source_is_unchanged():
    response = client.post("/api/problem/generate", json={
        "source": "synthetic", "num_nodes": 20, "num_jobs": 8,
        "num_vehicles": 2, "seed": 42,
    })
    assert response.status_code == 200
    body = response.json()

    assert body["data_source"] == "synthetic"
    assert body["node_count"] == 20
    assert body["scenario"]["data_source"] == "synthetic"
    assert all(n["osm_id"] is None for n in body["scenario"]["nodes"])
    assert "location" not in body


def test_source_defaults_to_synthetic():
    response = client.post("/api/problem/generate", json={
        "num_nodes": 15, "num_jobs": 5, "num_vehicles": 2, "seed": 1,
    })
    assert response.status_code == 200
    assert response.json()["data_source"] == "synthetic"


def test_synthetic_scenario_hash_is_unchanged_by_the_extra_field():
    """compute_scenario_hash gained an `extra` argument for the OSM path; the
    synthetic hashes must be byte-identical to what they always were."""
    from problem_generator import compute_scenario_hash

    assert compute_scenario_hash(30, 15, 3, 42) == compute_scenario_hash(30, 15, 3, 42, extra="")
    assert compute_scenario_hash(30, 15, 3, 42) != compute_scenario_hash(30, 15, 3, 42, extra="osm:1,2,3,4")
