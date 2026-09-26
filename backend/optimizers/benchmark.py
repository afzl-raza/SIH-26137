import hashlib
import os
import threading
from collections import OrderedDict
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from typing import Dict

from models import ProblemScenario, OptimizationConfig, BenchmarkResult, OptimizationResult
from problem_generator import RouteMatrix
from route_cache import ROUTE_MATRIX_CACHE, get_route_matrix
from optimizers.greedy import GreedyOptimizer
from optimizers.pso import PSOOptimizer
from optimizers.ga import GAOptimizer
from optimizers.qpso import QPSOOptimizer

_OPTIMIZERS = {
    "pso": PSOOptimizer,
    "ga": GAOptimizer,
    "qpso": QPSOOptimizer,
}

# The three population-based optimizers are CPU-bound pure Python/NumPy, so
# threads would serialise on the GIL. They run in separate processes
# instead. The pool is created once and kept alive: on Windows every new
# process re-imports NumPy/NetworkX (~1s), which would otherwise be paid on
# every benchmark call. Each worker keeps its own route-matrix cache, so a
# repeat benchmark on the same scenario hits it there too.
_pool = None
_pool_lock = threading.Lock()


def _get_pool():
    global _pool
    with _pool_lock:
        if _pool is None:
            # One BLAS thread per worker: three workers each spinning up a
            # full-width NumPy thread pool would oversubscribe the CPU and
            # slow all three down. Workers read this at spawn time; the
            # parent's already-initialised NumPy is unaffected.
            for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
                os.environ[var] = "1"
            workers = max(1, min(len(_OPTIMIZERS), (os.cpu_count() or 1) - 1))
            _pool = ProcessPoolExecutor(max_workers=workers)
        return _pool


def _noop() -> None:
    return None


def warm_pool() -> None:
    """Spawn the worker processes ahead of the first benchmark, so that call
    doesn't pay the process start-up / NumPy import cost."""
    pool = _get_pool()
    for f in [pool.submit(_noop) for _ in _OPTIMIZERS]:
        f.result()


# Result cache. Every optimizer is seeded from config.seed, so the same
# scenario content + the same config always produces the same results - a
# repeat benchmark can be served without recomputing. The key hashes the
# FULL scenario (graph, edge costs, every condition multiplier, jobs,
# vehicles) and the full config, so any traffic/weather/incident change or
# solver setting change is a different key: a stale result can't be served.
# Cached entries keep the runtime_ms genuinely measured when they were
# computed; the response's `cached` flag says the numbers weren't re-run.
_CACHE_MAX_ENTRIES = 16
_cache: "OrderedDict[str, Dict[str, OptimizationResult]]" = OrderedDict()
_cache_lock = threading.Lock()


def clear_result_cache() -> None:
    with _cache_lock:
        _cache.clear()


def _cache_key(scenario: ProblemScenario, config: OptimizationConfig) -> str:
    h = hashlib.sha256()
    h.update(scenario.model_dump_json().encode())
    h.update(b"|")
    h.update(config.model_dump_json().encode())
    return h.hexdigest()


def _reset_pool():
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.shutdown(wait=False, cancel_futures=True)
        _pool = None


# Route-matrix builds that happened inside worker processes during the most
# recent benchmark. Should always be 0: workers are handed the matrix the
# parent built. Exposed so the "one build per benchmark" guarantee stays
# testable now that the optimizers run in other processes.
LAST_WORKER_ROUTE_MATRIX_BUILDS = 0


def _run_one(name: str, scenario: ProblemScenario, config: OptimizationConfig, matrix: RouteMatrix):
    # Top-level so it can be pickled for a worker process.
    builds_before = ROUTE_MATRIX_CACHE.builds
    ROUTE_MATRIX_CACHE.seed(scenario, matrix)
    result = _OPTIMIZERS[name]().optimize(scenario, config)
    return result, ROUTE_MATRIX_CACHE.builds - builds_before


def run_benchmark(
    scenario: ProblemScenario,
    config: OptimizationConfig
) -> BenchmarkResult:
    """
    Executes all available optimizers (Greedy, Classical PSO, GA, QPSO) on the EXACT same
    problem scenario and parameters, collecting actual experimental results.

    PSO, GA and QPSO run concurrently in worker processes. Every optimizer is
    seeded from `config.seed` and receives its own copy of the same scenario,
    so the results are identical to a sequential run - only the wall-clock
    wait changes. Each algorithm's reported runtime_ms is still measured
    inside its own optimize() call.
    """
    key = _cache_key(scenario, config)
    with _cache_lock:
        hit = _cache.get(key)
        if hit is not None:
            _cache.move_to_end(key)
    if hit is not None:
        return BenchmarkResult(scenario_seed=scenario.seed, results=hit, cached=True)

    global LAST_WORKER_ROUTE_MATRIX_BUILDS
    results: Dict[str, OptimizationResult] = {}

    # The one route-matrix build for this benchmark happens here, in the
    # parent; every optimizer (in-process or in a worker) reuses it.
    matrix = get_route_matrix(scenario)

    # Greedy is a single construction pass (milliseconds) - not worth a
    # process round-trip.
    results["greedy"] = GreedyOptimizer().optimize(scenario, config)

    worker_builds = 0
    try:
        pool = _get_pool()
        futures = {name: pool.submit(_run_one, name, scenario, config, matrix) for name in _OPTIMIZERS}
        for name, future in futures.items():
            results[name], builds = future.result()
            worker_builds += builds
    except BrokenProcessPool:
        # A dead worker must not fail the request - fall back to the
        # original sequential path and rebuild the pool next time.
        _reset_pool()
        for name in _OPTIMIZERS:
            results[name], builds = _run_one(name, scenario, config, matrix)
            worker_builds += builds
    LAST_WORKER_ROUTE_MATRIX_BUILDS = worker_builds

    ordered = {k: results[k] for k in ("greedy", "pso", "ga", "qpso")}
    with _cache_lock:
        _cache[key] = ordered
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)

    return BenchmarkResult(scenario_seed=scenario.seed, results=ordered)
