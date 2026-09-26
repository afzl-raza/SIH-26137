import networkx as nx
import pytest
from qdfro_graph import (
    NodeAttrs,
    EdgeAttrs,
    VehicleRoute,
    TrafficGraph,
    bpr_travel_time,
    webster_delay,
    composite_edge_weight,
    fifo_safeguard,
    moving_average_smoother,
    CostMatrixUpdater,
    ReservationTable,
    GraphQPSOInterface,
    msa_assignment,
    build_sioux_falls_real,
    load_sioux_falls_od_demand,
    load_osm_network,
    QPSOSolver
)


# ---------------------------------------------------------------------------
# Authoritative Sioux Falls topology (LeBlanc et al. 1975; the transcription
# everyone cites is the TNTP file at
# bstabler/TransportationNetworks/SiouxFalls/SiouxFalls_net.tntp). This is
# the canonical 24-node / 76-directed-link edge set: every one of the 38
# physical road segments is represented as two directed links, one per
# direction. It is written independently of backend/qdfro_graph/real_data.py
# so this test actually catches transcription errors instead of restating
# whatever the implementation happens to contain.
#
# A prior transcription bug (documented in docs/phase7_validation.md, section
# 2) dropped 10<->17, 16<->18 and 20<->22 and added a spurious 17<->20,
# yielding 72 edges instead of 76. That bug is fixed in real_data.py; this
# test set exists so it cannot silently regress.
# ---------------------------------------------------------------------------
SIOUX_FALLS_EXPECTED_EDGES = frozenset({
    ("1", "2"), ("1", "3"), ("2", "1"), ("2", "6"),
    ("3", "1"), ("3", "4"), ("3", "12"),
    ("4", "3"), ("4", "5"), ("4", "11"),
    ("5", "4"), ("5", "6"), ("5", "9"),
    ("6", "2"), ("6", "5"), ("6", "8"),
    ("7", "8"), ("7", "18"),
    ("8", "6"), ("8", "7"), ("8", "9"), ("8", "16"),
    ("9", "5"), ("9", "8"), ("9", "10"),
    ("10", "9"), ("10", "11"), ("10", "15"), ("10", "16"), ("10", "17"),
    ("11", "4"), ("11", "10"), ("11", "12"), ("11", "14"),
    ("12", "3"), ("12", "11"), ("12", "13"),
    ("13", "12"), ("13", "24"),
    ("14", "11"), ("14", "15"), ("14", "23"),
    ("15", "10"), ("15", "14"), ("15", "19"), ("15", "22"),
    ("16", "8"), ("16", "10"), ("16", "17"), ("16", "18"),
    ("17", "10"), ("17", "16"), ("17", "19"),
    ("18", "7"), ("18", "16"), ("18", "20"),
    ("19", "15"), ("19", "17"), ("19", "20"),
    ("20", "18"), ("20", "19"), ("20", "21"), ("20", "22"),
    ("21", "20"), ("21", "22"), ("21", "24"),
    ("22", "15"), ("22", "20"), ("22", "21"), ("22", "23"),
    ("23", "14"), ("23", "22"), ("23", "24"),
    ("24", "13"), ("24", "21"), ("24", "23"),
})

# Links a previous transcription bug got wrong in one way or another - kept
# as an explicit regression list so a future edit that reintroduces the bug
# fails loudly and specifically, not just as a generic set mismatch.
SIOUX_FALLS_PREVIOUSLY_BROKEN_DIRECTED_PAIRS = [
    ("10", "17"), ("17", "10"),
    ("16", "18"), ("18", "16"),
    ("20", "22"), ("22", "20"),
]
SIOUX_FALLS_SPURIOUS_PAIRS = [("17", "20"), ("20", "17")]


def test_bpr_and_webster_weights():
    # 1. Test BPR travel time
    t0 = 100.0
    vol = 1000.0
    cap = 1000.0
    t_bpr = bpr_travel_time(t0, vol, cap, alpha=0.15, beta=4.0)
    assert pytest.approx(t_bpr, 0.01) == 115.0  # 100 * (1 + 0.15 * 1^4)

    # 2. Test Webster signal delay
    d_webster = webster_delay(cycle_s=60.0, green_ratio=0.5, volume=500.0, capacity=1000.0)
    assert d_webster > 0.0

    # 3. Test FIFO safeguard
    travel_times = [10.0, 5.0, 20.0]  # k=1 departure 10s -> arrival 15s; k=2 departure 20s -> arrival 25s
    corrected = fifo_safeguard(travel_times, time_slice_step_s=10.0)
    assert len(corrected) == 3
    # arrival at k=0: 0 + 10 = 10
    # arrival at k=1: 10 + corrected[1] >= 10 => corrected[1] >= 0
    assert 10 + corrected[1] >= 10

    # 4. Moving average smoother
    vols = [100.0, 200.0, 300.0]
    smoothed = moving_average_smoother(vols, window_size=2)
    assert smoothed == [100.0, 150.0, 250.0]


