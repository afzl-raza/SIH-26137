import hashlib
import math
import random
import numpy as np
import networkx as nx
from typing import Tuple, Dict, List, Optional
from models import Node, Edge, Vehicle, Job, ProblemScenario


def compute_scenario_hash(
    num_nodes: int,
    num_jobs: int,
    num_vehicles: int,
    seed: int,
    extra: str = "",
) -> str:
    """Deterministic short id of the generation parameters - same inputs
    always produce the same hash, since generation itself is deterministic.
    Used as a reproducible "Run ID" for display/replay, not as a security
    hash.

    `extra` carries any additional input that distinguishes one scenario from
    another; the OSM path passes its bounding box, so two different places
    with the same job and vehicle counts do not collide. It defaults to empty
    so synthetic hashes are byte-identical to what they have always been.
    """
    raw = f"{num_nodes}:{num_jobs}:{num_vehicles}:{seed}"
    if extra:
        raw = f"{raw}:{extra}"
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


class _NodeIndexedMatrix:
    """Wraps a compact K x K array so it can still be indexed by node-ID pairs.

    The optimization path only ever queries routing *terminals* (the depot,
    vehicle start/end nodes and job nodes), so the underlying array is K x K
    rather than V x V. Indexing stays `matrix[u, v]` with real node IDs, which
    is why decoder.py and the optimizers need no changes.
    """

    __slots__ = ("_array", "_index")

    def __init__(self, array: np.ndarray, index: Dict[int, int]):
        self._array = array
        self._index = index

    def __getitem__(self, key: Tuple[int, int]) -> float:
        u, v = key
        try:
            return self._array[self._index[u], self._index[v]]
        except KeyError as exc:
            raise KeyError(
                f"node {exc.args[0]} is not a routing terminal; the route "
                f"matrix only covers the depot, vehicle start/end nodes and "
                f"job nodes"
            ) from None

    @property
    def array(self) -> np.ndarray:
        return self._array

    @property
    def shape(self) -> Tuple[int, int]:
        return self._array.shape


class RouteMatrix:
    """Shortest-path distances, travel times and full node paths between the
    routing terminals of a scenario.

    Memory is O(K^2) in the number of terminals (K = 1 depot + N jobs), not
    O(V^2) in the size of the road graph. The full graph is still traversed by
    Dijkstra, so `paths` contains complete node-by-node routes through
    intermediate road nodes - only the *matrix* is restricted.
    """

    __slots__ = ("terminals", "dist", "time", "paths")

    def __init__(
        self,
        terminals: List[int],
        dist_array: np.ndarray,
        time_array: np.ndarray,
        paths: Dict[Tuple[int, int], List[int]],
    ):
        index = {node_id: i for i, node_id in enumerate(terminals)}
        self.terminals = terminals
        self.dist = _NodeIndexedMatrix(dist_array, index)
        self.time = _NodeIndexedMatrix(time_array, index)
        self.paths = paths

    def as_tuple(self):
        """Unpacks into the (dist, time, paths) triple the optimizers use."""
        return self.dist, self.time, self.paths


def terminal_nodes(scenario: ProblemScenario) -> List[int]:
    """The only nodes the optimizers ever route between: the depot, every
    vehicle's start/end node, and every job node. Sorted and de-duplicated so
    the resulting matrix ordering is deterministic."""
    terminals = {scenario.depot_node_id}
    for v in scenario.vehicles:
        terminals.add(v.start_node)
        terminals.add(v.end_node)
    for j in scenario.jobs:
        terminals.add(j.node_id)
    return sorted(terminals)


def build_routing_graph(scenario: ProblemScenario) -> nx.DiGraph:
    """Builds the directed road graph used for routing. Edge weight is
    `current_travel_time`, i.e. base travel time already scaled by the edge's
    traffic factor - this is what makes congestion actually change routes."""
    G = nx.DiGraph()
    for n in scenario.nodes:
        G.add_node(n.id)
    for e in scenario.edges:
        G.add_edge(
            e.source,
            e.destination,
            weight=e.current_travel_time,
            distance=e.distance,
        )
    return G


UNREACHABLE = 1e6


def compute_route_matrix(
    scenario: ProblemScenario,
    terminals: Optional[List[int]] = None,
) -> RouteMatrix:
    """Computes shortest paths between routing terminals with K single-source
    Dijkstra runs over the *full* road graph.

    This replaces the previous all-pairs approach in the optimization path.
    The old version allocated two V x V float matrices plus a dict of V^2 node
    paths, which is fine for a 30-node synthetic graph but is not viable for a
    real OpenStreetMap extract of several thousand nodes. Restricting the
    matrix to terminals makes cost independent of road-graph size in memory,
    and linear rather than quadratic in Dijkstra runs.

    `terminals=None` uses the scenario's own terminals. Passing an explicit
    list is used by `compute_shortest_paths` for the all-pairs diagnostic
    variant, and by tests.
    """
    if terminals is None:
        terminals = terminal_nodes(scenario)

    G = build_routing_graph(scenario)
    k = len(terminals)

    dist_array = np.zeros((k, k))
    time_array = np.zeros((k, k))
    paths: Dict[Tuple[int, int], List[int]] = {}

    for row, source in enumerate(terminals):
        if G.has_node(source):
            _, paths_from_source = nx.single_source_dijkstra(G, source=source, weight="weight")
        else:
            paths_from_source = {}

        for col, target in enumerate(terminals):
            if source == target:
                dist_array[row, col] = 0.0
                time_array[row, col] = 0.0
                paths[(source, target)] = [source]
                continue

            path = paths_from_source.get(target)
            if path is None:
                dist_array[row, col] = UNREACHABLE
                time_array[row, col] = UNREACHABLE
                paths[(source, target)] = [source, target]
                continue

            total_t = 0.0
            total_d = 0.0
            for u, v in zip(path[:-1], path[1:]):
                edge_data = G[u][v]
                total_t += edge_data["weight"]
                total_d += edge_data["distance"]

            time_array[row, col] = total_t
            dist_array[row, col] = total_d
            paths[(source, target)] = path

    return RouteMatrix(terminals, dist_array, time_array, paths)


def compute_shortest_paths(
    scenario: ProblemScenario
) -> Tuple[np.ndarray, np.ndarray, Dict[Tuple[int, int], List[int]]]:
    """All-pairs variant, kept for diagnostics and tests.

    WARNING: this is O(V^2) in memory and is deliberately NOT used by the
    optimization path - see `compute_route_matrix`, which the optimizers call.
    It is retained because it exercises the same Dijkstra core over every node
    pair, which is what the hand-computed correctness tests check.

    Returns plain numpy arrays indexed by node ID (node IDs are contiguous
    from 0), matching the original signature.
    """
    node_ids = sorted(n.id for n in scenario.nodes)
    matrix = compute_route_matrix(scenario, terminals=node_ids)

    num_nodes = len(node_ids)
    dist_matrix = np.zeros((num_nodes, num_nodes))
    time_matrix = np.zeros((num_nodes, num_nodes))
    for row, u in enumerate(node_ids):
        for col, v in enumerate(node_ids):
            dist_matrix[u, v] = matrix.dist[u, v]
            time_matrix[u, v] = matrix.time[u, v]

    return dist_matrix, time_matrix, matrix.paths
