import asyncio
import time
import pytest
from unittest.mock import MagicMock, patch

from app.events.bus import EventBus
from app.events.events import FridayEvent
from app.optimizer.base import PipelineRunMetadata
from app.optimizer.statistics import RollingStats, PipelineStatisticsTracker
from app.optimizer.recommendations import RecommendationEngine, AnomalyDetector
from app.optimizer.optimizer import AdaptivePipelineOptimizer


@pytest.fixture
def event_bus():
    return EventBus()


def test_rolling_stats_calculations():
    stats = RollingStats()
    for v in range(1, 101):  # 1 to 100
        stats.add(float(v))
        
    metrics = stats.get_metrics()
    
    # overall mean should be 50.5
    assert metrics["overall"]["mean"] == 50.5
    # median should be 50.5
    assert metrics["overall"]["median"] == 50.5
    # p95 index is ceil(0.95 * 100) - 1 = 94. value is 95.0
    assert metrics["overall"]["p95"] == 95.0
    # p99 index is ceil(0.99 * 100) - 1 = 98. value is 99.0
    assert metrics["overall"]["p99"] == 99.0


@pytest.mark.anyio
async def test_optimizer_recommendations_rules(event_bus):
    optimizer = AdaptivePipelineOptimizer(event_bus=event_bus)
    await optimizer.start()
    
    # Record 15 runs to fill rolling queue history
    for i in range(15):
        run = PipelineRunMetadata(
            execution_id=f"exec_{i}",
            session_id="session_1",
            total_latency_ms=120.0,
            stage_latencies={"extraction": 80.0, "ranking": 10.0, "validation": 10.0, "compression": 10.0},
            extractor_latencies={"memory_extractor": 600.0}, # repeatedly high latency (> 500ms)
            cache_hit_ratio=0.85, # high cache hit ratio (> 0.8)
            token_utilization=0.45, # underutilized budget (< 0.5)
            context_reuse_ratio=0.85,
            incremental_update_ratio=0.0,
        )
        await optimizer.record_run(run)
        
    # Yield control to allow background tasks / async records to execute
    await asyncio.sleep(0.1)
    
    recs = optimizer._recommendations
    assert len(recs) > 0
    
    # Assert specific rules triggered
    rule_names = {r.rule_name for r in recs}
    assert "Slow Extractor Detected" in rule_names
    assert "High Cache Efficiency" in rule_names
    assert "Low Token Utilization" in rule_names
    assert "Underutilized Token Budget" in rule_names
    
    await optimizer.shutdown()


@pytest.mark.anyio
async def test_optimizer_anomaly_detection(event_bus):
    optimizer = AdaptivePipelineOptimizer(event_bus=event_bus)
    await optimizer.start()
    
    # Feed baseline runs
    for i in range(10):
        await optimizer.record_run(PipelineRunMetadata(
            execution_id=f"base_{i}",
            session_id="s1",
            total_latency_ms=50.0,
        ))
        
    await asyncio.sleep(0.05)
    
    # Spike latency run (Latency Spike)
    spike_run = PipelineRunMetadata(
        execution_id="spike_1",
        session_id="s1",
        total_latency_ms=300.0,  # 6x higher than average baseline
    )
    await optimizer.record_run(spike_run)
    
    # Timeout run (Extractor Timeout)
    timeout_run = PipelineRunMetadata(
        execution_id="timeout_1",
        session_id="s1",
        total_latency_ms=2000.0,
        is_timeout=True,
    )
    await optimizer.record_run(timeout_run)
    
    # Failure run (Pipeline Execution Failure)
    failed_run = PipelineRunMetadata(
        execution_id="fail_1",
        session_id="s1",
        total_latency_ms=10.0,
        status="failed",
        error_message="Unexpected extraction timeout",
    )
    await optimizer.record_run(failed_run)
    
    await asyncio.sleep(0.1)
    
    anomalies = optimizer._anomalies
    assert len(anomalies) >= 3
    
    types = {a.anomaly_type for a in anomalies}
    assert "Latency Spike" in types
    assert "Extractor Timeout" in types
    assert "Pipeline Execution Failure" in types
    
    await optimizer.shutdown()


