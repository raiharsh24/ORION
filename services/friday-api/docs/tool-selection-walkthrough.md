# Tool Selection Engine — Walkthrough

## Overview

The Tool Selection Engine (`app/tool_selection/selector.py`) determines the
optimal set of tools required to satisfy a user request, given an analyzed
intent, strategy, and execution plan. It performs deterministic selection
only — it does **not** execute tools.

## Input

```python
ToolSelectionContext(
    intent=IntentType.BROWSER,
    strategy=...,
    execution_plan=...,
    optimizer_recommendations={"recommended_tools": [...], "discouraged_tools": [...]},
    pipeline_metadata={"max_tool_latency_ms": 500, "tool_cost_budget": 10.0},
    user_permission_level=PermissionLevel.USER,
    required_categories=["browser", "filesystem"],
    required_capabilities=["read"],
    prefer_streaming=True,
    prefer_parallel=False,
)
```

## Output

```python
ToolSelectionResult(
    selected_tools=[SelectedTool(tool=..., score=85.0, reason="Best match by scoring")],
    selection_scores={"browser_get": 85.0, "fs_read": 72.5},
    selection_reasons={"browser_get": "Best match by scoring"},
    fallback_tools=[SelectedTool(tool=..., is_fallback=True)],
    estimated_total_latency_ms=250.0,
    estimated_total_cost=2.5,
    confidence=0.85,
    candidate_count=8,
    selection_latency_ms=1.23,
)
```

## Selection Flow

```
Input Context
     │
     ▼
Filter Candidates
  • Available (not error/unavailable)
  • Has permission
  • Matches required categories
     │
     ▼
Score Each Candidate
  • Intent match       (25 pts)
  • Health status      (20 pts)
  • Latency            (15 pts)
  • Cost               (10 pts)
  • Streaming support  (10 pts)
  • Parallel support   (10 pts)
  • Permission         ( 5 pts)
  • Category match     ( 5 pts)
  • Optimizer ±        (15/-15 pts)
     │
     ▼
Sort by Score (descending)
     │
     ▼
Select Tools (no duplicates)
  • Try primary selection
  • If fails → find fallback
  • Include dependencies
     │
     ▼
Compute Result
  • Estimated latency/cost
  • Confidence = selected / total
  • Publish events
```

## Scoring Weights

| Factor                 | Weight | Notes                              |
|------------------------|--------|------------------------------------|
| Intent match           | 25     | Intent type appears in tool meta   |
| Health status          | 20     | healthy=20, unknown=10, warn=5     |
| Latency                | 15     | Inverse ratio to max_tool_latency  |
| Cost                   | 10     | Inverse ratio to tool_cost_budget  |
| Streaming support      | 10     | Only if context prefers streaming  |
| Parallel support       | 10     | Only if context prefers parallel   |
| Permission match       | 5      | User has permission for tool       |
| Category match         | 5      | Tool category matches requirements |
| Optimizer recommend    | 15     | Boost for recommended tools        |
| Optimizer discourage   | -15    | Penalty for discouraged tools      |

## Filtering Rules

| Rule               | Effect                                     |
|--------------------|--------------------------------------------|
| `is_available`     | Rejects `error` and `unavailable` health   |
| `has_permission`   | Checks user level >= tool level            |
| `matches_category` | Passes if context has no category filter   |
| `dependencies`     | All required deps must be satisfiable      |
| `is_healthy`       | Rejects `error` status (primary selection) |

## Fallback Logic

When the best tool is unavailable (unhealthy, dependency failure), the engine
automatically selects the highest-ranked healthy alternative from the same
category. Alternatives are sorted by:

1. Success count (descending)
2. Estimated latency (ascending)

## Events

| Event                   | When Published                | Data                                    |
|-------------------------|-------------------------------|-----------------------------------------|
| `ToolSelectionStarted`  | Selection begins              | intent, context                         |
| `ToolSelected`          | A tool is selected            | tool_id, name, score, reason            |
| `FallbackToolSelected`  | Fallback replaces primary     | tool_id, name, original_tool_id, reason |
| `ToolSelectionCompleted`| Selection ends                | intent, selected_count, confidence      |

## Integration

- **DI key:** `"tool_selection_engine"`
- **Module:** `"tool_selection_engine"` v1.0.0, depends on `event_bus` and `universal_tool_registry`
- **Capability:** `"ToolSelection"`
- **Health:** `tool_selection_engine` subsystem in `KernelHealth`
