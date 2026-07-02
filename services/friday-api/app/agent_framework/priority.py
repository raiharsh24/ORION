from dataclasses import dataclass


@dataclass
class PriorityFactors:
    urgency: float = 1.0
    dependency_count: int = 0
    resource_availability: float = 1.0
    estimated_runtime: float = 1.0
    mission_importance: float = 1.0


class PriorityEngine:
    def calculate(self, factors: PriorityFactors) -> float:
        urgency_score = factors.urgency * 0.30
        dep_score = (1.0 / (1.0 + factors.dependency_count)) * 0.20
        resource_score = factors.resource_availability * 0.20
        runtime_score = (1.0 / (1.0 + factors.estimated_runtime)) * 0.10
        mission_score = factors.mission_importance * 0.20
        return round(
            urgency_score + dep_score + resource_score + runtime_score + mission_score,
            2,
        )

    def update(self, current_priority: float, factors: PriorityFactors) -> float:
        new_priority = self.calculate(factors)
        return round((current_priority + new_priority) / 2, 2)
