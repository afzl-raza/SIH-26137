"""Adapter: OpenStreetMap road graph -> ProblemScenario.

This is the seam that keeps the optimizers unaware of OpenStreetMap. GA, PSO,
QPSO and Greedy keep receiving exactly the ProblemScenario they always have;
they neither know nor care whether its edges came from the synthetic generator
or from a real road network. Nothing in the optimizer, decoder or objective
function changes.

Node identity
-------------
OSM node ids are 64-bit and sparse, while the route matrix and the decoder
index nodes by small contiguous integers. So nodes are renumbered 0..V-1 in a
deterministic order (sorted by OSM id), and the original id is preserved on
`Node.osm_id`. The depot is always renumbered to id 0, matching the synthetic
generator's convention.

Terminal selection
------------------
OSM contains roads, not delivery jobs, so depot and job locations have to be
chosen. Both rules are deterministic and neither hardcodes a location:

  * Depot   - the routable node closest to the centre of the requested area.
              That follows wherever the user pointed, whether that is a place
              name, a coordinate pair or a bounding box.
  * Jobs    - a seeded sample of routable nodes, drawn from the node list in
              sorted order so the same seed and the same area always produce
              the same jobs.

Every depot and job is an actual OSM node inside the strongly connected
component, so every one of them is genuinely reachable by road. No coordinate
is ever invented.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

import networkx as nx

from models import Edge, Job, Node, ProblemScenario, Vehicle
from problem_generator import compute_scenario_hash, generate_time_windows

from .osm_loader import OsmRoadGraph, haversine_m

# Matches the synthetic generator so the two sources look consistent in the UI.
FLEET_COLORS = ["#C99A3B", "#B5613F", "#5F8A80", "#5D7A9E", "#8A8C4E"]

DEFAULT_MAX_ROUTE_TIME_MIN = 150.0
DEMAND_MIN, DEMAND_MAX = 5.0, 15.0
SERVICE_TIME_MIN, SERVICE_TIME_MAX = 3.0, 8.0
CAPACITY_SLACK = 1.35


def _closest_node(graph: OsmRoadGraph, lat: float, lon: float) -> int:
    """Nearest routable OSM node to a point. Ties break on the smaller OSM id
    so the result cannot drift between runs."""
    return min(
        graph.nodes.values(),
        key=lambda n: (haversine_m(lat, lon, n.lat, n.lon), n.osm_id),
    ).osm_id


def _depot_travel_time_minutes(graph: OsmRoadGraph, depot_osm_id: int) -> Dict[int, float]:
    """Shortest free-flow travel time (minutes), depot -> every routable OSM
    node, for time-window generation (t0 in generate_time_windows).

    Built locally with travel_time_minutes as edge weight -
    `OsmRoadGraph.to_digraph()` uses distance (length_m) for a different
    purpose (connectivity analysis), so that graph isn't reused here.
    """
    g = nx.DiGraph()
    for osm_id in graph.nodes:
        g.add_node(osm_id)
    for edge in graph.edges:
        w = edge.travel_time_minutes
        existing = g.get_edge_data(edge.source, edge.target)
        if existing is None or w < existing["weight"]:
            g.add_edge(edge.source, edge.target, weight=w)
    if not g.has_node(depot_osm_id):
        return {}
    return nx.single_source_dijkstra_path_length(g, source=depot_osm_id, weight="weight")


def select_terminals(
    graph: OsmRoadGraph,
    num_jobs: int,
    seed: int,
) -> Tuple[int, List[int]]:
    """(depot_osm_id, [job_osm_id, ...]).

    Deterministic for a given graph, job count and seed.
    """
    center_lat, center_lon = graph.location.latitude, graph.location.longitude
    depot = _closest_node(graph, center_lat, center_lon)

    candidates = sorted(nid for nid in graph.nodes if nid != depot)
    if not candidates:
        return depot, []

    rng = random.Random(seed)
    count = min(num_jobs, len(candidates))
    jobs = sorted(rng.sample(candidates, count))
    return depot, jobs


def osm_graph_to_scenario(
    graph: OsmRoadGraph,
    num_jobs: int = 15,
    num_vehicles: int = 3,
    seed: int = 42,
    max_route_time_min: float = DEFAULT_MAX_ROUTE_TIME_MIN,
    time_windows: bool = False,
    tw_width_min: float = 60.0,
) -> ProblemScenario:
    """Builds a ProblemScenario from a real OSM road graph."""
    if not graph.nodes or not graph.edges:
        raise ValueError("Cannot build a scenario from an empty road graph.")

    depot_osm_id, job_osm_ids = select_terminals(graph, num_jobs, seed)

    # Renumber: depot becomes 0, everything else keeps sorted-OSM-id order.
    ordered = [depot_osm_id] + [n for n in sorted(graph.nodes) if n != depot_osm_id]
    index_of: Dict[int, int] = {osm_id: i for i, osm_id in enumerate(ordered)}

    nodes: List[Node] = []
    for osm_id in ordered:
        osm_node = graph.nodes[osm_id]
        internal = index_of[osm_id]
        is_depot = internal == 0
        nodes.append(Node(
            id=internal,
            name="Depot" if is_depot else f"OSM node {osm_id}",
            lat=osm_node.lat,
            lng=osm_node.lon,
            is_depot=is_depot,
            osm_id=osm_id,
        ))

    edges: List[Edge] = []
    for osm_edge in graph.edges:
        base_minutes = osm_edge.travel_time_minutes
        edges.append(Edge(
            source=index_of[osm_edge.source],
            destination=index_of[osm_edge.target],
            distance=round(osm_edge.length_m / 1000.0, 5),
            base_travel_time=round(base_minutes, 5),
            # A fresh OSM network is free-flow. OSM carries no traffic
            # information whatsoever; congestion is applied later and is
            # simulated, never observed.
            traffic_factor=1.0,
            current_travel_time=round(base_minutes, 5),
            road_name=osm_edge.name or f"{osm_edge.highway} {osm_edge.way_id}",
            osm_way_id=osm_edge.way_id,
            highway=osm_edge.highway,
            geometry=osm_edge.geometry,
            speed_kph=round(osm_edge.speed_kph, 3),
            speed_source=osm_edge.speed_source,
            lanes=osm_edge.lanes,
            lanes_source=osm_edge.lanes_source,
            capacity_vph=osm_edge.capacity_vph,
        ))

    rng = random.Random(seed)
    jobs: List[Job] = []
    service_times: List[float] = []
    total_demand = 0.0
    for position, osm_id in enumerate(job_osm_ids):
        demand = round(rng.uniform(DEMAND_MIN, DEMAND_MAX), 1)
        total_demand += demand
        service_time = round(rng.uniform(SERVICE_TIME_MIN, SERVICE_TIME_MAX), 1)
        service_times.append(service_time)
        jobs.append(Job(
            id=position + 1,
            node_id=index_of[osm_id],
            demand=demand,
            service_time=service_time,
            priority=rng.randint(1, 3),
        ))

    # Time windows (CVRPTW), opt-in. Drawn from a SEPARATE RNG (see
    # generate_time_windows) after every job is already fully built, so the
    # node/demand/service_time draws above are byte-identical whether or not
    # time_windows is set - only ready_time/due_time are added afterward.
    if time_windows:
        depot_travel_time = _depot_travel_time_minutes(graph, depot_osm_id)
        windows = generate_time_windows(
            job_node_ids=job_osm_ids,
            service_times=service_times,
            depot_travel_time=depot_travel_time,
            max_route_time=max_route_time_min,
            tw_width_min=tw_width_min,
            seed=seed,
        )
        for job, (ready, due) in zip(jobs, windows):
            job.ready_time = ready
            job.due_time = due

    vehicle_count = max(1, num_vehicles)
    capacity = round((total_demand / vehicle_count) * CAPACITY_SLACK, 1) if jobs else 100.0
    vehicles = [
        Vehicle(
            id=i + 1,
            capacity=capacity,
            start_node=0,
            end_node=0,
            max_route_time=max_route_time_min,
            color=FLEET_COLORS[i % len(FLEET_COLORS)],
        )
        for i in range(vehicle_count)
    ]

    # Same hash helper as the synthetic path - the bbox is folded in through
    # `extra` so two different places with the same job/vehicle counts do not
    # collide. No second hashing scheme is introduced. The TW param is folded
    # in ONLY when time_windows=True, so an existing OSM scenario hash stays
    # byte-identical.
    bbox = graph.location.bbox
    hash_extra = f"osm:{bbox.to_overpass_bbox()}"
    if time_windows:
        hash_extra = f"{hash_extra}:tw:{tw_width_min}"
    scenario_hash = compute_scenario_hash(
        num_nodes=len(nodes),
        num_jobs=len(jobs),
        num_vehicles=vehicle_count,
        seed=seed,
        extra=hash_extra,
    )

    return ProblemScenario(
        nodes=nodes,
        edges=edges,
        vehicles=vehicles,
        jobs=jobs,
        depot_node_id=0,
        seed=seed,
        scenario_hash=scenario_hash,
        data_source="openstreetmap",
    )
