"""Unit tests for backend/route_geometry.py.

The thing worth protecting here is that the drawn route is the route that was
actually costed. Two ways that could silently break:

  * the geometry lookup picks a different parallel edge than the router did;
  * an edge's geometry is used in the wrong direction, so the polyline
    backtracks.

Both are checked below, against real OSM geometry from the recorded Overpass
extract rather than a hand-built graph.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import Edge, Job, Node, ProblemScenario, Vehicle, VehicleRoute
from problem_generator import build_routing_graph, generate_synthetic_scenario
from realdata.cache import DiskCache
from realdata.geocoding import resolve_location
from realdata.osm_loader import load_osm_graph
from realdata.osm_scenario import osm_graph_to_scenario
from route_geometry import (
    GEOMETRY_OSM,
    GEOMETRY_STRAIGHT,
    edge_polylines,
    node_path_polyline,
    route_geometries,
    scenario_geometry_source,
    segment_geometry,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "overpass_real_extract.json"
REAL_PAYLOAD = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def osm_scenario():
    """A scenario built from the recorded real Overpass extract."""
    location = resolve_location(latitude=26.8381, longitude=80.9346, radius_m=600)
    graph = load_osm_graph(
        location,
        cache=DiskCache(root=Path(tempfile.mkdtemp(prefix="geomtest_"))),
        post_overpass=lambda url, query, timeout: REAL_PAYLOAD,
    )
    return osm_graph_to_scenario(graph, num_jobs=8, num_vehicles=2, seed=42)


@pytest.fixture(scope="module")
def synthetic_scenario():
    return generate_synthetic_scenario(num_nodes=20, num_jobs=8, num_vehicles=2, seed=42)


# ============================================================ OSM geometry

def test_osm_edges_carry_real_geometry(osm_scenario):
    """The precondition everything else rests on: OSM edges have polylines."""
    with_geometry = [e for e in osm_scenario.edges if e.geometry and len(e.geometry) >= 2]
    assert with_geometry, "OSM scenario produced no edge geometry at all"
    assert len(with_geometry) == len(osm_scenario.edges)

    for edge in with_geometry[:50]:
        for point in edge.geometry:
            assert len(point) == 2
            assert -90.0 <= point[0] <= 90.0
            assert -180.0 <= point[1] <= 180.0


def test_edge_geometry_endpoints_match_its_nodes(osm_scenario):
    """Geometry runs source -> destination, so a route can be stitched from it
    without checking orientation at every hop."""
    nodes = {n.id: (n.lat, n.lng) for n in osm_scenario.nodes}
    for edge in osm_scenario.edges[:200]:
        start, end = edge.geometry[0], edge.geometry[-1]
        assert start == pytest.approx(list(nodes[edge.source]), abs=1e-6)
        assert end == pytest.approx(list(nodes[edge.destination]), abs=1e-6)


def test_some_osm_edges_are_genuinely_curved(osm_scenario):
    """If every edge had exactly two points, drawing geometry would be no
    better than drawing straight lines and this whole feature would be moot."""
    curved = [e for e in osm_scenario.edges if len(e.geometry) > 2]
    assert curved, "no OSM edge retained intermediate shape points"


def test_scenario_geometry_source_distinguishes_the_two_networks(
    osm_scenario, synthetic_scenario
):
    assert scenario_geometry_source(osm_scenario) == GEOMETRY_OSM
    assert scenario_geometry_source(synthetic_scenario) == GEOMETRY_STRAIGHT


# ========================================================== route polylines

def test_route_polyline_follows_osm_geometry(osm_scenario):
    """A route over real roads is drawn from the roads' own shapes, and is
    strictly more detailed than the junction-to-junction path."""
    node_path = _a_real_path(osm_scenario, hops=6)
    resolved = node_path_polyline(osm_scenario, node_path)

    assert resolved["geometry_source"] == GEOMETRY_OSM
    assert resolved["node_count"] == len(node_path)
    assert resolved["point_count"] >= len(node_path)
    assert len(resolved["segments"]) == len(node_path) - 1


def test_route_polyline_starts_and_ends_at_the_path_endpoints(osm_scenario):
    node_path = _a_real_path(osm_scenario, hops=5)
    nodes = {n.id: [n.lat, n.lng] for n in osm_scenario.nodes}
    polyline = node_path_polyline(osm_scenario, node_path)["polyline"]

    assert polyline[0] == pytest.approx(nodes[node_path[0]], abs=1e-6)
    assert polyline[-1] == pytest.approx(nodes[node_path[-1]], abs=1e-6)


def test_shared_junctions_are_not_emitted_twice(osm_scenario):
    """Each edge's geometry includes both endpoints, so consecutive hops would
    duplicate the junction between them if stitching were naive."""
    node_path = _a_real_path(osm_scenario, hops=6)
    polyline = node_path_polyline(osm_scenario, node_path)["polyline"]

    for previous, current in zip(polyline[:-1], polyline[1:]):
        assert previous != current


def test_every_hop_is_a_real_edge_the_router_could_have_used(osm_scenario):
    """The geometry lookup must resolve the same directed edge the routing
    graph holds - otherwise the map draws a road the optimizer never costed."""
    node_path = _a_real_path(osm_scenario, hops=6)
    graph = build_routing_graph(osm_scenario)
    resolved = node_path_polyline(osm_scenario, node_path)

    for segment in resolved["segments"]:
        assert graph.has_edge(segment["source"], segment["destination"])
        assert segment["geometry_source"] == GEOMETRY_OSM


def test_route_geometries_covers_every_vehicle(osm_scenario):
    routes = [
        VehicleRoute(
            vehicle_id=1,
            job_ids=[1],
            node_path=_a_real_path(osm_scenario, hops=4),
            route_distance=1.0,
            route_travel_time=1.0,
            total_demand=1.0,
        ),
        VehicleRoute(
            vehicle_id=2,
            job_ids=[],
            node_path=[osm_scenario.depot_node_id],
            route_distance=0.0,
            route_travel_time=0.0,
            total_demand=0.0,
        ),
    ]
    resolved = route_geometries(osm_scenario, routes)

    assert [r["vehicle_id"] for r in resolved] == [1, 2]
    assert resolved[0]["point_count"] > 1
    # A vehicle with no jobs still has a drawable position, and no hops.
    assert resolved[1]["point_count"] == 1
    assert resolved[1]["segments"] == []


# ===================================================== synthetic fallback

def test_synthetic_routes_fall_back_to_straight_lines(synthetic_scenario):
    """Synthetic roads genuinely are straight lines. The fallback must keep
    working and must say what it is, not imply OSM fidelity."""
    node_path = _a_real_path(synthetic_scenario, hops=4)
    resolved = node_path_polyline(synthetic_scenario, node_path)

    assert resolved["geometry_source"] == GEOMETRY_STRAIGHT
    # One point per node: no intermediate shape points exist to add.
    assert resolved["point_count"] == len(node_path)
    assert all(s["geometry_source"] == GEOMETRY_STRAIGHT for s in resolved["segments"])


def test_synthetic_polyline_matches_the_node_coordinates(synthetic_scenario):
    node_path = _a_real_path(synthetic_scenario, hops=4)
    nodes = {n.id: [n.lat, n.lng] for n in synthetic_scenario.nodes}
    polyline = node_path_polyline(synthetic_scenario, node_path)["polyline"]

    assert polyline == [nodes[nid] for nid in node_path]


def test_edge_polylines_are_produced_for_both_network_kinds(
    osm_scenario, synthetic_scenario
):
    osm_lines = edge_polylines(osm_scenario)
    synthetic_lines = edge_polylines(synthetic_scenario)

    assert len(osm_lines) == len(osm_scenario.edges)
    assert len(synthetic_lines) == len(synthetic_scenario.edges)
    assert all(line["geometry_source"] == GEOMETRY_OSM for line in osm_lines)
    assert all(line["geometry_source"] == GEOMETRY_STRAIGHT for line in synthetic_lines)
    assert all(len(line["polyline"]) >= 2 for line in synthetic_lines)


# ================================================================ edge cases

def test_a_missing_edge_still_draws_the_straight_line():
    """An edge the scenario does not contain - which the router would never
    have chosen - degrades to the straight line rather than vanishing."""
    points, origin = segment_geometry(None, (1.0, 2.0), (3.0, 4.0))
    assert points == [[1.0, 2.0], [3.0, 4.0]]
    assert origin == GEOMETRY_STRAIGHT


def test_parallel_edges_resolve_the_same_way_the_router_resolved_them():
    """networkx keeps the LAST edge added for a node pair, so the geometry
    index must too."""
    nodes = [
        Node(id=0, name="Depot", lat=0.0, lng=0.0, is_depot=True),
        Node(id=1, name="A", lat=0.01, lng=0.01),
    ]
    first = Edge(
        source=0, destination=1, distance=1.0, base_travel_time=2.0,
        current_travel_time=2.0, road_name="first",
        geometry=[[0.0, 0.0], [0.005, 0.0], [0.01, 0.01]],
    )
    second = Edge(
        source=0, destination=1, distance=1.0, base_travel_time=2.0,
        current_travel_time=2.0, road_name="second",
        geometry=[[0.0, 0.0], [0.0, 0.005], [0.01, 0.01]],
    )
    scenario = ProblemScenario(
        nodes=nodes, edges=[first, second],
        vehicles=[Vehicle(id=1, capacity=10.0, start_node=0, end_node=0)],
        jobs=[Job(id=1, node_id=1, demand=1.0)],
        depot_node_id=0,
    )

    graph = build_routing_graph(scenario)
    routed_edge_name = "second"  # last added wins in networkx
    assert graph[0][1]["weight"] == second.current_travel_time

    resolved = node_path_polyline(scenario, [0, 1])
    assert resolved["polyline"] == second.geometry
    assert resolved["segments"][0]["road_name"] == routed_edge_name


def test_an_empty_path_produces_nothing_rather_than_a_guess(synthetic_scenario):
    resolved = node_path_polyline(synthetic_scenario, [])
    assert resolved["polyline"] == []
    assert resolved["segments"] == []


# ------------------------------------------------------------------ helpers

def _a_real_path(scenario, hops: int):
    """Walks `hops` real edges out of the depot, so tests exercise paths the
    router could actually produce rather than invented node sequences."""
    graph = build_routing_graph(scenario)
    path = [scenario.depot_node_id]
    seen = {scenario.depot_node_id}

    while len(path) <= hops:
        successors = [n for n in graph.successors(path[-1]) if n not in seen]
        if not successors:
            break
        nxt = min(successors)
        path.append(nxt)
        seen.add(nxt)

    assert len(path) >= 3, "could not walk far enough into the graph to test"
    return path
