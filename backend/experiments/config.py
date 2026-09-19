"""Configuration objects for the Q-DFRO experiment framework.

Reuses the existing OptimizationConfig/ObjectiveWeights models from
`models.py` for solver parameters rather than re-inventing them - only the
scenario-generation parameters need a new, minimal container.
"""
from dataclasses import dataclass, asdict

from models import OptimizationConfig, ObjectiveWeights


@dataclass
class ScenarioSpec:
    num_nodes: int = 30
    num_jobs: int = 15
    num_vehicles: int = 3
    seed: int = 42

    def as_dict(self) -> dict:
        return asdict(self)


# Matches the live demo's default scenario (App.jsx) so experiment evidence
# and the interactive demo describe the same problem.
DEFAULT_SCENARIO = ScenarioSpec()

DEFAULT_SOLVER_CONFIG = OptimizationConfig(
    algorithm="qpso", population_size=40, max_iterations=100, seed=42,
    weights=ObjectiveWeights()
)

# A reduced solver budget used ONLY for the scalability sweep (E3), so a
# 4-algorithm x N-size sweep completes in a reasonable time. This must always
# be documented alongside E3 output and never compared directly against E1's
# costs, which use the full budget above - see docs/experiment_protocol.md.
E3_SOLVER_CONFIG = OptimizationConfig(
    algorithm="qpso", population_size=20, max_iterations=30, seed=42,
    weights=ObjectiveWeights()
)
