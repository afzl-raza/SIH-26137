import math
import random
import numpy as np
from typing import List, Dict, Tuple, Optional
from .schema import VehicleRoute
from .qpso_interface import GraphQPSOInterface


class QPSOSolver:
    """
    Quantum-behaved Particle Swarm Optimization (QPSO) core solver for Vehicle Routing.
    Implements delta-potential wave function position updates with mean best (M),
    personal best (P_i), global best (G), and contraction-expansion coefficient (beta).
    """

    def __init__(
        self,
        interface: GraphQPSOInterface,
        num_particles: int = 40,
        max_iterations: int = 100,
        seed: int = 42
    ):
        self.interface = interface
        self.num_particles = num_particles
        self.max_iterations = max_iterations
        self.seed = seed

    def solve(
        self,
        job_nodes: List[Tuple[str, float]],  # List of (node_id, demand)
        vehicles: List[Tuple[str, str, str, float]], # List of (veh_id, start_node, end_node, capacity)
        beta_start: float = 1.0,
        beta_end: float = 0.5
    ) -> Dict[str, VehicleRoute]:
        """
        Runs QPSO swarm search over continuous random keys to find minimum cost vehicle routes.
        Returns dict of vehicle_id -> VehicleRoute.
        """
        random.seed(self.seed)
        np.random.seed(self.seed)

        num_jobs = len(job_nodes)
        num_vehicles = len(vehicles)

        if num_jobs == 0 or num_vehicles == 0:
            return {}

        dim = num_jobs

        # 1. Initialize swarm positions in [0, 1]^dim
        positions = np.random.uniform(0.0, 1.0, size=(self.num_particles, dim))
        pbest_positions = np.copy(positions)
        pbest_costs = np.full(self.num_particles, 1e9)

        gbest_position = np.copy(positions[0])
        gbest_cost = 1e9

        # Evaluate initial swarm
        for i in range(self.num_particles):
            routes = self._decode_solution(positions[i], job_nodes, vehicles)
            cost = sum(self.interface.route_cost(r) for r in routes.values())
            pbest_costs[i] = cost
            if cost < gbest_cost:
                gbest_cost = cost
                gbest_position = np.copy(positions[i])

        # 2. QPSO Main Iteration Loop
        for it in range(self.max_iterations):
            # Linearly decay contraction-expansion coefficient beta
            beta = beta_start - (beta_start - beta_end) * (it / max(1, self.max_iterations - 1))

            # Compute mean best position M = (1/N) * sum(P_i)
            mbest = np.mean(pbest_positions, axis=0)

            for i in range(self.num_particles):
                for j in range(dim):
                    phi = random.random()
                    # Stochastic local attractor point p_{i,j}
                    p_ij = phi * pbest_positions[i, j] + (1.0 - phi) * gbest_position[j]

                    u = random.random()
                    if u <= 0.0001:
                        u = 0.0001

                    # Quantum delta-potential wave function position update
                    L = beta * abs(mbest[j] - positions[i, j]) * math.log(1.0 / u)

                    if random.random() < 0.5:
                        positions[i, j] = p_ij + L
                    else:
                        positions[i, j] = p_ij - L

                    # Clamp position to [0.0, 1.0]
                    positions[i, j] = max(0.0, min(1.0, positions[i, j]))

                # Evaluate new particle solution
                routes = self._decode_solution(positions[i], job_nodes, vehicles)
                cost = sum(self.interface.route_cost(r) for r in routes.values())

                if cost < pbest_costs[i]:
                    pbest_costs[i] = cost
                    pbest_positions[i] = np.copy(positions[i])
                    if cost < gbest_cost:
                        gbest_cost = cost
                        gbest_position = np.copy(positions[i])

        # Decode best solution
        best_routes = self._decode_solution(gbest_position, job_nodes, vehicles)
        return best_routes

    def _decode_solution(
        self,
        keys: np.ndarray,
        job_nodes: List[Tuple[str, float]],
        vehicles: List[Tuple[str, str, str, float]]
    ) -> Dict[str, VehicleRoute]:
        """
        Decodes a continuous position vector in [0, 1]^dim into feasible vehicle node sequences.
        """
        num_vehicles = len(vehicles)
        num_jobs = len(job_nodes)

        veh_job_assignments: Dict[int, List[Tuple[float, int]]] = {v: [] for v in range(num_vehicles)}

        for j_idx, key in enumerate(keys):
            v_idx = min(num_vehicles - 1, int(math.floor(key * num_vehicles)))
            seq_key = key * num_vehicles - v_idx
            veh_job_assignments[v_idx].append((seq_key, j_idx))

        routes: Dict[str, VehicleRoute] = {}

        for v_idx, (veh_id, start_node, end_node, capacity) in enumerate(vehicles):
            assigned = veh_job_assignments[v_idx]
            assigned.sort(key=lambda item: item[0])  # Sort by sequence key

            job_indices = [idx for _, idx in assigned]
            stop_nodes = [job_nodes[idx][0] for idx in job_indices]
            demands = [job_nodes[idx][1] for idx in job_indices]

            total_demand = sum(demands)

            # Build full node path by connecting stops with shortest paths
            full_node_path = [start_node]
            curr_node = start_node

            for stop in stop_nodes:
                path, _ = self.interface.shortest_path_live(curr_node, stop)
                if path and len(path) > 1:
                    full_node_path.extend(path[1:])
                elif not path:
                    full_node_path.append(stop)
                curr_node = stop

            # Return to end_node (depot)
            if curr_node != end_node:
                path, _ = self.interface.shortest_path_live(curr_node, end_node)
                if path and len(path) > 1:
                    full_node_path.extend(path[1:])
                elif not path:
                    full_node_path.append(end_node)

            edge_sequence = list(zip(full_node_path[:-1], full_node_path[1:]))

            routes[veh_id] = VehicleRoute(
                vehicle_id=veh_id,
                nodes=full_node_path,
                edges=edge_sequence,
                capacity_q=capacity,
                demand_served=total_demand
            )

        return routes
