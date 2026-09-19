import time
import numpy as np
from typing import List
from models import ProblemScenario, OptimizationConfig, OptimizationResult
from problem_generator import compute_route_matrix
from decoder import decode_random_keys
from fitness import evaluate_solution
from optimizers.base import BaseOptimizer


class QPSOOptimizer(BaseOptimizer):
    def __init__(self):
        super().__init__(name="QPSO (Quantum-behaved PSO)")

    def optimize(
        self,
        scenario: ProblemScenario,
        config: OptimizationConfig
    ) -> OptimizationResult:
        start_time = time.perf_counter()
        np.random.seed(config.seed)

        dist_matrix, time_matrix, paths_dict = compute_route_matrix(scenario).as_tuple()
        num_jobs = len(scenario.jobs)

        if num_jobs == 0:
            return evaluate_solution([], scenario, config.weights, self.name, 0.0, [])

        pop_size = config.population_size
        max_iter = config.max_iterations

        # Contraction-Expansion coefficient limits
        alpha_start = 1.0
        alpha_end = 0.4

        # Initialize quantum particle positions X in [0, 1]^num_jobs
        X = np.random.rand(pop_size, num_jobs)

        pbest_pos = np.copy(X)
        pbest_cost = np.full(pop_size, float('inf'))

        gbest_pos = None
        gbest_cost = float('inf')
        gbest_routes = None

        convergence_history: List[float] = []
        convergence_elapsed_ms: List[float] = []

        # Initial evaluation
        for i in range(pop_size):
            routes = decode_random_keys(X[i], scenario, dist_matrix, time_matrix, paths_dict)
            res = evaluate_solution(routes, scenario, config.weights, self.name)
            pbest_cost[i] = res.total_cost

            if res.total_cost < gbest_cost:
                gbest_cost = res.total_cost
                gbest_pos = np.copy(X[i])
                gbest_routes = routes

        convergence_history.append(gbest_cost)
        convergence_elapsed_ms.append((time.perf_counter() - start_time) * 1000.0)

        for iteration in range(1, max_iter):
            # Linearly decreasing contraction-expansion coefficient alpha
            alpha = alpha_start - (alpha_start - alpha_end) * (iteration / max_iter)

            # 1. Compute Mean Best Position (mbest)
            mbest = np.mean(pbest_pos, axis=0)

            # 2. Update each particle position using quantum delta-potential wave function
            phi = np.random.rand(pop_size, num_jobs)
            # Local attractor p = phi * pbest + (1 - phi) * gbest
            p = phi * pbest_pos + (1.0 - phi) * gbest_pos

            u = np.random.rand(pop_size, num_jobs)
            u = np.clip(u, 1e-10, 1.0 - 1e-10)  # avoid log(0)
            ln_u_inv = np.log(1.0 / u)

            # Random sign (+1 or -1)
            signs = np.random.choice([-1.0, 1.0], size=(pop_size, num_jobs))

            # Quantum Position Update
            X = p + signs * alpha * np.abs(mbest - X) * ln_u_inv
            X = np.clip(X, 0.0, 1.0)

            # 3. Fitness Evaluation & Best State Updates
            for i in range(pop_size):
                routes = decode_random_keys(X[i], scenario, dist_matrix, time_matrix, paths_dict)
                res = evaluate_solution(routes, scenario, config.weights, self.name)

                if res.total_cost < pbest_cost[i]:
                    pbest_cost[i] = res.total_cost
                    pbest_pos[i] = np.copy(X[i])

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
