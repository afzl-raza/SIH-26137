"""
qdfro_graph - Quantum-Inspired Dynamic Fleet Route Optimizer Graph Engine.
"""

from .schema import (
    NodeAttrs,
    EdgeAttrs,
    VehicleRoute,
    ReservationSlot,
    SpacetimeConflict
)
from .graph_model import TrafficGraph
from .weights import (
    bpr_travel_time,
    webster_delay,
    composite_edge_weight,
    fifo_safeguard,
    moving_average_smoother
)
from .dynamic import CostMatrixUpdater, DynamicEvent
from .spacetime import ReservationTable
from .qpso_interface import GraphQPSOInterface
from .assignment import msa_assignment
from .real_data import build_sioux_falls_real, load_sioux_falls_od_demand
from .benchmark import load_osm_network
from .solver import QPSOSolver

__all__ = [
    "NodeAttrs",
    "EdgeAttrs",
    "VehicleRoute",
    "ReservationSlot",
    "SpacetimeConflict",
    "TrafficGraph",
    "bpr_travel_time",
    "webster_delay",
    "composite_edge_weight",
    "fifo_safeguard",
    "moving_average_smoother",
    "CostMatrixUpdater",
    "DynamicEvent",
    "ReservationTable",
    "GraphQPSOInterface",
    "msa_assignment",
    "build_sioux_falls_real",
    "load_sioux_falls_od_demand",
    "load_osm_network",
    "QPSOSolver",
]
