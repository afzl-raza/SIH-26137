"""
Memetic QPSO: QPSO + greedy warm start + bounded quantum jump + local search.

Drop-in alongside optimizers/qpso.py. Uses the SAME decoder and the SAME
fitness.evaluate_solution for the final reported result, so the benchmark
stays fair. Local search uses a fast cost model that reproduces
evaluate_solution's formula from the route matrix (legs + service time +
congestion along each shortest path + normalized quadratic penalty,
including the CVRPTW lateness term), with timing computed by the same
schedule.simulate_route every other optimizer and fitness.py use - so this
fast model can never silently diverge from the real evaluator's numbers.
"""
import time
import numpy as np
from typing import List, Dict, Tuple
from models import ProblemScenario, OptimizationConfig, OptimizationResult
from route_cache import get_route_matrix
from decoder import decode_random_keys
from fitness import build_edge_map, evaluate_solution
from schedule import simulate_route
from optimizers.base import BaseOptimizer
from optimizers.greedy import GreedyOptimizer


class MemeticQPSOOptimizer(BaseOptimizer):
    def __init__(self, ls_interval: int = 10, penalty_scale: float = 1.0):
        super().__init__(name="QPSO + Local Search (Memetic)")
        self.ls_interval = ls_interval
        self.penalty_scale = penalty_scale

    # ---------- fast cost model (mirrors fitness.evaluate_solution) ----------
    def _prepare(self, scenario, dist_m, time_m, paths, edge_map, weights):
        self.S = scenario
        self.w = weights
        self.depot = scenario.depot_node_id
        self.jobs = scenario.jobs
        self.job_node = [j.node_id for j in self.jobs]
        self.job_dem = [j.demand for j in self.jobs]
        self.job_svc = [j.service_time for j in self.jobs]
        self.veh = scenario.vehicles
        self.dist_m, self.time_m = dist_m, time_m
        # simulate_route wants a job-id -> Job lookup; `route` lists below are
        # positions into self.jobs (see _keys_to_routes), so position doubles
        # as the "job id" key here - simulate_route never reads job.id itself.
        self.jobs_by_pos = {i: j for i, j in enumerate(self.jobs)}
        nodes = set(self.job_node) | {self.depot}
        self.cong: Dict[Tuple[int, int], float] = {}
        for a in nodes:
            for b in nodes:
                p = paths.get((a, b), [a, b])
                c = 0.0
                for u, v in zip(p[:-1], p[1:]):
                    e = edge_map.get((u, v))
                    if e and e.traffic_factor > 1.0:
                        c += (e.traffic_factor - 1.0) * e.base_travel_time
                self.cong[(a, b)] = c

    def _route_cost(self, v_idx: int, route: List[int]) -> float:
        w = self.w
        v = self.veh[v_idx]

        # Distance, congestion and demand: schedule.simulate_route only owns
        # timing (mirroring decoder.py/greedy.py), so those stay a direct sum.
        cur = self.depot
        d = c = dem = 0.0
        for j in route:
            n = self.job_node[j]
            d += self.dist_m[cur, n]
            c += self.cong[(cur, n)]
            dem += self.job_dem[j]
            cur = n
        d += self.dist_m[cur, self.depot]
        c += self.cong[(cur, self.depot)]

        # Timing, including wait/lateness - the one shared timing function.
        sched = simulate_route(route, v, self.depot, self.time_m, self.jobs_by_pos)
        t = sched.travel_time

        pen = 0.0
        cap_ex = max(0.0, dem - v.capacity)
        t_ex = max(0.0, t - v.max_route_time)
        pw = w.penalty_weight * self.penalty_scale
        if cap_ex > 0:
            pen += pw * (cap_ex / max(v.capacity, 1e-9)) ** 2 + pw * 0.05
        if t_ex > 0:
            pen += pw * (t_ex / max(v.max_route_time, 1e-9)) ** 2 + pw * 0.05
        # Lateness (CVRPTW) - mirrors fitness.py's lateness penalty exactly:
        # normalized quadratic term plus a fixed penalty per late job.
        if sched.lateness > 0:
            pen += pw * (sched.lateness / max(v.max_route_time, 1e-9)) ** 2
            pen += pw * 0.05 * sched.late_jobs
        return w.alpha * t + w.beta * d + w.gamma * c + pen

    # ---------- keys <-> routes ----------
    def _keys_to_routes(self, keys):
        nv = len(self.veh)
        buckets = [[] for _ in range(nv)]
        for j, k in enumerate(keys):
            v = min(nv - 1, int(k * nv))
            buckets[v].append((k * nv - v, j))
        return [[j for _, j in sorted(b)] for b in buckets]

    def _routes_to_keys(self, routes):
        nv = len(self.veh)
        keys = np.zeros(len(self.jobs))
        for v, r in enumerate(routes):
            for rank, j in enumerate(r):
                keys[j] = (v + (rank + 0.5) / (len(r) + 1)) / nv
        return np.clip(keys, 0.0, 1.0 - 1e-9)

    # ---------- local search: 2-opt, relocate, swap (first improvement) ----------
    def _local_search(self, routes, max_rounds=3):
        routes = [list(r) for r in routes]
        costs = [self._route_cost(v, r) for v, r in enumerate(routes)]
        for _ in range(max_rounds):
            improved = False
            # 2-opt intra-route
            for v, r in enumerate(routes):
                n = len(r)
                for i in range(n - 1):
                    for k in range(i + 1, n):
                        cand = r[:i] + r[i:k + 1][::-1] + r[k + 1:]
                        cc = self._route_cost(v, cand)
                        if cc < costs[v] - 1e-9:
                            routes[v], costs[v], r = cand, cc, cand
                            improved = True
            # relocate inter/intra
            for a in range(len(routes)):
                i = 0
                while i < len(routes[a]):
                    job = routes[a][i]
                    ra = routes[a][:i] + routes[a][i + 1:]
                    ca = self._route_cost(a, ra)
                    best = (0.0, None, None)
                    for b in range(len(routes)):
                        base = ra if b == a else routes[b]
                        for pos in range(len(base) + 1):
                            cand = base[:pos] + [job] + base[pos:]
                            cb = self._route_cost(b, cand)
                            delta = (cb - costs[a]) if b == a else (ca + cb - costs[a] - costs[b])
                            if delta < best[0] - 1e-9:
                                best = (delta, b, pos)
                    if best[1] is not None:
                        b, pos = best[1], best[2]
                        if b == a:
                            routes[a] = ra[:pos] + [job] + ra[pos:]
                            costs[a] = self._route_cost(a, routes[a])
                        else:
                            routes[a] = ra
                            routes[b] = routes[b][:pos] + [job] + routes[b][pos:]
                            costs[a] = ca
                            costs[b] = self._route_cost(b, routes[b])
                        improved = True
                    else:
                        i += 1
            # swap inter-route
            for a in range(len(routes)):
                for b in range(a + 1, len(routes)):
                    for i in range(len(routes[a])):
                        for k in range(len(routes[b])):
                            ra, rb = list(routes[a]), list(routes[b])
                            ra[i], rb[k] = rb[k], ra[i]
                            ca, cb = self._route_cost(a, ra), self._route_cost(b, rb)
                            if ca + cb < costs[a] + costs[b] - 1e-9:
                                routes[a], routes[b], costs[a], costs[b] = ra, rb, ca, cb
                                improved = True
            if not improved:
                break
        return routes, sum(costs)

    def optimize(self, scenario: ProblemScenario, config: OptimizationConfig) -> OptimizationResult:
        start = time.perf_counter()
        rng = np.random.default_rng(config.seed)
        dist_m, time_m, paths = get_route_matrix(scenario).as_tuple()
        m = len(scenario.jobs)
        edge_map = build_edge_map(scenario)
        if m == 0:
            return evaluate_solution([], scenario, config.weights, self.name, 0.0, [])
        self._prepare(scenario, dist_m, time_m, paths, edge_map, config.weights)
        job_index = {j.id: i for i, j in enumerate(scenario.jobs)}

        def fit(keys):
            return sum(self._route_cost(v, r) for v, r in enumerate(self._keys_to_routes(keys)))

        n, T = config.population_size, config.max_iterations
        X = rng.random((n, m))
        # Warm start: greedy solution (polished) injected as one particle
        g = GreedyOptimizer().optimize(scenario, config)
        g_routes = [[job_index[j] for j in r.job_ids] for r in g.routes]
        g_routes, _ = self._local_search(g_routes)
        X[0] = self._routes_to_keys(g_routes)

        pbest = X.copy()
        pcost = np.array([fit(x) for x in X])
        gi = int(np.argmin(pcost))
        gbest, gcost = pbest[gi].copy(), pcost[gi]
        history, elapsed = [gcost], [(time.perf_counter() - start) * 1000]
        jump_cap = max(0.3, 3.0 / (1 + m / 20.0))  # bounded ln(1/u)

        for it in range(1, T):
            alpha = 1.0 - 0.6 * it / T
            mbest = pbest.mean(axis=0)
            phi = rng.random((n, m))
            p = phi * pbest + (1 - phi) * gbest
            u = np.clip(rng.random((n, m)), 1e-10, 1 - 1e-10)
            jump = np.minimum(np.log(1 / u), jump_cap)
            sign = np.where(rng.random((n, m)) < 0.5, -1.0, 1.0)
            X = np.clip(p + sign * alpha * np.abs(mbest - X) * jump, 0.0, 1 - 1e-9)
            for i in range(n):
                c = fit(X[i])
                if c < pcost[i]:
                    pcost[i], pbest[i] = c, X[i].copy()
                    if c < gcost:
                        gcost, gbest = c, X[i].copy()
            if it % self.ls_interval == 0:
                r, c = self._local_search(self._keys_to_routes(gbest))
                if c < gcost - 1e-9:
                    gcost, gbest = c, self._routes_to_keys(r)
                    w = int(np.argmax(pcost))
                    pbest[w], pcost[w], X[w] = gbest.copy(), gcost, gbest.copy()
            history.append(gcost)
            elapsed.append((time.perf_counter() - start) * 1000)

        r, c = self._local_search(self._keys_to_routes(gbest), max_rounds=5)
        if c < gcost:
            gbest = self._routes_to_keys(r)
        routes = decode_random_keys(gbest, scenario, dist_m, time_m, paths)
        return evaluate_solution(routes, scenario, config.weights, self.name,
                                 (time.perf_counter() - start) * 1000, history, elapsed, edge_map)
