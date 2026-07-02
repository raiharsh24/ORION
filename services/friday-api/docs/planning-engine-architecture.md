# Cognitive Planning Engine Architecture

## Design Overview

Phase 8 Sprint 3 implements a deterministic symbolic planning engine — not an LLM — that allows agents to reason, plan, evaluate options, revise plans, and cooperate before execution.

## Design Principles

1. **Symbolic, Not Neural** — No LLM calls; pure deterministic algorithms
2. **DAG-Based** — Plans are directed acyclic graphs with parallel, conditional, and fallback branches
3. **Goal-Driven** — Planning starts from goal decomposition
4. **Multi-Stage** — Generate → Validate → Simulate → Score → Optimize → Revise → Execute
5. **Memory-Augmented** — Successful plans are cached, templated, and reused

## Module Map

```
app/planning/
├── __init__.py        # Public API exports (20+ symbols)
├── base.py            # Plan, PlanStep data models
├── goal.py            # Goal model with hierarchy support
├── action.py          # Action model
├── graph.py           # ActionGraph — DAG with cycle detection, topological sort, parallel batches, critical path
├── planner.py         # PlanningEngine — main orchestrator
├── constraints.py     # ConstraintEngine — permissions, agents, capabilities, deadlines, policies
├── heuristics.py      # HeuristicScorer — 6-dimension deterministic scoring
├── simulation.py      # SimulationEngine — runtime, resource, risk, bottleneck estimation
├── validator.py       # PlanValidator — cycle, missing dep, resource conflict, deadlock detection
├── memory.py          # PlanMemory — file-based persistence, cache, templates, versioning
├── events.py          # 8 planning event types
└── health.py          # PlanningHealth model
```

## Core Models

### Goal
| Field | Type | Description |
|---|---|---|
| goal_id | str | Unique ID |
| name | str | Goal name |
| priority | float | 0-10 scale |
| deadline | Optional[datetime] | Completion deadline |
| required_capabilities | List[str] | Capabilities needed |
| success_criteria | List[str] | Completion criteria |
| constraints | Dict | Custom constraints |
| estimated_cost | float | Expected cost |
| estimated_duration | float | Expected duration (s) |
| parent_goal_id | Optional[str] | Parent hierarchy |
| child_goal_ids | List[str] | Sub-goals |
| status | str | active, planned, in_progress, completed, failed, cancelled |

### PlanStep
| Field | Type | Description |
|---|---|---|
| step_id | str | Unique ID |
| action_id | str | Action to execute |
| action_name | str | Human-readable name |
| agent_id | Optional[str] | Assigned agent |
| dependencies | List[str] | Prerequisite step IDs |
| parallel_group | Optional[str] | Steps in same group run concurrently |
| condition | Optional[str] | Conditional execution expression |
| fallback_step_id | Optional[str] | Fallback if step fails |
| estimated_cost | float | Expected cost |
| estimated_duration | float | Expected duration |

### Plan
| Field | Type | Description |
|---|---|---|
| plan_id | str | Unique ID |
| goal_id | str | Associated goal |
| steps | List[PlanStep] | Execution steps |
| total_cost | float | Sum of step costs |
| total_duration | float | Sum of step durations |
| risk_score | float | 0-1 risk assessment |
| success_probability | float | 0-1 success likelihood |
| constraint_score | float | 0-1 constraint compliance |
| status | str | draft, generated, validated, executing, completed, failed |
| version | int | Revision counter |

## Action Graph (DAG)

The `ActionGraph` provides:

- **Cycle Detection**: DFS-based with 3-color marking, returns all cycles
- **Topological Sort**: Kahn's algorithm for execution ordering
- **Parallel Batches**: Groups steps by dependency depth (same batch → run concurrently)
- **Critical Path**: Longest-duration path through the DAG (determines total runtime)
- **Dependency Depth**: Maximum chain length from a node to a leaf

## Heuristic Scoring (6 Dimensions)

| Dimension | Weight | Formula |
|---|---|---|
| Complexity | 15% | steps + edges |
| Cost | 20% | total estimated cost (normalized) |
| Latency | 15% | critical path duration (normalized) |
| Parallelism | 15% | steps / (batches * 2), clamped to [0,1] |
| Dependency Depth | 10% | max depth (normalized) |
| Risk (inverted) | 25% | 1 - failure_prob * depth_penalty * cost_factor |

Total = weighted sum, clamped to [0, 1].

## Simulation Model

- **Runtime**: Critical path total duration
- **Resource Usage**: Sum of step costs
- **Success Probability**: 0.95^n (n = steps)
- **Risk Score**: (1 - success_prob) + depth_penalty
- **Bottlenecks**: Steps with most dependencies + longest on critical path

## Validation Rules

| Rule | Severity | Condition |
|---|---|---|
| no_steps | error | Plan has zero steps |
| cycle_detected | error | DAG contains cycles |
| missing_dependency | error | Step depends on non-existent step |
| resource_conflict | warning | Agent assigned to concurrent steps |
| conditional_no_fallback | warning | Conditional step has no fallback |
| deadlock | error | Circular fallback between steps |

## Constraint Engine

| Check | Severity | Description |
|---|---|---|
| no_cycles | error | DAG must be acyclic |
| dependencies_exist | error | All dependency step IDs must exist |
| deadline | warning | Total duration ≤ deadline |
| agent_available | error | All assigned agents must be available |
| resource_limit | warning | Total cost ≤ max_cost |
| policy_agent | error | Policy requiring agent assignments |
| goal_max_cost | warning | Plan cost ≤ goal constraint max_cost |

## Plan Memory

- **File-based**: JSON in configurable directory (default `/tmp/.planning_memory/`)
- **In-memory cache**: Recent plans cached in dict
- **Templates**: Reusable plan patterns keyed by template_id
- **Similarity search**: By goal name and capability intersection
- **Statistics**: saves, loads, cache hits/misses, archives, template matches

## Events (8 types)

GoalCreated, GoalUpdated, PlanGenerated, PlanValidated, PlanRejected, PlanOptimized, PlanExecuted, PlanArchived

## Health Model

```python
@dataclass
class PlanningHealth:
    status: str
    plans_generated: int
    average_planning_time_ms: float
    validation_failures: int
    cache_hits: int
    simulation_accuracy: float
    total_goals: int
    active_goals: int
    plans_cached: int
    template_count: int
```

## Integration

| Integration | File | Pattern |
|---|---|---|
| DI Registration | `boot.py:698` (Step 7q) | `register_singleton("planning_engine", ...)` |
| Health Check | `kernel.py:health()` | `check_service_health("planning_engine", ...)` |
| Health Model | `health.py:KernelHealth` | `planning_engine: SubsystemHealth` field |
| Capability | `boot.py` | `register_capability("CognitivePlanning", ...)` |

## Dependencies

- **Runtime**: Python 3.12+ stdlib only (asyncio, uuid, json, heapq, pathlib, tempfile)
- **External**: `app.agent_framework.manager.AgentManager` (optional, for agent-aware planning)
