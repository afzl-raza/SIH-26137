import hashlib
import math
import random
import numpy as np
import networkx as nx
from typing import Tuple, Dict, List
from models import Node, Edge, Vehicle, Job, ProblemScenario


def compute_scenario_hash(num_nodes: int, num_jobs: int, num_vehicles: int, seed: int) -> str:
    """Deterministic short id of the generation parameters - same inputs
    always produce the same hash, since generation itself is deterministic.
    Used as a reproducible "Run ID" for display/replay, not as a security
    hash."""
    raw = f"{num_nodes}:{num_jobs}:{num_vehicles}:{seed}"
    return hashlib.sha256(raw.encode()).hexdigest()[:10]


def generate_synthetic_scenario(
    num_nodes: int = 30,
    num_jobs: int = 15,
    num_vehicles: int = 3,
    seed: int = 42
) -> ProblemScenario:
    """
    Generates a deterministic synthetic urban transportation scenario.
    Depot is located at node 0.
    """
    random.seed(seed)
    np.random.seed(seed)

    # City center coordinates (e.g., Bengaluru center)
    center_lat = 12.9716
    center_lng = 77.5946

    # 1. Generate Node Locations within ~10km radius
    nodes: List[Node] = []
    # Node 0 is Depot at center
    nodes.append(Node(
        id=0,
        name="Central Depot",
        lat=center_lat,
        lng=center_lng,
        is_depot=True
    ))

    # Generate remaining nodes in clusters/grid for realistic urban topology
    for i in range(1, num_nodes):
        angle = random.uniform(0, 2 * math.pi)
        radius_km = random.uniform(0.5, 8.0)
        # 1 deg lat ~= 111 km, 1 deg lng ~= 111 * cos(lat) km
        lat_offset = (radius_km / 111.0) * math.cos(angle)
        lng_offset = (radius_km / (111.0 * math.cos(math.radians(center_lat)))) * math.sin(angle)
        nodes.append(Node(
            id=i,
            name=f"Intersection Node {i}",
            lat=center_lat + lat_offset,
            lng=center_lng + lng_offset,
            is_depot=False
        ))

    # 2. Construct Connected Urban Network Edges (k-NN graph + Delaunay)
    G = nx.Graph()
    for n in nodes:
        G.add_node(n.id, pos=(n.lat, n.lng))

    coords = np.array([[n.lat, n.lng] for n in nodes])
    
    # Connect each node to its k nearest neighbors to ensure urban road network topology
    k = min(4, num_nodes - 1)
    for i in range(num_nodes):
        # Calculate distance to all other nodes
        dists = []
        for j in range(num_nodes):
            if i == j:
                continue
            # Haversine distance in km
            d = haversine_distance(nodes[i].lat, nodes[i].lng, nodes[j].lat, nodes[j].lng)
            dists.append((d, j))
        dists.sort()
        for d, j in dists[:k]:
            if not G.has_edge(i, j):
                # Speed varies by road type (30 km/h to 60 km/h)
                speed = random.uniform(30.0, 50.0)
                base_time = (d / speed) * 60.0  # in minutes
                G.add_edge(i, j, distance=round(d, 2), base_time=round(base_time, 2))

    # Ensure graph is fully connected (add MST edges if disconnected)
    if not nx.is_connected(G):
        all_dists = []
        for i in range(num_nodes):
            for j in range(i + 1, num_nodes):
                if not G.has_edge(i, j):
                    d = haversine_distance(nodes[i].lat, nodes[i].lng, nodes[j].lat, nodes[j].lng)
                    all_dists.append((d, i, j))
        all_dists.sort()
        for d, i, j in all_dists:
            speed = 40.0
            base_time = (d / speed) * 60.0
            G.add_edge(i, j, distance=round(d, 2), base_time=round(base_time, 2))
            if nx.is_connected(G):
                break

    edges: List[Edge] = []
    for u, v, data in G.edges(data=True):
        road_name = f"Road {u}-{v}"
        e1 = Edge(
            source=u,
            destination=v,
            distance=data['distance'],
            base_travel_time=data['base_time'],
            traffic_factor=1.0,
            current_travel_time=data['base_time'],
            road_name=road_name
        )
        e2 = Edge(
            source=v,
            destination=u,
            distance=data['distance'],
            base_travel_time=data['base_time'],
            traffic_factor=1.0,
            current_travel_time=data['base_time'],
            road_name=road_name
        )
        edges.append(e1)
        edges.append(e2)

    # 3. Select Delivery Locations (Jobs)
    job_node_ids = random.sample(range(1, num_nodes), min(num_jobs, num_nodes - 1))
    jobs: List[Job] = []
    total_demand = 0.0
    for idx, node_id in enumerate(job_node_ids):
        demand = round(random.uniform(5.0, 15.0), 1)
        total_demand += demand
        jobs.append(Job(
            id=idx + 1,
            node_id=node_id,
            demand=demand,
            service_time=round(random.uniform(3.0, 8.0), 1),
            priority=random.randint(1, 3)
        ))

    # 4. Create Vehicles (Capacity total > total job demands)
    vehicle_capacity = round((total_demand / num_vehicles) * 1.35, 1)
    # Warm-neutral fleet palette (ochre/clay/teal/dusty-blue/olive) - keeps
    # vehicles visually distinct without a cool-toned rainbow fighting the
    # UI's asphalt/amber base palette.
    colors = ["#C99A3B", "#B5613F", "#5F8A80", "#5D7A9E", "#8A8C4E"]
    vehicles: List[Vehicle] = []
    for v in range(num_vehicles):
        vehicles.append(Vehicle(
            id=v + 1,
            capacity=vehicle_capacity,
            start_node=0,
            end_node=0,
            max_route_time=150.0,
            color=colors[v % len(colors)]
        ))

    return ProblemScenario(
        nodes=nodes,
        edges=edges,
        vehicles=vehicles,
        jobs=jobs,
        depot_node_id=0,
        seed=seed,
        scenario_hash=compute_scenario_hash(num_nodes, num_jobs, num_vehicles, seed)
    )


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates geographical distance between two lat/lng points in kilometers."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def compute_shortest_paths(scenario: ProblemScenario) -> Tuple[np.ndarray, np.ndarray, Dict[Tuple[int, int], List[int]]]:
    """
    Computes shortest path distance matrix, travel time matrix, and node path lookup
    for all pairs of network nodes using current travel times (accounting for traffic factors).
    Returns (distance_matrix, travel_time_matrix, paths_dict).

    Uses one single_source_dijkstra call per source node (O(V) Dijkstra runs)
    rather than one shortest_path call per (source, target) pair (O(V^2) runs) -
    the latter does not scale past a few hundred nodes.
    """
    num_nodes = len(scenario.nodes)
    G = nx.DiGraph()
    for n in scenario.nodes:
        G.add_node(n.id)

    for e in scenario.edges:
        # edge weight for routing is current_travel_time
        G.add_edge(e.source, e.destination, weight=e.current_travel_time, distance=e.distance)

    dist_matrix = np.zeros((num_nodes, num_nodes))
    time_matrix = np.zeros((num_nodes, num_nodes))
    paths_dict = {}

    for i in range(num_nodes):
        _, paths_from_i = nx.single_source_dijkstra(G, source=i, weight='weight')

        for j in range(num_nodes):
            if i == j:
                dist_matrix[i, j] = 0.0
                time_matrix[i, j] = 0.0
                paths_dict[(i, j)] = [i]
            elif j in paths_from_i:
                path = paths_from_i[j]
                paths_dict[(i, j)] = path
                # Sum time and distance along path
                total_t = 0.0
                total_d = 0.0
                for u, v in zip(path[:-1], path[1:]):
                    edge_data = G[u][v]
                    total_t += edge_data['weight']
                    total_d += edge_data['distance']
                time_matrix[i, j] = total_t
                dist_matrix[i, j] = total_d
            else:
                time_matrix[i, j] = 1e6
                dist_matrix[i, j] = 1e6
                paths_dict[(i, j)] = [i, j]

    return dist_matrix, time_matrix, paths_dict