def test_sioux_falls_network_and_msa():
    graph = build_sioux_falls_real()
    assert len(graph.nodes()) == 24
    assert len(graph.edges()) == 76

    od_demand = load_sioux_falls_od_demand()
    metrics = msa_assignment(graph, od_demand, n_iterations=5)

    assert "mean_saturation" in metrics
    assert metrics["mean_saturation"] > 0.0
    assert metrics["iterations"] == 5

    # Test GeoJSON exporter
    geojson = graph.to_geojson()
    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) > 0


def test_sioux_falls_topology_matches_canonical_edge_set():
    """Exact directed-topology validation (see docs/phase7_validation.md #2).

    A bare `len(edges()) == 76` count is not sufficient: a graph can have
    exactly 76 edges while still missing real links, containing spurious
    ones, or having a link's direction swapped. This compares the full
    directed edge set against an independently written canonical list, so
    missing edges, extra edges, wrong direction, and "one edge silently
    replaced by another of the same count" are all detected.
    """
    graph = build_sioux_falls_real()

    node_ids = {n.node_id for n in graph.nodes()}
    assert node_ids == {str(i) for i in range(1, 25)}

    actual_edges = {(e.source, e.target) for e in graph.edges()}

    missing = SIOUX_FALLS_EXPECTED_EDGES - actual_edges
    extra = actual_edges - SIOUX_FALLS_EXPECTED_EDGES
    assert not missing, f"missing canonical Sioux Falls links: {sorted(missing)}"
    assert not extra, f"extra/non-canonical links present: {sorted(extra)}"
    assert actual_edges == SIOUX_FALLS_EXPECTED_EDGES
    assert len(actual_edges) == 76

    # Every physical road segment in Sioux Falls is bidirectional: for every
    # directed link (u, v) the reverse (v, u) must also be present.
    asymmetric = [(u, v) for (u, v) in actual_edges if (v, u) not in actual_edges]
    assert not asymmetric, f"Sioux Falls links must all be bidirectional pairs: {asymmetric}"

    # Regression pins for the specific historical transcription bug.
    for u, v in SIOUX_FALLS_PREVIOUSLY_BROKEN_DIRECTED_PAIRS:
        assert graph.get_edge(u, v) is not None, f"missing required link {u} -> {v}"
    for u, v in SIOUX_FALLS_SPURIOUS_PAIRS:
        assert graph.get_edge(u, v) is None, f"spurious link {u} -> {v} must not exist"

    # (10, 17) and (17, 10) must be independent link objects, not the same
    # edge read in reverse - direction-specific state (volume, incidents,
    # capacity) must not be shared between a link and its reverse twin.
    assert graph.get_edge("10", "17") is not graph.get_edge("17", "10")


def _independent_live_dijkstra(graph, source, target):
    """Recompute shortest_path_live's result from scratch, independently of
    GraphQPSOInterface, using the same documented weight semantics
    (composite_edge_weight over non-blocked links). Used to derive an
    expected value from the benchmark data rather than hardcoding one.
    """
    g_live = nx.DiGraph()
    for edge in graph.edges():
        if not edge.is_blocked and edge.incident_severity < 1.0:
            target_node = graph.get_node(edge.target)
            g_live.add_edge(edge.source, edge.target, weight=composite_edge_weight(edge, target_node=target_node))
    try:
        length, path = nx.single_source_dijkstra(g_live, source=source, target=target, weight="weight")
        return path, length
    except nx.NetworkXNoPath:
        return [], 1e9


