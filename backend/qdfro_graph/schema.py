from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any


@dataclass
class NodeAttrs:
    """Attributes defining a physical or logical network node (intersection / depot)."""
    node_id: str
    name: str = ""
    lat: float = 0.0
    lng: float = 0.0
    is_depot: bool = False
    signal_cycle_s: float = 60.0    # C in Webster formula (seconds)
    green_ratio: float = 0.5        # lambda (g / C) ratio for main signal phase

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "lat": self.lat,
            "lng": self.lng,
            "is_depot": self.is_depot,
            "signal_cycle_s": self.signal_cycle_s,
            "green_ratio": self.green_ratio,
        }


@dataclass
class EdgeAttrs:
    """Attributes defining a directed roadway link."""
    source: str
    target: str
    length_m: float
    free_flow_speed_m_s: float
    capacity_vph: float
    alpha: float = 0.15
    beta: float = 4.0
    road_class: str = "arterial"     # freeway, arterial, collector, local
    lane_count: int = 2
    is_blocked: bool = False
    incident_severity: float = 0.0  # 0.0 (normal) to 1.0 (impassable)
    volume_vph: float = 0.0          # Current traffic volume (vehicles per hour)
    cached_weight: float = 0.0       # Cached composite weight for threshold gating

    @property
    def free_flow_travel_time_s(self) -> float:
        """t0 in seconds."""
        if self.free_flow_speed_m_s <= 0:
            return 1e6
        return self.length_m / self.free_flow_speed_m_s

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "length_m": self.length_m,
            "free_flow_speed_m_s": self.free_flow_speed_m_s,
            "capacity_vph": self.capacity_vph,
            "alpha": self.alpha,
            "beta": self.beta,
            "road_class": self.road_class,
            "lane_count": self.lane_count,
            "is_blocked": self.is_blocked,
            "incident_severity": self.incident_severity,
            "volume_vph": self.volume_vph,
            "free_flow_travel_time_s": self.free_flow_travel_time_s,
        }


@dataclass
class VehicleRoute:
    """Path assignment and vehicle characteristics for a single vehicle."""
    vehicle_id: str
    nodes: List[str] = field(default_factory=list)
    edges: List[Tuple[str, str]] = field(default_factory=list)
    start_time_s: float = 0.0
    speed_m_s: float = 13.89         # Nominal speed (~50 km/h)
    capacity_q: float = 100.0        # Vehicle payload capacity Q
    demand_served: float = 0.0       # Sum of job demands q_v
    time_window_start: float = 0.0   # Customer time window start (seconds)
    time_window_end: float = 86400.0 # Customer time window end (seconds)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vehicle_id": self.vehicle_id,
            "nodes": self.nodes,
            "edges": self.edges,
            "start_time_s": self.start_time_s,
            "speed_m_s": self.speed_m_s,
            "capacity_q": self.capacity_q,
            "demand_served": self.demand_served,
            "time_window_start": self.time_window_start,
            "time_window_end": self.time_window_end,
        }


@dataclass
class ReservationSlot:
    """Single 3D spacetime reservation slot."""
    vehicle_id: str
    time_slice: int
    node_id: Optional[str] = None
    edge: Optional[Tuple[str, str]] = None


@dataclass
class SpacetimeConflict:
    """Record of a detected spacetime collision between 2+ vehicles."""
    conflict_type: str  # "node", "same_direction_edge", "head_on_edge"
    vehicle_ids: List[str]
    location: str
    time_slice: int
    timestamp_s: float
