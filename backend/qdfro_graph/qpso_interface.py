import networkx as nx
from typing import Dict, List, Tuple, Optional, Callable, Set
from .dynamic import CostMatrixUpdater, DynamicEvent
from .spacetime import ReservationTable
from .schema import VehicleRoute
from .weights import composite_edge_weight


class GraphQPSOInterface:
    """
    High-level contract interface exposing graph topology, dynamic weights,
    route cost evaluation, live shortest paths, and re-optimization event notifications.
    """

    def __init__(self, updater: CostMatrixUpdater, reservations: ReservationTable):
        self.updater = updater
        self.reservations = reservations
        self.callbacks: List[Callable[[str], None]] = []

    @property
    def graph(self):
        return self.updater.graph

    def neighbors(self, node_id: str) -> List[str]:
        """Return downstream out-neighbors for node_id."""
        return self.graph.neighbors(node_id)

    def edge_weight(self, source: str, target: str) -> float:
        """Return live composite edge weight for link (source, target)."""
        edge = self.graph.get_edge(source, target)
        if not edge:
            return 1e9
        target_node = self.graph.get_node(target)
        return composite_edge_weight(edge, target_node=target_node)

    def route_cost(self, route: VehicleRoute) -> float:
        """
        Evaluate complete fitness cost for a vehicle route, including composite edge weights,
        capacity constraints, time windows, and 3D space-time conflict penalties.
        """
        if not route.nodes or len(route.nodes) < 2:
            return 0.0

        total_cost = 0.0
        # 1. Sum composite edge costs
        for u, v in zip(route.nodes[:-1], route.nodes[1:]):
            total_cost += self.edge_weight(u, v)

        # 2. Capacity constraint penalty
        if route.demand_served > route.capacity_q:
            total_cost += 1000.0 * ((route.demand_served - route.capacity_q) ** 2)

        # 3. Spacetime conflict penalty
        self.reservations.clear()
        self.reservations.add_route_reservation(route, self.graph)
        conflicts = self.reservations.detect_conflicts()
        total_cost += self.reservations.calculate_conflict_penalty(conflicts)

        return round(total_cost, 4)

    def shortest_path_live(self, source: str, target: str) -> Tuple[List[str], float]:
        """
        Compute Dijkstra shortest path between source and target using live non-blocked link weights.
        Returns (node_path, path_cost).
        """
        if not self.graph.graph.has_node(source) or not self.graph.graph.has_node(target):
            return ([], 1e9)

        if source == target:
            return ([source], 0.0)

        # Build weight lookup graph excluding blocked edges
        G_live = nx.DiGraph()
        for edge in self.graph.edges():
            if not edge.is_blocked and edge.incident_severity < 1.0:
                w = self.edge_weight(edge.source, edge.target)
                G_live.add_edge(edge.source, edge.target, weight=w)

        try:
            length, path = nx.single_source_dijkstra(G_live, source=source, target=target, weight="weight")
            return (path, round(length, 4))
        except nx.NetworkXNoPath:
            return ([], 1e9)

    def subscribe_to_weight_changes(self, callback: Callable[[str], None]) -> None:
        """Subscribe a handler callback(vehicle_id: str) to dynamic re-optimization triggers."""
        self.callbacks.append(callback)

    def notify_events(self, events: List[DynamicEvent]) -> Set[str]:
        """
        Evaluate dynamic events, find affected vehicle set, and notify all registered subscribers.
        Returns set of affected vehicle IDs.
        """
        affected_vehicles = self.updater.get_affected_vehicles(events)
        for veh_id in affected_vehicles:
            for cb in self.callbacks:
                cb(veh_id)
        return affected_vehicles
