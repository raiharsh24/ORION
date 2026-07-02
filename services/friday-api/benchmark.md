# Friday Dynamic Pipeline Planner Benchmark Report

Generated at: 2026-06-30 11:08:34

## Overall Subsystem Statistics
- **Total Plans Created**: 100
- **Successful Runs**: 100%
- **Mean Planning Latency**: 8.039 ms
- **Median Planning Latency**: 7.637 ms
- **p95 Planning Latency**: 10.451 ms
- **p99 Planning Latency**: 14.471 ms

## Heuristic Rule Trigger Frequencies
- **Math Query Rule**: 24.0%
- **Desktop Query Rule**: 26.0%
- **Mission Query Rule**: 25.0%
- **Snapshot Warm-Start Rule (Incremental)**: 25.0%

## Resource Estimation Accuracy
| Metric | Planned Mean | Actual Mean | Accuracy |
|---|---|---|---|
| Pipeline Latency (ms) | 134.5 ms | 132.8 ms | 98.7% |
| Token Budget (tokens) | 385.0 | 378.2 | 98.2% |
| Cache Probability (%) | 37.5% | 36.2% | 96.5% |

## Telemetry Metrics
- **Mean Accuracy**: 99.2%
- **Planned Stages Count**: 6.2 stages/run
- **Skipped Stages Count**: 2.8 stages/run
- **Overhead Ratio**: 53.595% of total execution budget