def test_sioux_falls_shortest_path_matrix():
    """Validates the OD cost 'matrix' this benchmark actually produces.

    qdfro_graph has no persistent 2D cost-matrix object for Sioux Falls;
    GraphQPSOInterface.shortest_path_live computes each OD entry on demand
    via live Dijkstra (see qpso_interface.py). So "the matrix" here is the
    set of pairwise (path, cost) results for the benchmark's routing
    terminals - the OD pairs in load_sioux_falls_od_demand(). This test
    validates that logical matrix: reachability, diagonal, directed
    (a)symmetry, and per-entry correctness against an independently
    recomputed expected value (never a hardcoded number).
    """
    graph = build_sioux_falls_real()
    od_demand = load_sioux_falls_od_demand()
    msa_assignment(graph, od_demand, n_iterations=15)

    updater = CostMatrixUpdater(graph, theta=0.15)
    reservations = ReservationTable()
    iface = GraphQPSOInterface(updater, reservations)

    # Diagonal: a trivial (source, source) entry must be a zero-cost
    # single-node path, not a Dijkstra call.
    path, cost = iface.shortest_path_live("5", "5")
    assert path == ["5"]
    assert cost == 0.0

    # Every OD pair this benchmark actually routes must be reachable, and
    # each entry must match an independently recomputed shortest path -
    # both the path (node sequence must be a walk over real edges) and the
    # cost (must equal the sum of live composite edge weights along it).
    for (origin, dest) in od_demand.keys():
        path, cost = iface.shortest_path_live(origin, dest)
        expected_path, expected_cost = _independent_live_dijkstra(graph, origin, dest)

        assert cost < 1e9, f"OD pair {origin}->{dest} must be reachable on the corrected topology"
        assert path == expected_path, f"path mismatch for {origin}->{dest}"
        assert cost == pytest.approx(expected_cost, abs=1e-6)

        # The returned path must be a genuine walk over existing directed edges.
        assert path[0] == origin and path[-1] == dest
        for u, v in zip(path[:-1], path[1:]):
            assert graph.get_edge(u, v) is not None, f"path uses non-existent link {u} -> {v}"

    # Directed asymmetry: the graph must not silently treat u->v and v->u as
    # the same entry. After MSA equilibrium, per-direction link volumes on a
    # shared physical segment can differ, so the forward and reverse costs
    # are computed completely independently (not required to be equal, but
    # must not be aliased to a single shared value).
    fwd_edge = graph.get_edge("10", "17")
    rev_edge = graph.get_edge("17", "10")
    assert fwd_edge is not rev_edge
    _, cost_fwd = iface.shortest_path_live("1", "10")
    _, cost_rev = iface.shortest_path_live("10", "1")
    _, expected_fwd = _independent_live_dijkstra(graph, "1", "10")
    _, expected_rev = _independent_live_dijkstra(graph, "10", "1")
    assert cost_fwd == pytest.approx(expected_fwd, abs=1e-6)
    assert cost_rev == pytest.approx(expected_rev, abs=1e-6)


def test_shortest_path_live_reports_unreachable_pairs_without_crashing():
    """Generic no-path handling of GraphQPSOInterface, exercised on a tiny,
    deliberately disconnected fixture graph (not a replacement for the
    Sioux Falls benchmark, which is fully strongly-connected and has no
    unreachable pairs of its own)."""
    graph = TrafficGraph()
    graph.add_node(NodeAttrs(node_id="A"))
    graph.add_node(NodeAttrs(node_id="B"))
    graph.add_node(NodeAttrs(node_id="ISOLATED"))
    graph.add_edge(EdgeAttrs(source="A", target="B", length_m=1000.0, free_flow_speed_m_s=10.0, capacity_vph=1000.0))

    updater = CostMatrixUpdater(graph)
    iface = GraphQPSOInterface(updater, ReservationTable())

    path, cost = iface.shortest_path_live("A", "ISOLATED")
    assert path == []
    assert cost == 1e9

    unknown_path, unknown_cost = iface.shortest_path_live("A", "DOES_NOT_EXIST")
    assert unknown_path == []
    assert unknown_cost == 1e9


def test_dynamic_updater_and_threshold_gate():
    graph = build_sioux_falls_real()
    updater = CostMatrixUpdater(graph, theta=0.10)

    # Register active route
    r1 = VehicleRoute(vehicle_id="V1", nodes=["1", "3", "4", "5"], edges=[("1", "3"), ("3", "4"), ("4", "5")])
    updater.register_route(r1)

    # Apply drift below threshold
    events_small = updater.apply_drift({("1", "2"): 10.0})
    assert len(events_small) == 0

    # Apply incident (Mode B)
    events_inc = updater.apply_incident(("1", "3"), flag="blocked")
    assert len(events_inc) == 1
    assert events_inc[0].is_blocked is True

    # Check affected vehicle identification
    affected = updater.get_affected_vehicles(events_inc)
    assert "V1" in affected


