# Friday Intelligence Pipeline Performance Optimization Report

Generated at: 2026-06-30 11:02:24

## Telemetry Summary
- **Total Monitored Operations**: 150
- **Average Execution Latency**: 252.96 ms
- **p95 Latency Bound**: 276.03 ms
- **Standard Deviation**: 73.92 ms

## Detected Anomalies (3)
| Anomaly Type | Metric Affected | Value Recorded | Threshold | Description | Timestamp |
|---|---|---|---|---|---|
| Pipeline Execution Failure | status | 0.0 | 1.0 | Pipeline aborted due to unexpected runtime error: Connection reset by peer | 11:02:23 |
| Latency Spike | total_latency_ms | 1131.2 | 541.9 | Pipeline run total latency spiked to 1131.2ms (threshold=541.9ms, mean=256.8ms). | 11:02:23 |
| Extractor Timeout | is_timeout | 1.0 | 0.5 | An active extractor failed to respond within the configured deadline limit. | 11:02:23 |

## Optimization Recommendations (5)
| Rule Identifier | Targeted Module | Action | Priority | Recommendation | Timestamp |
|---|---|---|---|---|---|
| Low Token Utilization | context_compressor | disable_compression_passes | LOW | Token budget is consistently underutilized (mean=20.1%). Recommend disabling expensive compression passes to save CPU/latency. | 11:02:23 |
| Underutilized Token Budget | token_allocator | increase_retrieval_budget | MEDIUM | Token budget is consistently underused (mean=20.1%). Recommend increasing retrieval extraction depth budget limits. | 11:02:23 |
| Redundant Validation | context_validator | lightweight_validation | LOW | Context validator never filters or removes block items. Recommend switching to lightweight validation mode. | 11:02:23 |
| Stable Ranking Orders | context_ranker | reuse_ranking | MEDIUM | Ranker consistently produces identical relative orderings. Recommend reusing ranking outcomes to bypass sorting. | 11:02:23 |
| High Budget Pressure | token_allocator | reduce_extraction_depth | HIGH | High token budget pressure (mean=30.8%) or timeouts detected. Recommend reducing extraction depth. | 11:02:23 |
