# Multi-Agent Enhancements Walkthrough

## Overview

Phase 8 Sprint 2 extends FRIDAY's Multi-Agent Framework with delegation, coordination, shared blackboard, persistence, recovery, consensus, priority scheduling, and metrics — turning the basic framework into a production-grade collaborative agent system.

## Architecture Additions

```
AgentManager (extended)
├── DelegationManager     — Task hierarchy, parent-child, dependency tracking
├── Coordinator           — Parallel/serial/dependency-aware execution, priority queues
├── Blackboard            — Shared inter-agent knowledge with versioning and conflict detection
├── KeyLockManager        — Resource-level locking for blackboard
├── ConsensusEngine       — Majority/unanimous/coordinator/priority voting
├── PriorityEngine        — Dynamic priority from urgency, deps, resources, runtime, mission
├── PersistenceManager    — JSON checkpoint/restore for agents, tasks, context, queues
├── RecoveryManager       — Automatic crash recovery and state restoration
└── MetricsCollector      — Delegation, utilization, latency, recovery tracking
```

## Quick Start

### Delegation

```python
task = await mgr.delegation.delegate(
    parent_task_id=None,
    agent_id="research-agent",
    task_type="research",
    payload={"query": "latest AI papers"},
)

# Create child subtask
child = await mgr.delegation.delegate(
    parent_task_id=task.task_id,
    agent_id="code-agent",
    task_type="code",
    payload={"task": "implement algorithm"},
)

# Complete task
await mgr.delegation.complete_task(task.task_id, {"result": "done"})

# Mark failed
await mgr.delegation.fail_task(child.task_id, "implementation error")
```

### Coordinator

```python
# Serial execution
results = await mgr.coordinator.execute_serial([
    {"agent_id": "agent1", "type": "task_a", "payload": {}},
    {"agent_id": "agent2", "type": "task_b", "payload": {}},
])

# Parallel execution
results = await mgr.coordinator.execute_parallel(tasks)

# Dependency-aware DAG execution
results = await mgr.coordinator.execute_dependency_aware({
    "build": {"agent_id": "a1", "type": "build", "payload": {}, "depends_on": []},
    "test": {"agent_id": "a2", "type": "test", "payload": {}, "depends_on": ["build"]},
    "deploy": {"agent_id": "a3", "type": "deploy", "payload": {}, "depends_on": ["build", "test"]},
})

# Priority queue
await mgr.coordinator.enqueue(task_info, priority=8.5)
results = await mgr.coordinator.process_queue(max_tasks=3)
```

### Blackboard

```python
# Post facts
version = await mgr.blackboard.post("status", "running", writer="planner-agent")

# Read facts
val = await mgr.blackboard.read("status")

# Read with metadata
entry = await mgr.blackboard.read_with_meta("status")
print(f"Version: {entry.version}, Writer: {entry.writer}")

# Check for conflicts
if mgr.blackboard.check_conflict("status", expected_version=2):
    print("Conflict detected!")

# Working memory (volatile)
await mgr.blackboard.set_working("temp_result", 42)
val = mgr.blackboard.get_working("temp_result")
```

### Locking

```python
from app.agent_framework.locks import KeyLockManager

locks = KeyLockManager()
await locks.acquire("resource_x", timeout=10.0)
try:
    # critical section
    pass
finally:
    locks.release("resource_x")
```

### Priority Engine

```python
from app.agent_framework.priority import PriorityEngine, PriorityFactors

pe = PriorityEngine()
factors = PriorityFactors(
    urgency=8.0,
    dependency_count=3,
    resource_availability=0.8,
    estimated_runtime=5.0,
    mission_importance=9.0,
)
priority = pe.calculate(factors)  # Returns 0-10 scale

updated = pe.update(current_priority=5.0, factors=factors)
```

### Consensus

```python
from app.agent_framework.consensus import ConsensusEngine, ConsensusStrategy

ce = ConsensusEngine()
result = await ce.reach_consensus(
    proposal="deploy v2.1",
    agents=["planner-agent", "research-agent", "code-agent", "mission-agent"],
    strategy=ConsensusStrategy.MAJORITY,
)
print(f"Accepted: {result.accepted}, Confidence: {result.confidence}")
```

### Persistence

```python
from app.agent_framework.persistence import PersistenceManager, CheckpointData

pm = PersistenceManager(base_path="/tmp/my-checkpoints")

# Create checkpoint
data = CheckpointData(
    agents={"agent1": {"state": "RUNNING"}},
    pending_tasks=[{"task_id": "t1", "agent_id": "a1", "task_type": "build", "payload": {}}],
)
await pm.save_checkpoint(data)

# Warm restart
checkpoint = await pm.warm_restart()
```

### Recovery

```python
report = await mgr.recovery.recover_all()
print(f"Restored: {report.restored_agents} agents, "
      f"{report.restored_tasks} tasks, "
      f"{report.restored_context_keys} context keys")

# Clean up stuck tasks
errors = await mgr.recovery.cleanup_inconsistent_state()
```

### Metrics

```python
mgr.metrics.record_delegation()
mgr.metrics.record_parallel_run(agents_used=4, total_agents=7)
mgr.metrics.record_queue_latency(150.0)
mgr.metrics.record_utilization("agent1", busy_seconds=45.0, total_seconds=60.0)
mgr.metrics.record_recovery()
mgr.metrics.record_task_completed()

snap = mgr.metrics.snapshot()
print(f"Delegations: {snap.delegation_count}")
print(f"Avg parallel efficiency: {snap.average_parallel_efficiency}")
print(f"Avg queue latency: {snap.average_queue_latency_ms}ms")
print(f"Overall utilization: {snap.overall_utilization:.1%}")
```

### Health

```python
h = mgr.health()
print(f"Coordinator: {h.coordinator.status}, Queue: {h.coordinator.queue_size}")
print(f"Delegation: {h.delegation.total_tasks} tasks, {h.delegation.pending} pending")
print(f"Blackboard: {h.blackboard.entries} entries, {h.blackboard.locked_keys} locked")
print(f"Persistence: checkpoint={h.persistence.has_checkpoint}, files={h.persistence.total_files}")
print(f"Recovery: {h.recovery.total_recoveries} recoveries")
```

## New Events

| Event | Trigger |
|---|---|
| DelegationStarted | Task delegated to agent |
| DelegationCompleted | Delegation task completed/failed |
| TaskAssigned | Task assigned to agent |
| TaskCompleted | Task finished |
| TaskRecovered | Task restored from checkpoint |
| ConsensusReached | Consensus decision made |
| BlackboardUpdated | Blackboard key written |
| CheckpointCreated | Checkpoint saved |

## Integration

Registered in kernel boot as Step 7p with 5 new DI services and 5 new health fields in KernelHealth.
