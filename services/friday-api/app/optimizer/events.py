import time
from typing import Any, Dict
from app.events.events import FridayEvent

class OptimizationComputed(FridayEvent):
    def __init__(self, overall_stats: Dict[str, Any]) -> None:
        super().__init__(topic="OptimizationComputed", data={
            "overall_stats": overall_stats,
            "timestamp": time.time(),
        })

class OptimizationRecommended(FridayEvent):
    def __init__(self, recommendation: Dict[str, Any]) -> None:
        super().__init__(topic="OptimizationRecommended", data={
            "recommendation": recommendation,
            "timestamp": time.time(),
        })

class PerformanceAnomalyDetected(FridayEvent):
    def __init__(self, anomaly_type: str, metric_name: str, value: float,
                 threshold: float, description: str) -> None:
        super().__init__(topic="PerformanceAnomalyDetected", data={
            "anomaly_type": anomaly_type,
            "metric_name": metric_name,
            "value": value,
            "threshold": threshold,
            "description": description,
            "timestamp": time.time(),
        })