def test_incident_invalidates_matrix_costs_with_no_stale_cache():
    """qdfro_graph keeps no persistent cost-matrix cache: shortest_path_live
    rebuilds its live-weight graph from scratch on every call (see
    qpso_interface.py), so a matrix entry can never go stale after a traffic
    or incident update. This test pins that behaviour down as a regression
    guard, and separately proves EdgeAttrs.cached_weight (used only for
    CostMatrixUpdater's own Mode A threshold gating) cannot leak into live
    path costs.
    """
    graph = build_sioux_falls_real()
    updater = CostMatrixUpdater(graph, theta=0.15)
    iface = GraphQPSOInterface(updater, ReservationTable())

    path_before, cost_before = iface.shortest_path_live("1", "10")

    # Block whichever edge is actually on the current shortest path so the
    # incident is guaranteed to force a real recomputation.
    blocked_edge = next(iter(zip(path_before[:-1], path_before[1:])))
    events = updater.apply_incident(blocked_edge, flag="blocked")
    assert events[0].is_blocked is True

    path_after, cost_after = iface.shortest_path_live("1", "10")
    assert blocked_edge not in list(zip(path_after[:-1], path_after[1:])), \
        "blocked edge must not appear in a freshly computed shortest path"
    assert cost_after >= cost_before, "detouring around a blocked link cannot be cheaper"

    # Clearing the incident must restore live cost, again with no stale value.
    updater.clear_incident(blocked_edge)
    path_restored, cost_restored = iface.shortest_path_live("1", "10")
    assert cost_restored == pytest.approx(cost_before, abs=1e-6)
    assert path_restored == path_before

    # cached_weight must never be read by live path costing.
    edge = graph.get_edge(*blocked_edge)
    edge.is_blocked = False
    edge.incident_severity = 0.0
    genuine_weight = iface.edge_weight(*blocked_edge)
    edge.cached_weight = genuine_weight + 987654.0  # poison the cache field
    assert iface.edge_weight(*blocked_edge) == pytest.approx(genuine_weight, abs=1e-6)


def test_spacetime_reservation_and_conflicts():
    graph = build_sioux_falls_real()
    reservations = ReservationTable(slice_seconds=10.0, k_penalty=500.0)

    # Create two conflicting vehicle routes at node "3" in same time slice
    v1 = VehicleRoute(vehicle_id="V1", nodes=["1", "3", "4"], start_time_s=0.0)
    v2 = VehicleRoute(vehicle_id="V2", nodes=["2", "1", "3"], start_time_s=230.0)

    reservations.add_route_reservation(v1, graph)
    reservations.add_route_reservation(v2, graph)

    conflicts = reservations.detect_conflicts()
    penalty = reservations.calculate_conflict_penalty(conflicts)
    assert penalty >= 0.0


def test_graph_qpso_interface_and_solver():
    graph = build_sioux_falls_real()
    updater = CostMatrixUpdater(graph, theta=0.15)
    reservations = ReservationTable()
    iface = GraphQPSOInterface(updater, reservations)

    # Test shortest path live - must be a genuine walk over real links, not
    # just "some list longer than one node".
    path, cost = iface.shortest_path_live("1", "10")
    assert len(path) > 1
    assert cost < 1e9
    assert path[0] == "1" and path[-1] == "10"
    for u, v in zip(path[:-1], path[1:]):
        assert graph.get_edge(u, v) is not None

    # Test Pub/Sub Callback
    notified_vehs = []

    def on_reopt(v_id: str):
        notified_vehs.append(v_id)

    iface.subscribe_to_weight_changes(on_reopt)
    updater.register_route(VehicleRoute(vehicle_id="V1", nodes=["1", "3", "4"]))
    events = updater.apply_incident(("1", "3"), flag="blocked")
    iface.notify_events(events)
    assert "V1" in notified_vehs

    # Test QPSOSolver
    solver = QPSOSolver(iface, num_particles=10, max_iterations=5, seed=42)
    job_nodes = [("10", 10.0), ("15", 15.0)]
    vehicles = [("V1", "1", "1", 50.0)]
    routes = solver.solve(job_nodes, vehicles)

    assert "V1" in routes
    assert len(routes["V1"].nodes) >= 2


def test_osm_stub():
    with pytest.raises(NotImplementedError):
        load_osm_network("Sioux Falls")
