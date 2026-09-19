import time
import numpy as np
from typing import List
from models import ProblemScenario, OptimizationConfig, OptimizationResult
from route_cache import get_route_matrix
from decoder import decode_random_keys
from fitness import evaluate_solution
from optimizers.base import BaseOptimizer


class PSOOptimizer(BaseOptimizer):
    def __init__(self):
        super().__init__(name="Classical PSO")

    def optimize(
        self,
        scenario: ProblemScenario,
        config: OptimizationConfig
    ) -> OptimizationResult:
        start_time = time.perf_counter()
        np.random.seed(config.seed)

        dist_matrix, time_matrix, paths_dict = get_route_matrix(scenario).as_tuple()
        num_jobs = len(scenario.jobs)

        if num_jobs == 0:
            return evaluate_solution([], scenario, config.weights, self.name, 0.0, [])

        pop_size = config.population_size
        max_iter = config.max_iterations

        # Inertia and acceleration coefficients
        w = 0.7
        c1 = 1.49
        c2 = 1.49

        # Initialize particles position X in [0, 1]^num_jobs and velocity V in [-0.2, 0.2]
        X = np.random.rand(pop_size, num_jobs)
        V = np.random.uniform(-0.2, 0.2, (pop_size, num_jobs))

        pbest_pos = np.copy(X)
        pbest_cost = np.full(pop_size, float('inf'))
        pbest_routes = [None] * pop_size

        gbest_pos = None
        gbest_cost = float('inf')
        gbest_routes = None

        convergence_history: List[float] = []
        convergence_elapsed_ms: List[float] = []

        for i in range(pop_size):
            routes = decode_random_keys(X[i], scenario, dist_matrix, time_matrix, paths_dict)
            res = evaluate_solution(routes, scenario, config.weights, self.name)
            pbest_cost[i] = res.total_cost
            pbest_routes[i] = routes

            if res.total_cost < gbest_cost:
                gbest_cost = res.total_cost
                gbest_pos = np.copy(X[i])
                gbest_routes = routes

        convergence_history.append(gbest_cost)
        convergence_elapsed_ms.append((time.perf_counter() - start_time) * 1000.0)

        for iteration in range(1, max_iter):
            r1 = np.random.rand(pop_size, num_jobs)
            r2 = np.random.rand(pop_size, num_jobs)

            # Velocity update
            V = w * V + c1 * r1 * (pbest_pos - X) + c2 * r2 * (gbest_pos - X)
            V = np.clip(V, -0.5, 0.5)

            # Position update
            X = np.clip(X + V, 0.0, 1.0)

            # Evaluate new positions
            for i in range(pop_size):
                routes = decode_random_keys(X[i], scenario, dist_matrix, time_matrix, paths_dict)
                res = evaluate_solution(routes, scenario, config.weights, self.name)

                if res.total_cost < pbest_cost[i]:
                    pbest_cost[i] = res.total_cost
                    pbest_pos[i] = np.copy(X[i])
                    pbest_routes[i] = routes

                    if res.total_cost < gbest_cost:
                        gbest_cost = res.total_cost
                        gbest_pos = np.copy(X[i])
                        gbest_routes = routes

            convergence_history.append(gbest_cost)
            convergence_elapsed_ms.append((time.perf_counter() - start_time) * 1000.0)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return evaluate_solution(
            routes=gbest_routes,
            scenario=scenario,
            weights=config.weights,
            algorithm_name=self.name,
            runtime_ms=elapsed_ms,
            convergence_history=convergence_history,
            convergence_elapsed_ms=convergence_elapsed_ms
        )
