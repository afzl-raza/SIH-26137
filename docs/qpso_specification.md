# Q-DFRO — QPSO Specification

Extracted from [`Engineering.md`](../Engineering.md) §5 and §7. Documents the
exact QPSO variant implemented in `backend/optimizers/qpso.py` and the
continuous-to-discrete bridge a judge will ask about. If this ever diverges
from `qpso.py`, the code wins and this file must be corrected to match it —
never the other way around.

## Route representation (the QPSO ↔ VRP bridge)

A candidate solution is a vector of `num_jobs` continuous keys in `[0, 1]`,
one per job — not one per vehicle, and not a permutation.

**Decoding** (`decoder.decode_random_keys`), for job `i` with key `x_i`:

```
vehicle_idx  = min(num_vehicles - 1, floor(x_i * num_vehicles))
sequence_key = x_i * num_vehicles - vehicle_idx
```

- The integer part of `x_i * num_vehicles` selects **which vehicle** serves job `i`.
- The fractional part (`sequence_key`) determines **visit order** within that
  vehicle: jobs assigned to the same vehicle are sorted ascending by `sequence_key`.

This single continuous vector encodes both the vehicle-assignment decision and
the intra-route ordering decision simultaneously, letting QPSO/PSO/GA search
both dimensions of the VRP at once without a separate splitting heuristic.

Consecutive jobs (and depot↔first/last job) are joined using precomputed
shortest paths (`problem_generator.compute_route_matrix`) under the current
traffic state. So the optimizer decides *which jobs, in what order, for which
vehicle*; the graph router decides *how a vehicle physically gets from one
stop to the next*.

There is no separate repair/reject step — capacity/time violations are
surfaced as quadratic penalties (see `mathematical_model.md`) rather than
repaired or rejected.

## QPSO — exact mechanism implemented

Implemented in `optimizers/qpso.py`:

1. Initialize `pop_size` particles as `X ~ U(0,1)^num_jobs`.
2. Each iteration, compute the mean best position: `mbest = mean(pbest_pos)`
   across the population.
3. Local attractor per particle/dimension:
   `p = φ·pbest + (1−φ)·gbest`, `φ ~ U(0,1)`.
4. Quantum position update (delta-potential-well formulation):
   `X = p ± α·|mbest − X|·ln(1/u)`, `u ~ U(0,1)`, sign chosen uniformly at random.
5. `α` (contraction-expansion coefficient) decays linearly from `1.0` to `0.4`
   over `max_iterations`.
6. Positions are clipped back to `[0, 1]` after the update.
7. Decode → evaluate → update `pbest`/`gbest` → append `gbest_cost` to
   `convergence_history` → repeat.

This is the exact and only QPSO variant implemented — no other formulation is
used anywhere in the codebase.

## Correct terminology

QPSO is a **quantum-inspired** metaheuristic that runs entirely on classical
hardware. It does not use quantum computing, quantum hardware, or claim a
"quantum speedup." The correct framing for the paper/PPT/video is:

> "Quantum-inspired optimization implemented on classical hardware."

## Reproducibility

`QPSOOptimizer.optimize` seeds `numpy.random` from `config.seed` before any
random draw. Given the same scenario and config, the same seed always
produces the same result — verified empirically in
`experiments/E6_reproducibility/` (5 seeds, see `experiment_protocol.md`) and
by `backend/tests/test_experiments.py::test_e6_reproducibility_determinism_and_stats`.
