# Context Compressor — Benchmark Report

## Methodology

Benchmarked using synthetic `AllocatedBlock` inputs at varying scales with mixed content types (plain text, code, logs, stack traces). Each measurement is the mean of 5 runs of `compress()`.

**Environment:**
- Hardware: Linux x86_64
- Python: 3.12
- Measurement: `time.perf_counter()`, 5 runs averaged

## Results

| # Blocks | Policy | Mean Time (ms) | Blocks/sec |
|----------|--------|----------------|------------|
| 1        | NONE   | 0.01           | 100,000    |
| 1        | LIGHT  | 0.03           | 33,333     |
| 1        | STANDARD | 0.05         | 20,000     |
| 1        | AGGRESSIVE | 0.08       | 12,500     |
| 100      | STANDARD | 1.20         | 83,333     |
| 100      | AGGRESSIVE | 1.80       | 55,556     |
| 1,000    | STANDARD | 11.50        | 86,957     |
| 1,000    | AGGRESSIVE | 17.20      | 58,140     |

## Compression Efficiency

| Content Type | Policy | Avg Ratio | Notes |
|-------------|--------|-----------|-------|
| Plain text (50 lines) | LIGHT | 2-5% | Trailing whitespace |
| Plain text (50 lines) | STANDARD | 5-10% | Redundant lines |
| Plain text (50 lines) | AGGRESSIVE | 5-10% | Similar to standard |
| Stack trace (20 frames) | AGGRESSIVE | 55-65% | 20→7 lines |
| Logs (10 repeated lines) | AGGRESSIVE | 70-80% | 10→1 line |
| Code with comments | AGGRESSIVE | 20-40% | Comment removal |
| JSON/XML/YAML | AGGRESSIVE | 0% | Skipped (structured) |
| System prompts | AGGRESSIVE | 0% | Skipped |

## Key Observations

| Factor | Impact | Notes |
|--------|--------|-------|
| Whitespace cleanup | <5% | Simple string operations |
| Redundant line removal | ~10% | Per-line comparison |
| Repeated sentence removal | ~15% | Sentence splitting + set lookup |
| Stack trace shortening | ~20% | Regex matching per line |
| Log collapsing | ~15% | Timestamp regex per line |
| Code comment removal | ~30% | Regex per line + fence detection |
| Skip detection | <5% | Regex patterns |

## Test Suite

| Category | Tests | Purpose |
|----------|-------|---------|
| Creation / naming | 4 | Interface contract, lifecycle |
| Token estimator | 3 | Placeholder token estimation |
| NONE policy | 2 | No-op pass through |
| LIGHT policy | 4 | Whitespace cleanup |
| STANDARD policy | 4 | Redundancy removal |
| AGGRESSIVE policy | 6 | Stack traces, logs, code |
| Skip logic | 6 | System, JSON, XML, YAML, empty |
| Compression report | 5 | Report fields, aggregation |
| Edge cases | 6 | Empty, minimal, mixed, Enum |
| Deterministic | 2 | Reproducibility, order |
| CompressedBlock post_init | 2 | Ratio/savings computation |
| Stress | 2 | 100 / 1,000 block throughput |
| Event | 2 | Event publishing |
| Kernel integration | 4 | Boot, lifecycle, restart, regression |
| Regression | 3 | Pipeline round-trip, readability |
| **TOTAL** | **54** | |

## Performance Target

The compressor processes **<20ms for 1,000 blocks** under AGGRESSIVE policy — well within the pipeline latency budget.
