# Cognitive Planning Engine Walkthrough

## Overview

The Cognitive Planning Engine is a **symbolic (non-LLM)** planning system that enables agents to reason, decompose goals, generate execution plans, validate constraints, simulate outcomes, and optimize before execution.

## Architecture

```
PlanningEngine
├── Goal Model           — Priority, deadline, capabilities, constraints
├── Action Graph (DAG)   — Steps, dependencies, parallel/conditional/fallback branches
├── Decomposition        — Goal → sub-goal → action mapping
├── ConstraintEngine     — Permissions, agents, capabilities, deadlines, policies
├── HeuristicScorer      — Complexity, cost, latency, parallelism, dependency depth, risk
├── SimulationEngine     — Runtime, resource usage, success prob, risk score, bottlenecks
├── PlanValidator        — Cycles, missing deps, resource conflicts, deadlocks
├── PlanMemory           — Persistence, cache, templates, versioning, statistics
└── Health               — Plans generated, avg time, validation failures, cache hits
```

## Quick Start

### Create a Planning Engine

```python
from app.planning.planner import PlanningEngine
engine = PlanningEngine()
```

### Create Goals

```python
goal = engine.create_goal(
    name="Deploy microservice",
    description="Build, test, and deploy the new auth service",
    priority=8.0,
    required_capabilities=["code_generation", "testing", "tool_execution"],
    success_criteria=["all_tests_pass", "deployment_confirmed"],
)
```

### Generate Plans

```python
plan = await engine.generate_plan(goal)
print(f"Plan: {plan.plan_id}, Steps: {len(plan.steps)}")
for step in plan.steps:
    print(f"  {step.step_id}: {step.action_name} ({step.estimated_duration}s, ${step.estimated_cost})")
```

### Validate Plans

```python
result = await engine.validate_plan(plan)
if result.valid:
    print("Plan is valid")
else:
    for err in result.errors:
        print(f"Error: {err.message}")
    for warn in result.warnings:
        print(f"Warning: {warn.message}")
```

### Simulate Plans

```python
sim = engine.simulate_plan(plan)
print(f"Estimated runtime: {sim.estimated_runtime}s")
print(f"Resource usage: {sim.estimated_resource_usage}")
print(f"Success probability: {sim.success_probability:.1%}")
print(f"Risk score: {sim.risk_score}")
for b in sim.bottlenecks:
    print(f"Bottleneck: {b}")
```

### Score Plans with Heuristics

```python
scores = engine.score_plan(plan)
print(f"Complexity: {scores.complexity}")
print(f"Cost: {scores.cost}")
print(f"Latency: {scores.latency}")
print(f"Parallelism: {scores.parallelism}")
print(f"Risk: {scores.risk}")
print(f"Total: {scores.total}")
```

### Optimize Plans

```python
optimized = await engine.optimize_plan(plan)
print(f"Before: ${plan.total_cost}, After: ${optimized.total_cost}")
print(f"Score improvement: {optimized.metadata['score_improvement']}")
```

### Revise Plans with Feedback

```python
revised = await engine.revise_plan(optimized, {
    "remove_steps": ["step_to_remove"],
    "add_steps": [
        {"action_id": "test", "action_name": "Run integration tests",
         "estimated_cost": 3.0, "estimated_duration": 5.0,
         "dependencies": ["s1"]},
    ],
    "modify_steps": {
        "step_id_123": {"action_id": "analyze", "estimated_duration": 1.0},
    },
})
```

### Check Constraints

```python
result = await engine.check_constraints(goal, plan)
print(f"Constraints satisfied: {result.passed}")
for v in result.violations:
    print(f"  [{v.severity}] {v.rule}: {v.message}")
```

### Work with Plan Memory

```python
# Save/load plans
await engine._memory.save_plan(plan)
loaded = await engine._memory.load_plan(plan.plan_id)

# Find similar plans
similar = await engine.find_similar_plans(goal)

# Templates
await engine.store_template("deploy-template", plan)
template = await engine.load_template("deploy-template")

# Archive
await engine.archive_plan(plan.plan_id)

# Statistics
stats = engine.memory_stats()
```

### Custom Actions

```python
from app.planning.action import Action

engine.register_action(Action(
    action_id="deploy_k8s",
    name="Deploy to Kubernetes",
    description="Deploy container to Kubernetes cluster",
    required_capabilities=["tool_execution"],
    estimated_cost=5.0,
    estimated_duration=10.0,
))
```

### Health Monitoring

```python
h = engine.health()
print(f"Status: {h.status}")
print(f"Plans generated: {h.plans_generated}")
print(f"Avg planning time: {h.average_planning_time_ms}ms")
print(f"Validation failures: {h.validation_failures}")
print(f"Cache hits: {h.cache_hits}")
print(f"Active goals: {h.active_goals}")
```

### Event Types

| Event | Trigger |
|---|---|
| GoalCreated | Goal created |
| GoalUpdated | Goal status changed |
| PlanGenerated | Plan generated from goal |
| PlanValidated | Plan validated |
| PlanRejected | Plan rejected by validator |
| PlanOptimized | Plan optimized |
| PlanExecuted | Plan executed |
| PlanArchived | Plan archived |

## Integration with Agent Manager

```python
from app.agent_framework.manager import AgentManager
from app.planning.planner import PlanningEngine

mgr = AgentManager()
engine = PlanningEngine(agent_manager=mgr)

# Generate and execute a plan
goal = engine.create_goal("Research and summarize AI trends")
plan = await engine.generate_plan(goal)
success = await engine.execute_plan(plan)
```
