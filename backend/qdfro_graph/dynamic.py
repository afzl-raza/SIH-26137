from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Optional, Callable
from .graph_model import TrafficGraph
from .schema import EdgeAttrs, VehicleRoute
from .weights import composite_edge_weight


@dataclass
class DynamicEvent:
    """Record of a link weight update event in the network."""
    event_type: str  # "drift" or "incident"
    edge: Tuple[str, str]
    old_weight: float
    new_weight: float
    severity: float = 0.0
    is_blocked: bool = False


class CostMatrixUpdater:
    """
    Dynamic cost matrix updater supporting Mode A (periodic congestion drift),
    Mode B (targeted incident injection/clearing), threshold gating (theta),
    route registration, and affected vehicle set identification.
    """

    def __init__(self, graph: TrafficGraph, theta: float = 0.15):
        self.graph = graph
        self.theta = theta  # Relative threshold gate (15% relative change default)
        self.active_routes: Dict[str, VehicleRoute] = {}

    def register_route(self, route: VehicleRoute) -> None:
        """Register or update an active vehicle route in the fleet."""
        self.active_routes[route.vehicle_id] = route

    def unregister_route(self, vehicle_id: str) -> None:
        """Remove a vehicle route from active tracker."""
        self.active_routes.pop(vehicle_id, None)

    def _compute_current_weight(self, edge: EdgeAttrs) -> float:
        """Helper to compute composite weight of an edge."""
        target_node = self.graph.get_node(edge.target)
        return composite_edge_weight(edge, target_node=target_node)

    def apply_drift(self, volume_deltas: Dict[Tuple[str, str], float]) -> List[DynamicEvent]:
        """
        Mode A: Apply periodic volume drift across network links and evaluate threshold gate.
        Returns list of DynamicEvent objects for links that exceeded theta threshold.
        """
        events = []
        for (u, v), delta in volume_deltas.items():
            edge = self.graph.get_edge(u, v)
            if not edge:
                continue

            old_w = edge.cached_weight if edge.cached_weight > 0 else self._compute_current_weight(edge)
            edge.volume_vph = max(0.0, edge.volume_vph + delta)
            new_w = self._compute_current_weight(edge)

            # Threshold gate check
            rel_change = abs(new_w - old_w) / max(0.001, old_w)
            if rel_change > self.theta:
                edge.cached_weight = new_w
                events.append(DynamicEvent(
                    event_type="drift",
                    edge=(u, v),
                    old_weight=old_w,
                    new_weight=new_w,
                    severity=edge.incident_severity,
                    is_blocked=edge.is_blocked
                ))
        return events

    def apply_incident(
        self,
        edge_pair: Tuple[str, str],
        flag: str = "blocked",
        severity: float = 1.0
    ) -> List[DynamicEvent]:
        """
        Mode B: Apply a targeted road incident (blocked road or heavy bottleneck).
        """
        u, v = edge_pair
        edge = self.graph.get_edge(u, v)
        if not edge:
            return []

        old_w = edge.cached_weight if edge.cached_weight > 0 else self._compute_current_weight(edge)
        if flag == "blocked":
            edge.is_blocked = True
            edge.incident_severity = 1.0
        else:
            edge.incident_severity = min(1.0, max(0.0, severity))

        new_w = self._compute_current_weight(edge)
        edge.cached_weight = new_w

        event = DynamicEvent(
            event_type="incident",
            edge=(u, v),
            old_weight=old_w,
            new_weight=new_w,
            severity=edge.incident_severity,
            is_blocked=edge.is_blocked
        )
        return [event]

    def clear_incident(self, edge_pair: Tuple[str, str]) -> List[DynamicEvent]:
        """Clear an incident on a directed road edge."""
        u, v = edge_pair
        edge = self.graph.get_edge(u, v)
        if not edge:
            return []

        old_w = self._compute_current_weight(edge)
        edge.is_blocked = False
        edge.incident_severity = 0.0
        new_w = self._compute_current_weight(edge)
        edge.cached_weight = new_w

        return [DynamicEvent(
            event_type="incident_clear",
            edge=(u, v),
            old_weight=old_w,
            new_weight=new_w,
            severity=0.0,
            is_blocked=False
        )]

    def get_affected_vehicles(self, events: List[DynamicEvent]) -> Set[str]:
        """
        Find exact subset of vehicle IDs whose planned route edges cross any modified edge in events.
        Enables targeted re-optimization instead of recalculating full fleet.
        """
        if not events:
            return set()

        modified_edges = {evt.edge for evt in events}
        affected = set()

        for veh_id, route in self.active_routes.items():
            # Check edge sequence
            route_edges = set(route.edges)
            if not route_edges and len(route.nodes) > 1:
                route_edges = set(zip(route.nodes[:-1], route.nodes[1:]))

            if route_edges.intersection(modified_edges):
                affected.add(veh_id)

        return affected
