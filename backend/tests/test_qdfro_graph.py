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

    # Test shortest path live
    path, cost = iface.shortest_path_live("1", "10")
    assert len(path) > 1
    assert cost < 1e9

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
