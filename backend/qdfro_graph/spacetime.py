import math
from typing import Dict, List, Tuple, Optional, Set
from .schema import ReservationSlot, SpacetimeConflict, VehicleRoute
from .graph_model import TrafficGraph


class ReservationTable:
    """
    3D Space-Time Reservation Table tracking node, same-direction edge,
    and head-on edge collisions across fleet routes.
    """

    def __init__(self, slice_seconds: float = 10.0, k_penalty: float = 500.0):
        self.slice_seconds = max(1.0, slice_seconds)
        self.k_penalty = k_penalty
        self.reservations: List[ReservationSlot] = []

    def clear(self) -> None:
        """Clear all active reservations."""
        self.reservations.clear()

    def add_route_reservation(self, route: VehicleRoute, graph: TrafficGraph) -> None:
        """
        Discretize vehicle route into 3D spacetime reservation slots.
        Calculates expected traversal times along each edge.
        """
        if not route.nodes or len(route.nodes) < 2:
            return

        current_time_s = route.start_time_s

        # Reserve initial node at start time
        t_slice = int(current_time_s // self.slice_seconds)
        self.reservations.append(ReservationSlot(
            vehicle_id=route.vehicle_id,
            node_id=route.nodes[0],
            edge=None,
            time_slice=t_slice
        ))

        # Loop through path segments
        for u, v in zip(route.nodes[:-1], route.nodes[1:]):
            edge_attrs = graph.get_edge(u, v)
            if edge_attrs:
                t_traverse = edge_attrs.free_flow_travel_time_s
            else:
                t_traverse = 10.0  # Fallback 10s

            # Calculate start and end time slices for traversing link (u, v)
            start_slice = int(current_time_s // self.slice_seconds)
            end_time_s = current_time_s + t_traverse
            end_slice = int(end_time_s // self.slice_seconds)

            # Reserve edge (u, v) across all occupied time slices
            for ts in range(start_slice, end_slice + 1):
                self.reservations.append(ReservationSlot(
                    vehicle_id=route.vehicle_id,
                    node_id=None,
                    edge=(u, v),
                    time_slice=ts
                ))

            # Reserve arrival node v
            self.reservations.append(ReservationSlot(
                vehicle_id=route.vehicle_id,
                node_id=v,
                edge=None,
                time_slice=end_slice
            ))

            current_time_s = end_time_s

    def detect_conflicts(self) -> List[SpacetimeConflict]:
        """
        Detect node conflicts, same-direction edge conflicts, and head-on edge conflicts.
        """
        conflicts: List[SpacetimeConflict] = []

        # 1. Group node reservations by (node_id, time_slice)
        node_map: Dict[Tuple[str, int], List[str]] = {}
        # 2. Group edge reservations by (u, v, time_slice)
        edge_map: Dict[Tuple[str, str, int], List[str]] = {}

        for slot in self.reservations:
            if slot.node_id is not None:
                key = (slot.node_id, slot.time_slice)
                node_map.setdefault(key, [])
                if slot.vehicle_id not in node_map[key]:
                    node_map[key].append(slot.vehicle_id)

            if slot.edge is not None:
                u, v = slot.edge
                key = (u, v, slot.time_slice)
                edge_map.setdefault(key, [])
                if slot.vehicle_id not in edge_map[key]:
                    edge_map[key].append(slot.vehicle_id)

        # Check Node Conflicts
        for (node_id, ts), vehs in node_map.items():
            if len(vehs) > 1:
                conflicts.append(SpacetimeConflict(
                    conflict_type="node",
                    vehicle_ids=vehs,
                    location=f"Node {node_id}",
                    time_slice=ts,
                    timestamp_s=ts * self.slice_seconds
                ))

        # Check Same-Direction Edge Conflicts
        for (u, v, ts), vehs in edge_map.items():
            if len(vehs) > 1:
                conflicts.append(SpacetimeConflict(
                    conflict_type="same_direction_edge",
                    vehicle_ids=vehs,
                    location=f"Edge ({u}->{v})",
                    time_slice=ts,
                    timestamp_s=ts * self.slice_seconds
                ))

        # Check Head-On Edge Conflicts ((u, v) and (v, u) in same time slice)
        checked_pairs: Set[Tuple[str, str, int]] = set()
        for (u, v, ts), vehs in edge_map.items():
            reverse_key = (v, u, ts)
            if reverse_key in edge_map and (u, v, ts) not in checked_pairs:
                rev_vehs = edge_map[reverse_key]
                all_vehs = list(set(vehs + rev_vehs))
                conflicts.append(SpacetimeConflict(
                    conflict_type="head_on_edge",
                    vehicle_ids=all_vehs,
                    location=f"Opposing Edge ({u}<->{v})",
                    time_slice=ts,
                    timestamp_s=ts * self.slice_seconds
                ))
                checked_pairs.add((u, v, ts))
                checked_pairs.add((v, u, ts))

        return conflicts

    def calculate_conflict_penalty(self, conflicts: Optional[List[SpacetimeConflict]] = None) -> float:
        """Calculate total conflict penalty score P_conflict = k * N_conflicts."""
        if conflicts is None:
            conflicts = self.detect_conflicts()
        return self.k_penalty * len(conflicts)