@pytest.mark.anyio
async def test_event_driven_telemetry(event_bus):
    optimizer = AdaptivePipelineOptimizer(event_bus=event_bus)
    await optimizer.start()
    
    events_captured = []
    event_bus.subscribe("OptimizationComputed", lambda e: events_captured.append("computed"))
    event_bus.subscribe("OptimizationRecommended", lambda e: events_captured.append("recommended"))
    event_bus.subscribe("PerformanceAnomalyDetected", lambda e: events_captured.append("anomaly"))
    
    # 1. Fire ExtractorCompleted followed by StreamingCompleted
    await event_bus.publish(FridayEvent("ExtractorCompleted", {
        "execution_id": "test_exec_1",
        "extractor_name": "memory_extractor",
        "latency_ms": 600.0,
    }))
    
    await event_bus.publish(FridayEvent("StreamingCompleted", {
        "execution_id": "test_exec_1",
        "total_latency_ms": 700.0,
        "final_prompt_tokens": 800,
        "cache_hit_ratio": 0.9,
    }))
    
    # 2. Fire IncrementalUpdateCompleted
    await event_bus.publish(FridayEvent("IncrementalUpdateCompleted", {
        "execution_id": "test_exec_2",
        "reused_count": 8,
        "recomputed_count": 0,
        "latency_ms": 12.0,
    }))
    
    # 3. Fire PipelineFailed
    await event_bus.publish(FridayEvent("PipelineFailed", {
        "execution_id": "test_exec_3",
        "latency_ms": 150.0,
        "reason": "Model disconnected",
    }))
    
    # Yield control to allow event handlers and record tasks to finish
    await asyncio.sleep(0.3)
    
    assert len(optimizer._runs) == 3
    assert "computed" in events_captured
    assert "anomaly" in events_captured  # Memory extractor took 600ms, pipeline failed, etc.
    
    await optimizer.shutdown()


def test_reports_generation():
    tracker = PipelineStatisticsTracker()
    for i in range(15):
        tracker.record_run(PipelineRunMetadata(
            execution_id=f"run_{i}",
            session_id="s1",
            total_latency_ms=100.0,
            stage_latencies={"extraction": 60.0, "ranking": 10.0, "validation": 15.0, "assembly": 15.0},
            extractor_latencies={"memory_extractor": 60.0},
            cache_hit_ratio=0.7,
            token_utilization=0.8,
        ))
        
    optimizer = AdaptivePipelineOptimizer()
    optimizer._tracker = tracker
    optimizer._recommendations.append(MagicMock(rule_name="Slow Extractor", target="memory_extractor", action="demote", priority="HIGH", description="Memory is slow", timestamp=time.time()))
    
    bench = optimizer.generate_benchmark_report()
    perf = optimizer.generate_performance_report()
    
    assert "# Friday Intelligence Pipeline Benchmark Report" in bench
    assert "Stage Latency Analysis" in bench
    assert "Average Throughput" in bench
    
    assert "# Friday Intelligence Pipeline Performance Optimization Report" in perf
    assert "Optimization Recommendations" in perf


@pytest.mark.anyio
async def test_stress_concurrency(event_bus):
    optimizer = AdaptivePipelineOptimizer(event_bus=event_bus)
    await optimizer.start()
    
    async def simulate_runs(session):
        for i in range(20):
            await optimizer.record_run(PipelineRunMetadata(
                execution_id=f"{session}_{i}",
                session_id=session,
                total_latency_ms=50.0 + (i * 5.0),
            ))
            
    # Run 10 sessions concurrently
    await asyncio.gather(*(simulate_runs(f"sess_{j}") for j in range(10)))
    await asyncio.sleep(0.2)
    
    assert len(optimizer._runs) == 200
    assert optimizer._tracker.total_runs_count == 200
    
    await optimizer.shutdown()
