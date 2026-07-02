# Tool Selection Engine — Benchmark

## Test Suite

- **Test file:** `tests/test_tool_selection.py`
- **Total tests:** 43
- **Run time:** ~1.1s

### Test Categories

| Category         | Count | Description                                   |
|------------------|-------|-----------------------------------------------|
| Model tests      | 4     | Context defaults, result properties, empty    |
| Rules tests      | 8     | Health, permission, deps, category, intent    |
| Scoring tests    | 8     | Weight computation, optimizer boost/penalty   |
| Selection tests  | 8     | Category filter, permissions, latency, dedup  |
| Fallback tests   | 3     | Unhealthy fallback, event, no alternative     |
| Dependency tests | 2     | Satisfied vs missing dependencies             |
| Event tests      | 3     | Started/Completed/ToolSelected events         |
| Health tests     | 2     | Initial and post-selection health             |
| Integration      | 4     | Multi-category, optimizer, metadata, pipeline |

### Test Results

```
43 passed in 1.12s
```

### Key Test Scenarios

- **Selection respects categories:** Only tools in requested categories are returned.
- **Unhealthy tools excluded:** Tools with `error` or `unavailable` health are filtered.
- **Permissions enforced:** USER cannot see ADMIN/SYSTEM tools; ADMIN can see USER and ADMIN.
- **Lower latency preferred:** When capability is equivalent, faster tools score higher.
- **No duplicates:** No tool ID appears twice in the result.
- **Dependencies included:** Required dependencies are automatically added to the selection.
- **Missing deps skip tool:** A tool with an unsatisfied required dependency is rejected.
- **Fallback on failure:** When primary fails (missing dep), a healthy alternative is chosen.
- **Events published:** All 4 event types are published during selection.
- **No event bus crash:** Registry functions without EventBus gracefully.

## Full Regression

**991 tests pass** with zero regressions.

| Metric | Value |
|--------|-------|
| Total tests | 991 |
| Passed | 991 |
| Failed | 0 |
| New tests (selection) | 43 |
| Pre-existing pass rate | 948/948 (100%) |
| Post-integration pass rate | 991/991 (100%) |
