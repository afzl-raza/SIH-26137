"""Tests for OpenStreetMap ingestion and the OSM -> ProblemScenario adapter.

No test touches the network. Two kinds of fixture are used:

  * hand-built Overpass payloads for each specific rule (one-way, speed
    parsing, geometry, connectivity), so failures point at one behaviour;
  * one real recorded Overpass extract (tests/fixtures/), so the parser is
    exercised against actual OSM data with all its messiness - in that
    extract 132 of 133 ways carry no maxspeed at all.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import OptimizationConfig
from optimizers.benchmark import run_benchmark
from problem_generator import compute_route_matrix, terminal_nodes
import realdata.osm_loader as osm_loader_module
from realdata.cache import DiskCache, SOURCE_CACHE, SOURCE_CACHE_STALE, SOURCE_NETWORK
from realdata.geocoding import BoundingBox, ResolvedLocation, resolve_location
from realdata.osm_loader import (
    DEFAULT_HIGHWAY_CLASSES,
    MAX_BBOX_AREA_KM2,
    OsmLoaderError,
    bbox_area_km2,
    build_overpass_query,
    haversine_m,
    largest_routable_component,
    load_osm_graph,
    overpass_endpoints,
    parse_lanes,
    parse_maxspeed,
    parse_overpass_response,
    polyline_length_m,
    resolve_directions,
)
from realdata.osm_scenario import osm_graph_to_scenario, select_terminals

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "overpass_real_extract.json"


# ------------------------------------------------------------- helpers

def way(way_id, node_ids, coords, **tags):
    """Builds an Overpass way element in the shape the real API returns:
    parallel `nodes` and `geometry` lists."""
    tags.setdefault("highway", "residential")
    return {
        "type": "way",
        "id": way_id,
        "nodes": list(node_ids),
        "geometry": [{"lat": lat, "lon": lon} for lat, lon in coords],
        "tags": tags,
    }


def payload(*ways):
    return {"version": 0.6, "generator": "test", "elements": list(ways)}


def a_location(lat=26.84, lon=80.93, radius_m=1000.0):
    return resolve_location(latitude=lat, longitude=lon, radius_m=radius_m)


def tmp_cache():
    return DiskCache(root=Path(tempfile.mkdtemp(prefix="osmtest_")))


STRAIGHT = [(26.8400, 80.9300), (26.8410, 80.9300)]
# A pronounced U-bend: its endpoints are close together but the road between
# them is far longer, so any code that measured endpoint-to-endpoint instead
# of following the geometry would be caught immediately.
CURVED = [(26.8410, 80.9300), (26.8410, 80.9330), (26.8440, 80.9330), (26.8440, 80.9300)]


# =============================================================== one-way

def test_untagged_road_is_bidirectional():
    assert resolve_directions({}, "residential") == (True, True)


def test_oneway_yes_variants_are_forward_only():
    for value in ("yes", "1", "true", "YES", " Yes "):
        assert resolve_directions({"oneway": value}, "residential") == (True, False), value


def test_oneway_reverse_variants_are_backward_only():
    for value in ("-1", "reverse", "REVERSE"):
        assert resolve_directions({"oneway": value}, "residential") == (False, True), value


def test_oneway_no_is_explicitly_bidirectional():
    for value in ("no", "0", "false"):
        assert resolve_directions({"oneway": value}, "residential") == (True, True), value


def test_motorway_is_oneway_by_convention():
    """Treating an untagged motorway as bidirectional would let a vehicle
    drive the wrong way down it."""
    assert resolve_directions({}, "motorway") == (True, False)
    assert resolve_directions({}, "motorway_link") == (True, False)
    # An explicit tag still wins over the convention.
    assert resolve_directions({"oneway": "no"}, "motorway") == (True, True)


def test_roundabout_is_oneway_by_convention():
    assert resolve_directions({"junction": "roundabout"}, "residential") == (True, False)


def test_bidirectional_way_produces_both_directions():
    nodes, edges, _ = parse_overpass_response(payload(way(1, [10, 11], STRAIGHT)))

    assert len(edges) == 2
    assert {(e.source, e.target) for e in edges} == {(10, 11), (11, 10)}
    assert nodes.keys() == {10, 11}


def test_oneway_way_produces_one_direction():
    _, edges, _ = parse_overpass_response(
        payload(way(1, [10, 11], STRAIGHT, oneway="yes")))

    assert len(edges) == 1
    assert (edges[0].source, edges[0].target) == (10, 11)


def test_reverse_oneway_produces_the_reversed_direction_and_geometry():
    _, edges, _ = parse_overpass_response(
        payload(way(1, [10, 11, 12], CURVED[:3], oneway="-1")))

    assert len(edges) == 1
    edge = edges[0]
    assert (edge.source, edge.target) == (12, 10), "travel runs against the way"
    # Geometry must run in the direction of travel.
    assert edge.geometry[0] == [CURVED[2][0], CURVED[2][1]]
    assert edge.geometry[-1] == [CURVED[0][0], CURVED[0][1]]


def test_not_every_road_becomes_bidirectional():
    data = payload(
        way(1, [10, 11], STRAIGHT),
        way(2, [12, 13], STRAIGHT, oneway="yes"),
        way(3, [14, 15], STRAIGHT, oneway="-1"),
    )
    _, edges, stats = parse_overpass_response(data)

    assert stats["bidirectional"] == 1
    assert stats["oneway_forward"] == 1
    assert stats["oneway_reverse"] == 1
    assert len(edges) == 2 + 1 + 1


# ================================================================= speed

@pytest.mark.parametrize("raw,expected", [
    ("50", 50.0),
    ("50 km/h", 50.0),
    ("50km/h", 50.0),
    ("60 kph", 60.0),
    ("30 mph", 30.0 * 1.609344),
    ("30mph", 30.0 * 1.609344),
    ("walk", 5.0),
    ("30;50", 30.0),
])
def test_maxspeed_parsing(raw, expected):
    assert parse_maxspeed(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", [None, "", "none", "signals", "IN:urban", "DE:rural", "abc"])
def test_unusable_maxspeed_falls_back(raw):
    assert parse_maxspeed(raw) is None


def test_speed_provenance_is_recorded():
    data = payload(
        way(1, [10, 11], STRAIGHT, highway="residential", maxspeed="40"),
        way(2, [12, 13], STRAIGHT, highway="residential"),
    )
    _, edges, stats = parse_overpass_response(data)

    tagged = [e for e in edges if e.way_id == 1]
    untagged = [e for e in edges if e.way_id == 2]

    assert all(e.speed_kph == 40.0 and e.speed_source == "osm_maxspeed" for e in tagged)
    assert all(e.speed_source == "fallback:residential" for e in untagged)
    assert all(e.speed_kph == 30.0 for e in untagged)  # documented residential default
    assert stats["ways_with_osm_maxspeed"] == 1
    assert stats["ways_using_speed_fallback"] == 1


def test_speed_fallback_is_deterministic_not_random():
    """Same input twice must give the exact same speed - the synthetic
    generator randomises speeds, the OSM path must never do that."""
    data = payload(way(1, [10, 11], STRAIGHT, highway="tertiary"))
    first = parse_overpass_response(data)[1]
    second = parse_overpass_response(data)[1]
    assert [e.speed_kph for e in first] == [e.speed_kph for e in second]
    assert first[0].speed_kph == 40.0


def test_mph_is_converted_to_kmh():
    _, edges, _ = parse_overpass_response(
        payload(way(1, [10, 11], STRAIGHT, maxspeed="30 mph")))
    assert edges[0].speed_kph == pytest.approx(48.28, abs=0.01)


@pytest.mark.parametrize("raw,expected", [("2", 2), ("3", 3), ("2;3", 2), (None, None), ("x", None)])
def test_lanes_parsing(raw, expected):
    assert parse_lanes(raw) == expected


def test_lanes_fallback_and_capacity():
    _, edges, _ = parse_overpass_response(
        payload(way(1, [10, 11], STRAIGHT, highway="residential")))
    edge = edges[0]
    assert edge.lanes == 1
    assert edge.lanes_source == "fallback:residential"
    assert edge.capacity_vph == 600.0  # 1 lane x documented residential rate


# ============================================================== geometry

def test_intermediate_geometry_is_preserved():
    _, edges, _ = parse_overpass_response(payload(way(1, [10, 11, 12, 13], CURVED)))
    forward = [e for e in edges if (e.source, e.target) == (10, 13)][0]

    assert len(forward.geometry) == 4, "all shape points retained"
    assert forward.geometry[0] == [CURVED[0][0], CURVED[0][1]]
    assert forward.geometry[-1] == [CURVED[-1][0], CURVED[-1][1]]


def test_distance_follows_the_road_not_the_straight_line():
    """A curving road must be longer than the crow-flies distance between its
    endpoints, otherwise geometry is being thrown away."""
    _, edges, _ = parse_overpass_response(payload(way(1, [10, 11, 12, 13], CURVED)))
    edge = [e for e in edges if (e.source, e.target) == (10, 13)][0]

    straight = haversine_m(CURVED[0][0], CURVED[0][1], CURVED[-1][0], CURVED[-1][1])
    assert edge.length_m > straight * 1.2
    assert edge.length_m == pytest.approx(polyline_length_m(CURVED))


def test_distances_are_geographic_and_deterministic():
    data = payload(way(1, [10, 11], STRAIGHT))
    first = parse_overpass_response(data)[1][0].length_m
    second = parse_overpass_response(data)[1][0].length_m

    assert first == second, "no randomness in distance"
    expected = haversine_m(*STRAIGHT[0], *STRAIGHT[1])
    assert first == pytest.approx(expected)
    assert first == pytest.approx(111.2, abs=1.0)  # 0.001 deg latitude ~ 111 m


def test_travel_time_is_distance_over_speed():
    _, edges, _ = parse_overpass_response(
        payload(way(1, [10, 11], STRAIGHT, maxspeed="60")))
    edge = edges[0]
    expected_minutes = (edge.length_m / 1000.0) / 60.0 * 60.0
    assert edge.travel_time_minutes == pytest.approx(expected_minutes)


# =========================================================== way splitting

def test_ways_are_split_at_shared_nodes():
    """Node 11 is shared, so the first way must break into two segments."""
    data = payload(
        way(1, [10, 11, 12], [(26.840, 80.930), (26.841, 80.930), (26.842, 80.930)],
            oneway="yes"),
        way(2, [11, 20], [(26.841, 80.930), (26.841, 80.931)], oneway="yes"),
    )
    nodes, edges, _ = parse_overpass_response(data)

    pairs = {(e.source, e.target) for e in edges}
    assert (10, 11) in pairs and (11, 12) in pairs
    assert (10, 12) not in pairs, "must not skip the shared junction"
    assert set(nodes) == {10, 11, 12, 20}


def test_unshared_intermediate_nodes_do_not_become_graph_nodes():
    nodes, _, _ = parse_overpass_response(payload(way(1, [10, 11, 12, 13], CURVED)))
    assert set(nodes) == {10, 13}, "shape points stay in geometry, not the graph"


def test_non_drivable_ways_are_excluded():
    data = payload(
        way(1, [10, 11], STRAIGHT, highway="footway"),
        way(2, [12, 13], STRAIGHT, highway="cycleway"),
        way(3, [14, 15], STRAIGHT, highway="steps"),
        way(4, [16, 17], STRAIGHT, highway="residential"),
    )
    _, edges, stats = parse_overpass_response(data)

    assert stats["ways_considered"] == 1
    assert {e.highway for e in edges} == {"residential"}


def test_mismatched_node_and_geometry_lists_are_skipped():
    bad = way(1, [10, 11, 12], STRAIGHT)  # 3 node ids, 2 coordinates
    _, edges, stats = parse_overpass_response(payload(bad))
    assert edges == []
    assert stats["ways_skipped"] == 1


# =========================================================== connectivity

def test_disconnected_component_is_dropped_deterministically():
    """Two islands of road; only the larger routable one survives, and no
    invented link is added between them."""
    big = [
        way(1, [1, 2], [(26.840, 80.930), (26.841, 80.930)]),
        way(2, [2, 3], [(26.841, 80.930), (26.842, 80.930)]),
        way(3, [3, 1], [(26.842, 80.930), (26.840, 80.930)]),
    ]
    small = [way(9, [90, 91], [(26.900, 80.990), (26.901, 80.990)])]

    nodes, edges, _ = parse_overpass_response(payload(*big, *small))
    kept_nodes, kept_edges, stats = largest_routable_component(nodes, edges)

    assert set(kept_nodes) == {1, 2, 3}
    assert 90 not in kept_nodes and 91 not in kept_nodes
    assert stats["dropped_nodes"] == 2
    assert all((e.source in kept_nodes and e.target in kept_nodes) for e in kept_edges)
    # Deterministic across repeats.
    again = largest_routable_component(*parse_overpass_response(payload(*big, *small))[:2])
    assert set(again[0]) == set(kept_nodes)


def test_strong_connectivity_excludes_one_way_dead_ends():
    """A node reachable but never escapable must not survive, or a vehicle
    could be routed somewhere it cannot return from."""
    data = payload(
        way(1, [1, 2], [(26.840, 80.930), (26.841, 80.930)]),
        way(2, [2, 1], [(26.841, 80.930), (26.840, 80.930)]),
        way(3, [2, 3], [(26.841, 80.930), (26.842, 80.930)], oneway="yes"),
    )
    nodes, edges, _ = parse_overpass_response(data)
    kept_nodes, _, _ = largest_routable_component(nodes, edges)

    assert 3 not in kept_nodes
    assert {1, 2} <= set(kept_nodes)


# ================================================================== query

def test_query_is_bounded_and_filters_highways():
    box = BoundingBox(26.83, 80.92, 26.84, 80.94)
    query = build_overpass_query(box)

    assert "26.83,80.92,26.84,80.94" in query
    assert "residential" in query and "motorway" in query
    assert "footway" not in query and "cycleway" not in query
    assert "out body geom" in query


def test_endpoint_is_configurable(monkeypatch):
    monkeypatch.setenv("QDFRO_OVERPASS_URL", "https://example.test/api,https://b.test/api")
    assert overpass_endpoints() == ["https://example.test/api", "https://b.test/api"]

    monkeypatch.delenv("QDFRO_OVERPASS_URL")
    assert overpass_endpoints()[0].startswith("https://")


def test_unbounded_area_is_rejected():
    huge = resolve_location(bbox=(0.0, 0.0, 20.0, 20.0))
    assert bbox_area_km2(huge.bbox) > MAX_BBOX_AREA_KM2

    with pytest.raises(OsmLoaderError, match="above the"):
        load_osm_graph(huge, cache=tmp_cache(), post_overpass=lambda u, q, t: payload())


# ================================================================ caching

def _connected_payload():
    return payload(
        way(1, [1, 2], [(26.8400, 80.9300), (26.8410, 80.9300)]),
        way(2, [2, 3], [(26.8410, 80.9300), (26.8420, 80.9310)]),
        way(3, [3, 1], [(26.8420, 80.9310), (26.8400, 80.9300)]),
    )


def test_second_load_comes_from_cache():
    cache = tmp_cache()
    loc = a_location()
    calls = []

    def post(url, query, timeout):
        calls.append(url)
        return _connected_payload()

    first = load_osm_graph(loc, cache=cache, post_overpass=post)
    second = load_osm_graph(loc, cache=cache, post_overpass=post)

    assert len(calls) == 1
    assert first.provenance == SOURCE_NETWORK
    assert second.provenance == SOURCE_CACHE
    assert len(second.edges) == len(first.edges)


def test_network_failure_serves_cached_network_marked_stale():
    cache = tmp_cache()
    loc = a_location()
    load_osm_graph(loc, cache=cache, post_overpass=lambda u, q, t: _connected_payload())

    # Age the entry past its TTL, then take the network away.
    from realdata.osm_loader import _cache_key
    from realdata.osm_loader import DEFAULT_HIGHWAY_CLASSES as HW
    path = cache.path_for("osm", _cache_key(loc.bbox, HW))
    raw = json.loads(path.read_text())
    raw["cached_at"] = 0.0
    path.write_text(json.dumps(raw))

    def dead(url, query, timeout):
        raise ConnectionError("overpass down")

    graph = load_osm_graph(loc, cache=cache, post_overpass=dead)
    assert graph.provenance == SOURCE_CACHE_STALE
    assert graph.provenance != SOURCE_NETWORK
    assert len(graph.edges) > 0


def test_network_failure_without_cache_is_an_explicit_error():
    """It must fail loudly rather than quietly substituting synthetic roads."""
    def dead(url, query, timeout):
        raise ConnectionError("overpass down")

    with pytest.raises(OsmLoaderError, match="no cached extract"):
        load_osm_graph(a_location(), cache=tmp_cache(), post_overpass=dead)


def test_transient_failure_is_retried_on_the_same_endpoint(monkeypatch):
    """Public Overpass instances 504 under load; one retry per endpoint is
    what makes the difference between a working demo and a 502."""
    monkeypatch.setattr(osm_loader_module, "RETRY_BACKOFF_S", 0.0)
    attempted = []

    def flaky(url, query, timeout):
        attempted.append(url)
        if len(attempted) == 1:
            raise ConnectionError("504")
        return _connected_payload()

    graph = load_osm_graph(
        a_location(), cache=tmp_cache(), post_overpass=flaky,
        endpoints=["https://first.test", "https://second.test"])

    assert attempted == ["https://first.test", "https://first.test"]
    assert graph.provenance == SOURCE_NETWORK


def test_persistently_failing_endpoint_falls_through_to_the_next(monkeypatch):
    monkeypatch.setattr(osm_loader_module, "RETRY_BACKOFF_S", 0.0)
    attempted = []

    def flaky(url, query, timeout):
        attempted.append(url)
        if url == "https://first.test":
            raise ConnectionError("504")
        return _connected_payload()

    graph = load_osm_graph(
        a_location(), cache=tmp_cache(), post_overpass=flaky,
        endpoints=["https://first.test", "https://second.test"])

    assert attempted[:2] == ["https://first.test", "https://first.test"]
    assert "https://second.test" in attempted
    assert graph.provenance == SOURCE_NETWORK


def test_empty_area_raises_rather_than_inventing_roads():
    with pytest.raises(OsmLoaderError, match="No drivable roads"):
        load_osm_graph(a_location(), cache=tmp_cache(),
                       post_overpass=lambda u, q, t: payload())


# ===================================================== scenario adapter

def _graph_from_fixture(radius_m=600.0):
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    loc = resolve_location(latitude=26.8381, longitude=80.9346, radius_m=radius_m)
    return load_osm_graph(loc, cache=tmp_cache(), post_overpass=lambda u, q, t: data)


def test_real_extract_parses_into_a_routable_network():
    graph = _graph_from_fixture()

    assert graph.stats["ways_considered"] == 133
    assert graph.stats["kept_nodes"] > 100
    assert graph.stats["kept_edges"] > 200
    # Honest reflection of real Indian OSM data: almost nothing is tagged.
    assert graph.stats["ways_using_speed_fallback"] > graph.stats["ways_with_osm_maxspeed"]


def test_osm_ids_and_coordinates_are_preserved():
    graph = _graph_from_fixture()
    scenario = osm_graph_to_scenario(graph, num_jobs=10, num_vehicles=3, seed=42)

    for node in scenario.nodes:
        assert node.osm_id is not None
        original = graph.nodes[node.osm_id]
        assert node.lat == original.lat
        assert node.lng == original.lon

    osm_ids = [n.osm_id for n in scenario.nodes]
    assert len(set(osm_ids)) == len(osm_ids)


def test_depot_and_jobs_are_real_graph_nodes():
    graph = _graph_from_fixture()
    scenario = osm_graph_to_scenario(graph, num_jobs=10, num_vehicles=3, seed=42)

    node_ids = {n.id for n in scenario.nodes}
    osm_ids = {n.osm_id for n in scenario.nodes}

    assert scenario.depot_node_id in node_ids
    depot = [n for n in scenario.nodes if n.id == scenario.depot_node_id][0]
    assert depot.osm_id in graph.nodes

    assert len(scenario.jobs) == 10
    for job in scenario.jobs:
        assert job.node_id in node_ids
        job_node = [n for n in scenario.nodes if n.id == job.node_id][0]
        assert job_node.osm_id in graph.nodes, "every job sits on a real OSM node"

    for vehicle in scenario.vehicles:
        assert vehicle.start_node in node_ids
        assert vehicle.end_node in node_ids


def test_depot_is_the_node_closest_to_the_requested_centre():
    graph = _graph_from_fixture()
    depot_osm_id, _ = select_terminals(graph, num_jobs=5, seed=1)

    centre_lat, centre_lon = graph.location.latitude, graph.location.longitude
    depot = graph.nodes[depot_osm_id]
    best = min(haversine_m(centre_lat, centre_lon, n.lat, n.lon) for n in graph.nodes.values())
    assert haversine_m(centre_lat, centre_lon, depot.lat, depot.lon) == pytest.approx(best)


def test_terminal_selection_is_deterministic():
    graph = _graph_from_fixture()

    a = select_terminals(graph, num_jobs=12, seed=42)
    b = select_terminals(graph, num_jobs=12, seed=42)
    c = select_terminals(graph, num_jobs=12, seed=7)

    assert a == b, "same seed must give the same depot and jobs"
    assert a[1] != c[1], "a different seed must give different jobs"


def test_scenario_is_deterministic_end_to_end():
    one = osm_graph_to_scenario(_graph_from_fixture(), num_jobs=8, num_vehicles=2, seed=5)
    two = osm_graph_to_scenario(_graph_from_fixture(), num_jobs=8, num_vehicles=2, seed=5)

    assert one.scenario_hash == two.scenario_hash
    assert [j.node_id for j in one.jobs] == [j.node_id for j in two.jobs]
    assert [j.demand for j in one.jobs] == [j.demand for j in two.jobs]
    assert [e.distance for e in one.edges] == [e.distance for e in two.edges]


def test_scenario_edges_carry_osm_provenance_and_geometry():
    scenario = osm_graph_to_scenario(_graph_from_fixture(), num_jobs=8, num_vehicles=2, seed=5)

    assert scenario.data_source == "openstreetmap"
    assert all(e.osm_way_id is not None for e in scenario.edges)
    assert all(e.highway in DEFAULT_HIGHWAY_CLASSES for e in scenario.edges)
    assert all(e.speed_source for e in scenario.edges)
    curved = [e for e in scenario.edges if e.geometry and len(e.geometry) > 2]
    assert len(curved) > 50, "real road curvature must survive into the scenario"


def test_fresh_osm_network_is_free_flow_not_live_traffic():
    """OSM carries no traffic data. Every edge must start at factor 1.0."""
    scenario = osm_graph_to_scenario(_graph_from_fixture(), num_jobs=8, num_vehicles=2, seed=5)

    assert all(e.traffic_factor == 1.0 for e in scenario.edges)
    assert all(e.current_travel_time == e.base_travel_time for e in scenario.edges)


def test_traffic_factor_still_drives_cost_on_an_osm_scenario():
    scenario = osm_graph_to_scenario(_graph_from_fixture(), num_jobs=8, num_vehicles=2, seed=5)
    before = compute_route_matrix(scenario)
    baseline = float(before.time.array.sum())

    for edge in scenario.edges:
        edge.traffic_factor = 4.0
        edge.current_travel_time = edge.base_travel_time * 4.0

    after = compute_route_matrix(scenario)
    assert float(after.time.array.sum()) > baseline * 3.5


# ============================================ route matrix + optimizers

def test_route_matrix_stays_terminal_sized_on_a_real_network():
    scenario = osm_graph_to_scenario(_graph_from_fixture(), num_jobs=12, num_vehicles=3, seed=42)
    terminals = terminal_nodes(scenario)
    matrix = compute_route_matrix(scenario)

    assert len(scenario.nodes) > 100
    assert len(terminals) == 13  # depot + 12 jobs
    assert matrix.dist.shape == (13, 13), "must not grow with the road graph"


def test_shortest_paths_retain_intermediate_osm_nodes():
    scenario = osm_graph_to_scenario(_graph_from_fixture(), num_jobs=12, num_vehicles=3, seed=42)
    matrix = compute_route_matrix(scenario)
    terminals = set(matrix.terminals)

    longest = max(matrix.paths.values(), key=len)
    assert len(longest) > 3
    assert any(n not in terminals for n in longest[1:-1]), (
        "routes must travel through non-terminal road nodes")


def test_all_four_optimizers_run_on_a_real_osm_scenario():
    scenario = osm_graph_to_scenario(_graph_from_fixture(), num_jobs=10, num_vehicles=3, seed=42)
    config = OptimizationConfig(population_size=10, max_iterations=6, seed=42)

    result = run_benchmark(scenario, config)

    # 10 jobs is within the exact solver's cap, so it's expected here too.
    assert set(result.results.keys()) == {"greedy", "pso", "ga", "qpso", "qpso_ls", "qpso_memetic", "exact"}
    for name, outcome in result.results.items():
        assert outcome.total_cost > 0, name
        assert outcome.total_distance > 0, name
        assert len(outcome.routes) == 3, name
        visited = sorted(j for r in outcome.routes for j in r.job_ids)
        assert visited == list(range(1, 11)), f"{name} must visit every job once"
        for route in outcome.routes:
            assert route.node_path[0] == scenario.depot_node_id
            assert route.node_path[-1] == scenario.depot_node_id


# ============================================== no hardcoded locations

@pytest.mark.parametrize("module_name", ["realdata.osm_loader", "realdata.osm_scenario"])
def test_no_city_names_or_coordinate_tables_in_osm_code(module_name):
    import ast
    import importlib

    module = importlib.import_module(module_name)
    source = open(module.__file__, encoding="utf-8").read()
    tree = ast.parse(source)

    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                docstrings.add(doc)

    code_strings = " ".join(
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and n.value not in docstrings
    ).lower()

    for city in ("lucknow", "bengaluru", "mumbai", "delhi", "noida", "pune",
                 "hyderabad", "patna", "kolkata", "london", "new york"):
        assert city not in code_strings, f"'{city}' must not appear in executable code"

    # No literal latitude/longitude pair may be baked into the loader.
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            numeric_keys = sum(
                1 for k in node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            )
            coord_values = sum(
                1 for v in node.values if isinstance(v, (ast.Tuple, ast.List))
            )
            assert not (numeric_keys >= 3 and coord_values >= 3), (
                "dict mapping names to coordinate pairs looks like a city table")
