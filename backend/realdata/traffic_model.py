"""BPR-based simulated congestion, and the single edge-cost pipeline.

NOT YET IMPLEMENTED - this is Phase 9/10. The module exists now so the
package layout is settled; it is deliberately not re-exported from
`realdata/__init__.py`.

Contract agreed for Phases 9 and 10
-----------------------------------
This is a SIMULATION. Congestion here is modelled, not observed, and every
value it produces is labelled "Simulated Congestion (BPR)". It must never be
presented as a live traffic feed.

One authoritative pipeline, no competing congestion models:

    base_travel_time
        -> weather adjustment      (from realdata.weather, real observation)
        -> BPR congestion          (simulated, this module)
        -> current_travel_time     (what the optimizers consume)

The BPR volume-delay function itself already exists as
`qdfro_graph.weights.bpr_travel_time`:

    t(v) = t0 * (1 + alpha * (v / c)^beta)

It will be reused rather than reimplemented, so there is exactly one BPR in
the codebase. alpha, beta, the capacity assumptions and the volume
assumptions per simulation mode (NORMAL / MODERATE / SEVERE / INCIDENT) will
be declared as named, documented constants - no unexplained magic numbers.

Planned output per edge: traffic_mode, traffic_source, traffic_factor,
current_travel_time, timestamp. The objective function in `fitness.py` is not
touched: this module only sets edge costs.
"""
from __future__ import annotations


def apply_traffic_model(*args, **kwargs):
    raise NotImplementedError(
        "The BPR traffic model is implemented in Phase 9/10. "
        "It will reuse qdfro_graph.weights.bpr_travel_time."
    )
