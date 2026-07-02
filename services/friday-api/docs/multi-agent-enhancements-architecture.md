# Multi-Agent Enhancements Architecture

## Design Overview

Phase 8 Sprint 2 builds on Sprint 1's agent framework with 9 new modules that enable collaborative multi-agent workflows, persistence, and production-grade reliability.

## New Module Map

```
app/agent_framework/
├── locks.py          # KeyLockManager — asyncio-based key-level locking
├── blackboard.py     # Shared knowledge space with versioning and conflict detection
├── delegation.py     # Task hierarchy, parent-child, dependency tracking, completion propagation
├── coordinator.py    # Parallel/serial/dag execution, priority queue, resource allocation
├── priority.py       # Dynamic priority calculation with 5-factor weighting
├── consensus.py      # 4 deterministic decision strategies
├── persistence.py    # JSON file-based checkpoint/restore with warm restart
├── recovery.py       # Automatic crash recovery for agents, tasks, context
└── metrics.py        # Delegation, utilization, latency, recovery statistics
```

## Module Details

### locks.py — KeyLockManager
- `acquire(key, timeout)` — Acquire lock for a key, returns bool
- `release(key)` — Release lock
- `is_locked(key)` — Check if key is locked
- `get_active_locks()` — List locked keys
- Thread-safe using internal `asyncio.Lock` for dict access
- Per-key `asyncio.Lock` instances

### blackboard.py — Blackboard
- `post(key, value, writer)` — Write with auto-incrementing version
- `read(key)` — Read latest value
- `read_with_meta(key)` — Read full entry metadata
- `delete(key)` — Remove entry
- `get_version(key)` — Current version
- `get_history(key)` — All versions
- `check_conflict(key, version)` — Conflict detection
- Working memory for ephemeral data
- Optional update callback for event publishing

### delegation.py — DelegationManager
- `DelegationTask` — Task model with parent, children, dependencies, status
- `delegate(parent, agent, type, payload, deps)` — Create subtask
- `complete_task(task_id, result)` — Mark complete, propagate to parent
- `fail_task(task_id, error)` — Mark failed
- `get_ready_tasks()` — Tasks whose dependencies are met
- `get_dependency_graph(task_id)` — Full dependency view
- `restore_task(data)` — Restore from checkpoint
- Completion callbacks for event publishing

### coordinator.py — Coordinator
- `execute_serial(tasks)` — Sequential execution
- `execute_parallel(tasks)` — Concurrent execution via `asyncio.gather`
- `execute_dependency_aware(graph)` — DAG-based topological execution
- `enqueue(task, priority)` — Priority queue via heapq
- `process_queue(max_tasks)` — Dequeue and execute
- `allocate_resource(agent, resource, quantity)` — Track resource usage
- Execute hooks for monitoring

### priority.py — PriorityEngine
- 5-factor weighted formula:
  - Urgency (30%)
  - Dependencies inverse (20%)
  - Resource availability (20%)
  - Runtime inverse (10%)
  - Mission importance (20%)
- `calculate(factors)` → float (0-10 scale)
- `update(current, factors)` → averaged new priority

### consensus.py — ConsensusEngine
| Strategy | Behavior |
|---|---|
| MAJORITY | Accept if >50% approve |
| UNANIMOUS | Accept only if all approve |
| PRIORITY_OVERRIDE | Highest priority agent decides |
| COORDINATOR_DECISION | Designated coordinator decides |

`reach_consensus(proposal, agents, strategy)` → `ConsensusResult`

### persistence.py — PersistenceManager
- File-based JSON persistence in configurable directory
- `save_checkpoint(data)` — Full system snapshot
- `load_checkpoint()` — Restore snapshot
- Individual agent state save/load
- Delegation tree, blackboard, metrics persistence
- `warm_restart()` — Load latest checkpoint
- `clear()` — Wipe all data

### recovery.py — RecoveryManager
- `recover_all()` → `RecoveryReport` — Full system recovery
- `recover_agent(id)` — Restore single agent status
- `_recover_delegated_work()` — Restore pending tasks
- `_recover_context()` — Restore blackboard entries
- `cleanup_inconsistent_state()` — Reset stuck running tasks
- Tracks recovery count and last recovery timestamp

### metrics.py — MetricsCollector
- `record_delegation()` — Increment delegation counter
- `record_parallel_run(used, total)` — Track parallel efficiency
- `record_queue_latency(ms)` — Track wait times
- `record_utilization(agent, busy, total)` — Per-agent utilization
- `record_recovery()` — Count recoveries
- `snapshot()` → `MetricsSnapshot` — Current state summary
- `reset()` — Clear all metrics

## Health Model

Updated `AgentFrameworkHealth` with 5 new sub-health fields:

```python
coordinator: CoordinatorHealth    # queue_size, active_tasks, resources_allocated
delegation: DelegationHealth      # total/pending/running/completed/failed tasks
blackboard: BlackboardHealth      # entries, locked_keys, working_memory_entries
persistence: PersistenceHealth    # has_checkpoint, stored_agents, total_files
recovery: RecoveryHealth          # last_recovery, total_recoveries
```

## Event Types (8 new + 8 existing = 16 total)

New: DelegationStarted, DelegationCompleted, TaskAssigned, TaskCompleted, TaskRecovered, ConsensusReached, BlackboardUpdated, CheckpointCreated

## Integration

| Integration | File | Pattern |
|---|---|---|
| DI Registration | `boot.py:574` (Step 7p) | 6 new singletons |
| Health Checks | `kernel.py:health()` | 6 new SubsystemHealth checks |
| Health Model | `health.py:KernelHealth` | 6 new fields |
| Capabilities | `boot.py` | 6 new capabilities |
| Exports | `__init__.py` | 20 new exported symbols |

## Dependencies

- **Runtime**: Python 3.12+ stdlib only (asyncio, json, heapq, uuid, pathlib, tempfile)
- **External**: `app.agent_framework.*` (Sprint 1 modules)
- **Test**: pytest, anyio
