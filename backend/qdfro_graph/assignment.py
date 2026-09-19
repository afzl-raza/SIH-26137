import networkx as nx
from typing import Dict, Tuple, List, Any
from .graph_model import TrafficGraph
from .weights import bpr_travel_time


def msa_assignment(
    graph: TrafficGraph,
    od_demand: Dict[Tuple[str, str], float],
    n_iterations: int = 20
) -> Dict[str, Any]:
    """
    Method of Successive Averages (MSA) user equilibrium traffic assignment.
    Loads origin-destination (OD) demand trips onto network topology to calculate equilibrium link volumes and congestion.
    """
    # Initialize link volumes to zero
    for edge in graph.edges():
        edge.volume_vph = 0.0

    n_iterations = max(1, n_iterations)

    for k in range(1, n_iterations + 1):
        # 1. Update link travel times using current volumes
        G_k = nx.DiGraph()
        for edge in graph.edges():
            t0 = edge.free_flow_travel_time_s
            t_bpr = bpr_travel_time(t0, edge.volume_vph, edge.capacity_vph, alpha=edge.alpha, beta=edge.beta)
            G_k.add_edge(edge.source, edge.target, weight=t_bpr)

        # 2. All-Or-Nothing (AON) assignment step
        aux_flows: Dict[Tuple[str, str], float] = {}

        # Cache shortest paths for each origin node
        all_nodes = [n.node_id for n in graph.nodes()]
        paths_cache = {}
        for origin in set(src for (src, _) in od_demand.keys()):
            if G_k.has_node(origin):
                try:
                    _, paths = nx.single_source_dijkstra(G_k, source=origin, weight="weight")
                    paths_cache[origin] = paths
                except Exception:
                    paths_cache[origin] = {}

        for (origin, dest), demand in od_demand.items():
            if demand <= 0:
                continue
            if origin in paths_cache and dest in paths_cache[origin]:
                path = paths_cache[origin][dest]
                for u, v in zip(path[:-1], path[1:]):
                    aux_flows[(u, v)] = aux_flows.get((u, v), 0.0) + demand

        # 3. Update link volumes using step size gamma_k = 1 / k
        gamma_k = 1.0 / float(k)
        for edge in graph.edges():
            y_e = aux_flows.get((edge.source, edge.target), 0.0)
            edge.volume_vph = (1.0 - gamma_k) * edge.volume_vph + gamma_k * y_e

    # Calculate summary metrics
    saturations = []
    for edge in graph.edges():
        sat = edge.volume_vph / max(1.0, edge.capacity_vph)
        saturations.append(sat)

    min_sat = min(saturations) if saturations else 0.0
    max_sat = max(saturations) if saturations else 0.0
    mean_sat = sum(saturations) / len(saturations) if saturations else 0.0

    return {
        "min_saturation": round(min_sat, 4),
        "max_saturation": round(max_sat, 4),
        "mean_saturation": round(mean_sat, 4),
        "total_network_volume": round(sum(e.volume_vph for e in graph.edges()), 2),
        "iterations": n_iterations,
    }
