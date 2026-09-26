import time
import numpy as np
from typing import List
from models import ProblemScenario, OptimizationConfig, OptimizationResult
from route_cache import get_route_matrix
from decoder import decode_random_keys, chromosome_from_routes
from fitness import build_edge_map, evaluate_solution
from optimizers.base import BaseOptimizer
from optimizers.local_search import local_search_refine


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

        dist_matrix, time_matrix, paths_dict = get_route_matrix(scenario).as_tuple()
        num_jobs = len(scenario.jobs)

        if num_jobs == 0:
            label = self.name + (" + Local Search" if config.use_local_search else " (ablation, no local search)")
            return evaluate_solution([], scenario, config.weights, label, 0.0, [])

        pop_size = config.population_size
        max_iter = config.max_iterations

        # Built once and reused for every candidate evaluation below - see
        # fitness.build_edge_map. Rebuilding it per candidate (pop_size *
        # max_iter times) was the dominant cost on real OpenStreetMap-scale
        # scenarios, since it scales with the road network's edge count.
        edge_map = build_edge_map(scenario)

        # Contraction-Expansion coefficient limits
        alpha_start = 1.0
        alpha_end = 0.4

        # Cap on the ln(1/u) quantum-jump excursion term. Uncapped, a
        # vanilla QPSO's jump grows without bound as u -> 0, and in
        # higher-dimensional chromosomes (one gene per job) the odds that
        # at least one dimension draws a huge value on a given iteration
        # rise quickly - repeatedly scattering an otherwise-good solution
        # right when the search should be exploiting structure. This is
        # measured, not theoretical: plain QPSO (no cap, no local search)
        # loses to Greedy at 30+ jobs and is frequently infeasible.
        # Scaled down as num_jobs grows, same shape as the cap used
        # elsewhere for this exact problem.
        max_jump_factor = max(0.3, 3.0 / (1.0 + num_jobs / 20.0))

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
            res = evaluate_solution(routes, scenario, config.weights, self.name, edge_map=edge_map)
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
            ln_u_inv = np.minimum(np.log(1.0 / u), max_jump_factor)

            # Random sign (+1 or -1)
            signs = np.random.choice([-1.0, 1.0], size=(pop_size, num_jobs))

            # Quantum Position Update
            X = p + signs * alpha * np.abs(mbest - X) * ln_u_inv
            X = np.clip(X, 0.0, 1.0)

            # 3. Fitness Evaluation & Best State Updates
            for i in range(pop_size):
                routes = decode_random_keys(X[i], scenario, dist_matrix, time_matrix, paths_dict)
                res = evaluate_solution(routes, scenario, config.weights, self.name, edge_map=edge_map)

                if res.total_cost < pbest_cost[i]:
                    pbest_cost[i] = res.total_cost
                    pbest_pos[i] = np.copy(X[i])

                    if res.total_cost < gbest_cost:
                        gbest_cost = res.total_cost
                        gbest_pos = np.copy(X[i])
                        gbest_routes = routes

            # 4. Periodic 2-opt/or-opt local search on the swarm's global
            # best, reinjected as a real particle position (Lamarckian) -
            # not just used to report a better fitness. This is what
            # closes the gap against Greedy at larger job counts; without
            # it, the jump-cap alone is not sufficient (measured).
            #
            # A single refinement's own cost scales with job count (more
            # jobs -> longer per-vehicle routes -> more candidate moves to
            # scan), so the interval is widened for large scenarios to keep
            # the TOTAL number of refinements from also growing with
            # scenario size on top of that. Measured, honestly: this keeps
            # the demo's default/typical sizes (num_jobs <= 30, where
            # effective_interval == the requested one) fast and clearly
            # ahead of Greedy; at very large scenarios (~100 jobs) fewer
            # refinements run, runtime stays in the tens-of-seconds range
            # rather than ~70s uncapped, and the quality margin over Greedy
            # narrows since there is less refinement to close the gap. That
            # tradeoff is accepted rather than chased further with a more
            # elaborate search (e.g. neighbour-list-restricted or-opt) -
            # the reported regression this fix targets is at 30-50 jobs,
            # not 100.
            #
            # Capped at max_iter // 2 so local search always gets at least
            # one real chance to run within whatever budget it's given -
            # widening the interval on a large scenario is only useful if it
            # still fires; a reduced-iteration sweep (E3's scalability
            # benchmark uses 30) with a naively-widened interval could push
            # it past max_iterations entirely, silently making
            # use_local_search=True behave identically to False. Caught by
            # exactly that happening in a real regenerated E3 run.
            effective_interval = min(
                max(config.local_search_interval, num_jobs // 3),
                max(1, max_iter // 2)
            )
            if config.use_local_search and iteration % effective_interval == 0:
                refined_routes = local_search_refine(
                    scenario, gbest_routes, dist_matrix, time_matrix, paths_dict,
                    config.weights, edge_map=edge_map
                )
                refined_res = evaluate_solution(refined_routes, scenario, config.weights, self.name, edge_map=edge_map)
                if refined_res.total_cost < gbest_cost:
                    gbest_cost = refined_res.total_cost
                    gbest_routes = refined_routes
                    gbest_pos = chromosome_from_routes(refined_routes, scenario)
                    # The swarm's mean-best position should reflect this
                    # improvement too, not just gbest, or the next
                    # iteration's local attractor (`p`) pulls particles back
                    # toward the old, worse position.
                    best_particle_idx = int(np.argmin(pbest_cost))
                    pbest_cost[best_particle_idx] = gbest_cost
                    pbest_pos[best_particle_idx] = gbest_pos

            convergence_history.append(gbest_cost)
            convergence_elapsed_ms.append((time.perf_counter() - start_time) * 1000.0)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        # Plain QPSO and QPSO+local-search share this one class (config
        # toggles the behavior), so the reported label must say which ran -
        # otherwise a benchmark table showing both looks like the same
        # algorithm produced two different numbers.
        label = self.name + (" + Local Search" if config.use_local_search else " (ablation, no local search)")

        return evaluate_solution(
            routes=gbest_routes,
            scenario=scenario,
            weights=config.weights,
            algorithm_name=label,
            runtime_ms=elapsed_ms,
            convergence_history=convergence_history,
            convergence_elapsed_ms=convergence_elapsed_ms,
            edge_map=edge_map
        )
