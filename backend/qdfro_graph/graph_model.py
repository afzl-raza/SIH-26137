import networkx as nx
from typing import Dict, List, Tuple, Optional, Any
from .schema import NodeAttrs, EdgeAttrs, VehicleRoute


ROAD_CLASS_DEFAULTS = {
    "freeway": {"speed_m_s": 30.0, "cap_per_lane": 2000.0, "alpha": 0.15, "beta": 4.0},
    "arterial": {"speed_m_s": 16.67, "cap_per_lane": 1200.0, "alpha": 0.15, "beta": 4.0},
    "collector": {"speed_m_s": 11.11, "cap_per_lane": 800.0, "alpha": 0.15, "beta": 4.0},
    "local": {"speed_m_s": 8.33, "cap_per_lane": 500.0, "alpha": 0.15, "beta": 4.0},
}


class TrafficGraph:
    """NetworkX DiGraph wrapper for directed multi-attribute traffic networks."""

    def __init__(self):
        self.graph = nx.DiGraph()

    def add_node(self, attrs: NodeAttrs) -> None:
        """Add or update a node in the graph."""
        self.graph.add_node(attrs.node_id, attrs=attrs)

    def add_edge(self, attrs: EdgeAttrs) -> None:
        """Add or update a directed link in the graph."""
        # Fill in road class defaults if length/capacity/speed are defaults
        defaults = ROAD_CLASS_DEFAULTS.get(attrs.road_class, ROAD_CLASS_DEFAULTS["arterial"])
        if attrs.free_flow_speed_m_s <= 0:
            attrs.free_flow_speed_m_s = defaults["speed_m_s"]
        if attrs.capacity_vph <= 0:
            attrs.capacity_vph = defaults["cap_per_lane"] * attrs.lane_count

        self.graph.add_edge(attrs.source, attrs.target, attrs=attrs)

    def get_node(self, node_id: str) -> Optional[NodeAttrs]:
        """Retrieve node attributes by ID."""
        if self.graph.has_node(node_id):
            return self.graph.nodes[node_id].get("attrs")
        return None

    def get_edge(self, source: str, target: str) -> Optional[EdgeAttrs]:
        """Retrieve directed edge attributes by source and target."""
        if self.graph.has_edge(source, target):
            return self.graph.edges[source, target].get("attrs")
        return None

    def neighbors(self, node_id: str) -> List[str]:
        """Return downstream out-neighbors for a given node."""
        if self.graph.has_node(node_id):
            return list(self.graph.successors(node_id))
        return []

    def nodes(self) -> List[NodeAttrs]:
        """Return list of all node attribute objects."""
        return [data["attrs"] for _, data in self.graph.nodes(data=True) if "attrs" in data]

    def edges(self) -> List[EdgeAttrs]:
        """Return list of all directed edge attribute objects."""
        return [data["attrs"] for _, _, data in self.graph.edges(data=True) if "attrs" in data]

    def to_geojson(self, active_routes: Optional[List[VehicleRoute]] = None) -> Dict[str, Any]:
        """
        Serialize graph topology, dynamic link saturation, incidents, and fleet paths into standard GeoJSON.
        Compatible with Leaflet, Mapbox, Deck.gl, and frontend rendering.
        """
        features = []

        # Serialize Nodes (Point features)
        for node in self.nodes():
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [node.lng, node.lat]
                },
                "properties": {
                    "id": node.node_id,
                    "name": node.name,
                    "is_depot": node.is_depot,
                    "type": "depot" if node.is_depot else "intersection",
                    "signal_cycle_s": node.signal_cycle_s,
                }
            })

        # Serialize Edges (LineString features)
        for edge in self.edges():
            src_node = self.get_node(edge.source)
            tgt_node = self.get_node(edge.target)
            if src_node and tgt_node:
                saturation = edge.volume_vph / max(1.0, edge.capacity_vph)
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [src_node.lng, src_node.lat],
                            [tgt_node.lng, tgt_node.lat]
                        ]
                    },
                    "properties": {
                        "source": edge.source,
                        "target": edge.target,
                        "road_class": edge.road_class,
                        "volume_vph": edge.volume_vph,
                        "capacity_vph": edge.capacity_vph,
                        "saturation": round(saturation, 3),
                        "is_blocked": edge.is_blocked,
                        "incident_severity": edge.incident_severity,
                    }
                })

        # Serialize Active Vehicle Routes (LineString features)
        if active_routes:
            for route in active_routes:
                route_coords = []
                for n_id in route.nodes:
                    node = self.get_node(n_id)
                    if node:
                        route_coords.append([node.lng, node.lat])

                if len(route_coords) > 1:
                    features.append({
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": route_coords
                        },
                        "properties": {
                            "vehicle_id": route.vehicle_id,
                            "type": "vehicle_route",
                            "demand_served": route.demand_served,
                        }
                    })

        return {
            "type": "FeatureCollection",
            "features": features
        }
