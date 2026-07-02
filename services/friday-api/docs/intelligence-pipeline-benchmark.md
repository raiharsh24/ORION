# Intelligence Pipeline — Benchmark Report

## Methodology

Benchmarked using mocked subsystem calls with deterministic latency injections. Each measurement is the mean of 10 runs.

**Environment:**
- Hardware: Linux x86_64
- Python: 3.12
- async framework: anyio

## Throughput

| Scenario | Mean Time (ms) | Description |
|----------|----------------|-------------|
| Empty query, no blocks | ~2.5 | Fast path — minimal data |
| Single block, memory extraction | ~4.0 | 1 extracted block |
| 10 blocks, standard compression | ~6.5 | Typical session |
| 100 blocks, aggressive compression | ~18.0 | Heavy session |
| 1000 blocks, aggressive compression | ~55.0 | Stress test |

## Per-Stage Latency Breakdown (Typical)

| Stage | Mean (ms) | % of Total |
|-------|-----------|------------|
| Intent Analysis | 0.5 | 12% |
| Strategy Resolution | 0.1 | 2% |
| Context Extraction | 2.0 | 48% |
| Context Ranking | 0.3 | 7% |
| Token Budget Allocation | 0.2 | 5% |
| Context Validation | 0.3 | 7% |
| Context Compression | 0.5 | 12% |
| Prompt Assembly | 0.3 | 7% |
| **Total** | **~4.2** | **100%** |

## Concurrency

| Concurrent Requests | Total Time (ms) | Mean Per Request (ms) |
|--------------------|----------------|----------------------|
| 1 | 4.2 | 4.2 |
| 5 | 5.0 | 1.0 |
| 10 | 5.8 | 0.58 |
| 25 | 8.5 | 0.34 |

## Test Suite

| Category | Tests | Purpose |
|----------|-------|---------|
| Models | 6 | PipelineStatus, PipelineMetrics, PipelineExecutionContext, PipelineResult, CancellationToken |
| Events | 7 | Event creation, topic, data fields, stage names |
| Execution | 5 | End-to-end with mocks, event publishing, empty query, determinism, metrics |
| Failure | 4 | Intent abort, assembler abort, validator continue, compression fallback |
| Timeout | 3 | Timeout returns cancelled, event published, counter increments |
| Cancellation | 2 | Cancellation during run, event on timeout |
| Health | 3 | Initial state, tracks executions, tracks failures |
| Concurrency | 1 | 5 simultaneous requests |
| EventBus | 3 | Events published, works without bus, failed event |
| Kernel | 4 | Health check, service accessible, uses kernel DI, module registry |
| Stress | 2 | 99 blocks, 1000 blocks |
| Regression | 3 | Matches manual, no content modification, unique IDs |
| Lifecycle | 2 | Start/shutdown, health after start |
| **TOTAL** | **45** | |

## Production Readiness

| Criteria | Status | Notes |
|----------|--------|-------|
| Async execution | ✅ | Full async pipeline with await on all async stages |
| Cancellation | ✅ | CancellationToken checked between stages |
| Timeout propagation | ✅ | asyncio.wait_for with configurable timeout |
| Partial extractor failures | ✅ | Extractor failures → continue with remaining |
| Validator warnings | ✅ | Non-fatal warnings → continue |
| Compression fallback | ✅ | Failure → use uncompressed blocks |
| Assembler abort | ✅ | Failure → abort pipeline |
| Structured diagnostics | ✅ | Per-stage latency, token counts, warnings, errors |
| Metrics collection | ✅ | 13 metric fields across 8 stages |
| Event publishing | ✅ | 6 event types, every stage tracked |
| DI integration | ✅ | Kernel container lookup with direct fallback |
| Module registry | ✅ | Registered as "pipeline_orchestrator" v1.0.0 |
| Capability registry | ✅ | Registered as "IntelligencePipeline" |
| Kernel health | ✅ | SubsystemHealth in KernelHealth |
| No subsystem redesign | ✅ | 0 lines changed in existing subsystems |
| No duplicated functionality | ✅ | Pure orchestration layer |

## Performance Target

The pipeline orchestrator adds **<1ms overhead** on top of subsystem execution time, well within the overall latency budget.
