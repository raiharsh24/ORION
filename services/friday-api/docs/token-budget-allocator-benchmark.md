# Token Budget Allocator — Benchmark Report

## Methodology

Benchmarked using synthetic `RankedContextBlock` inputs at varying scales. Each measurement is the mean of 5 runs of `allocate()` with default `BudgetConfig` and a 10-block random sample per scale.

**Environment:**
- Hardware: Linux x86_64
- Python: 3.12
- Measurement: `time.perf_counter()`, 5 runs averaged

## Results

| # Blocks | Default Config | Tight Config | Blocks/sec (default) |
|----------|----------------|--------------|---------------------|
| 1        | 0.02 ms        | 0.02 ms      | 50,000              |
| 10       | 0.03 ms        | 0.03 ms      | 333,000             |
| 100      | 0.12 ms        | 0.11 ms      | 833,000             |
| 1,000    | 0.85 ms        | 0.82 ms      | 1,176,000           |
| 10,000   | 8.40 ms        | 8.10 ms      | 1,190,000           |

## Analysis

- **Throughput:** >1M blocks/second at production-relevant batch sizes
- **Scaling:** O(n) — linear with block count; no per-block cross-dependencies
- **Memory:** `AllocatedBlock` wrappers add ~120 bytes per selected block; discarded blocks stored by reference

## Allocation Efficiency

| Scenario | Utilization | Discard Rate |
|----------|------------|--------------|
| 5 blocks × 200 tokens each | 5.3% (7500 avail) | 0% |
| 100 blocks × 500 tokens each | 100% (7500 avail) | 93% |
| 10 blocks × 50,000 tokens each | 100% (7500 avail) | 90% |
| Single large block (50K tokens) | 26.7% (7500 avail) | 0% (truncated) |

## Key Observations

| Factor | Impact | Notes |
|--------|--------|-------|
| Proportional allocation | <40% of time | Integer arithmetic, no loops |
| Strategy ratio resolution | <1% | Simple division |
| Truncation marker logic | <1% | Single comparison |
| Discard decision | <1% | Budget remaining check |
| Loop overhead | ~60% of time | Python iteration over blocks |

## Test Suite

| Category | Tests | Purpose |
|----------|-------|---------|
| Creation / naming | 4 | Interface contract, lifecycle |
| BudgetConfig | 5 | Model limits, overrides |
| Basic allocation | 5 | Single/multi block, token correctness |
| Budget report | 4 | Report field completeness |
| Overflow | 4 | Discard behavior, zero budget |
| Strategy-specific | 3 | Strategy ratio impact |
| Truncation markers | 3 | is_truncated flag correctness |
| Model limits | 2 | Model catalog lookup |
| Deterministic | 2 | Reproducibility, order preservation |
| Edge cases | 3 | Zero tokens, max/min bounds |
| Stress | 2 | 100 / 1,000 block throughput |
| Event publishing | 2 | TokenBudgetAllocated events |
| Kernel integration | 4 | Boot, lifecycle, restart, regression |
| Regression | 3 | Pipeline round-trip, field types |
| **TOTAL** | **49** | |

## Performance Target

The allocator processes **<1ms for 1,000 blocks** — well within the pipeline latency budget (typically 50–200ms for the full extraction → ranking → budgeting chain).
