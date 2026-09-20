import time
import numpy as np
from typing import List
from models import ProblemScenario, OptimizationConfig, OptimizationResult
from route_cache import get_route_matrix
from decoder import decode_random_keys
from fitness import build_edge_map, evaluate_solution
from optimizers.base import BaseOptimizer


class GAOptimizer(BaseOptimizer):
    def __init__(self):
        super().__init__(name="Genetic Algorithm (GA)")

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
        crossover_rate = 0.85
        mutation_rate = 0.15

        # Built once and reused for every candidate evaluation below - see
        # fitness.build_edge_map. Rebuilding it per candidate (pop_size *
        # max_iter times) was the dominant cost on real OpenStreetMap-scale
        # scenarios, since it scales with the road network's edge count.
        edge_map = build_edge_map(scenario)

        # Initialize population of continuous random key vectors in [0, 1]^num_jobs
        population = np.random.rand(pop_size, num_jobs)
        fitness_costs = np.full(pop_size, float('inf'))

        best_cost = float('inf')
        best_chrom = None
        best_routes = None

        convergence_history: List[float] = []
        convergence_elapsed_ms: List[float] = []

        # Evaluate initial population
        for i in range(pop_size):
            routes = decode_random_keys(population[i], scenario, dist_matrix, time_matrix, paths_dict)
            res = evaluate_solution(routes, scenario, config.weights, self.name, edge_map=edge_map)
            fitness_costs[i] = res.total_cost

            if res.total_cost < best_cost:
                best_cost = res.total_cost
                best_chrom = np.copy(population[i])
                best_routes = routes

        convergence_history.append(best_cost)
        convergence_elapsed_ms.append((time.perf_counter() - start_time) * 1000.0)

        for iteration in range(1, max_iter):
            new_population = []

            # Elitism: carry over best individual
            new_population.append(np.copy(best_chrom))

            while len(new_population) < pop_size:
                # Tournament Selection (k=3)
                idx1 = self._tournament_select(fitness_costs, k=3)
                idx2 = self._tournament_select(fitness_costs, k=3)

                parent1 = population[idx1]
                parent2 = population[idx2]

                # Crossover
                if np.random.rand() < crossover_rate:
                    child1, child2 = self._crossover(parent1, parent2)
                else:
                    child1, child2 = np.copy(parent1), np.copy(parent2)

                # Mutation
                child1 = self._mutate(child1, mutation_rate)
                child2 = self._mutate(child2, mutation_rate)

                new_population.append(child1)
                if len(new_population) < pop_size:
                    new_population.append(child2)

            population = np.array(new_population)

            # Evaluate new generation
            for i in range(pop_size):
                routes = decode_random_keys(population[i], scenario, dist_matrix, time_matrix, paths_dict)
                res = evaluate_solution(routes, scenario, config.weights, self.name, edge_map=edge_map)
                fitness_costs[i] = res.total_cost

                if res.total_cost < best_cost:
                    best_cost = res.total_cost
                    best_chrom = np.copy(population[i])
                    best_routes = routes

            convergence_history.append(best_cost)
            convergence_elapsed_ms.append((time.perf_counter() - start_time) * 1000.0)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return evaluate_solution(
            routes=best_routes,
            scenario=scenario,
            weights=config.weights,
            algorithm_name=self.name,
            runtime_ms=elapsed_ms,
            convergence_history=convergence_history,
            convergence_elapsed_ms=convergence_elapsed_ms,
            edge_map=edge_map
        )

    def _tournament_select(self, costs: np.ndarray, k: int = 3) -> int:
        candidates = np.random.choice(len(costs), size=k, replace=False)
        best_idx = candidates[0]
        for idx in candidates[1:]:
            if costs[idx] < costs[best_idx]:
                best_idx = idx
        return best_idx

    def _crossover(self, p1: np.ndarray, p2: np.ndarray):
        cut = np.random.randint(1, len(p1))
        c1 = np.concatenate([p1[:cut], p2[cut:]])
        c2 = np.concatenate([p2[:cut], p1[cut:]])
        return c1, c2

    def _mutate(self, chrom: np.ndarray, rate: float):
        mutated = np.copy(chrom)
        for i in range(len(chrom)):
            if np.random.rand() < rate:
                mutated[i] = np.random.rand()
        return mutated
