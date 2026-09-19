from abc import ABC, abstractmethod
from models import ProblemScenario, OptimizationConfig, OptimizationResult


class BaseOptimizer(ABC):
    """Common interface for all CVRP optimizers."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def optimize(
        self,
        scenario: ProblemScenario,
        config: OptimizationConfig
    ) -> OptimizationResult:
        """Solves the problem scenario and returns uniform OptimizationResult."""
        pass
