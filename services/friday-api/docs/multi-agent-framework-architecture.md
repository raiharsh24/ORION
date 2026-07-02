# Multi-Agent Framework Architecture

## Design Overview

Phase 8's Multi-Agent Framework is a production-grade agent orchestration system built on top of Phase 7's agent infrastructure. It provides a complete lifecycle management system for 7 built-in specialized agents with inter-agent communication, scheduling, permissions, and health monitoring.

## Design Principles

1. **State Machine Driven**: Every agent has a well-defined state lifecycle (8 states) with validated transitions
2. **Built-in Specialization**: 7 pre-built agents with distinct roles, capabilities, and tools
3. **Inter-agent Communication**: Asynchronous messaging with request/response and broadcast patterns
4. **Resource-based Permissions**: Fine-grained access control per agent
5. **Separation of Concerns**: Manager orchestrates, Registry stores, Bus communicates, Context stores data

## Module Map

```
app/agent_framework/
├── __init__.py          # Public API exports (31 symbols)
├── base.py              # AgentModel, AgentCapability, MissionAssignment, AgentTelemetry
├── state.py             # AgentState enum, StateMachine with validated transitions
├── permissions.py       # AgentPermission, PermissionManager
├── communication.py     # CommunicationBus, AgentMessage
├── registry.py          # AgentRegistry with capability indexing
├── context.py           # AgentContext (per-agent + shared)
├── scheduler.py         # AgentScheduler with tick loop
├── events.py            # 8 event types (FridayEvent subclasses)
├── health.py            # AgentFrameworkHealth model
├── manager.py           # AgentManager (central orchestrator)
└── agent.py             # 7 built-in agent definitions
```

## Core Models

### AgentModel
| Field | Type | Description |
|---|---|---|
| agent_id | str | Unique identifier |
| name | str | Human-readable name |
| role | str | Functional role (planner, research, etc.) |
| capabilities | List[AgentCapability] | What the agent can do |
| tools | List[str] | What tools the agent uses |
| mission | Optional[MissionAssignment] | Current mission assignment |
| state | AgentState | Current lifecycle state |
| priority | int | Scheduling priority (higher = more important) |
| memory_scope | str | Memory persistence scope |
| permissions | List[str] | Granted permissions |
| telemetry | AgentTelemetry | Execution metrics |

### AgentState (8 states)
| State | Description | Valid Next States |
|---|---|---|
| IDLE | Ready for work | PLANNING, PAUSED, COMPLETED |
| PLANNING | Analyzing task | RUNNING, FAILED, CANCELLED, PAUSED |
| RUNNING | Executing task | WAITING, COMPLETED, FAILED, PAUSED, CANCELLED |
| WAITING | Awaiting dependency | RUNNING, FAILED, CANCELLED, PAUSED |
| PAUSED | Suspended | IDLE, CANCELLED, FAILED |
| COMPLETED | Task done | (terminal) |
| FAILED | Error occurred | IDLE |
| CANCELLED | Aborted | IDLE |

### CommunicationBus Patterns

| Pattern | Method | Description |
|---|---|---|
| Direct Send | `send(message)` | Route to specific agent |
| Request-Response | `request(recipient, payload)` | Send + wait for response |
| Response | `respond(original, payload)` | Reply to request |
| Broadcast | `broadcast(sender, payload)` | Send to all agents |
| Subscribe | `subscribe(agent_id, handler)` | Register message handler |

## Built-in Agents Detail

### Planner Agent
- **Priority**: 10 (highest)
- **Capabilities**: task_decomposition, dependency_analysis, resource_allocation, priority_assignment
- **Tools**: planner, knowledge.search, memory

### Research Agent
- **Priority**: 7
- **Capabilities**: web_search, knowledge_retrieval, information_synthesis, source_verification
- **Tools**: knowledge.search, browser, memory

### Memory Agent
- **Priority**: 8
- **Capabilities**: memory_storage, memory_retrieval, context_maintenance, summarization
- **Tools**: memory, knowledge.search
- **Memory Scope**: persistent

### Code Agent
- **Priority**: 6
- **Capabilities**: code_generation, code_review, code_execution, dependency_management
- **Tools**: terminal, filesystem, knowledge.search

### Browser Agent
- **Priority**: 5
- **Capabilities**: web_navigation, content_extraction, form_interaction, screenshot_capture
- **Tools**: browser, desktop.screenshot, clipboard

### Tool Agent
- **Priority**: 9
- **Capabilities**: tool_execution, tool_discovery, workflow_execution, result_processing
- **Tools**: filesystem, terminal, clipboard, desktop

### Mission Agent
- **Priority**: 10
- **Capabilities**: mission_planning, mission_monitoring, mission_recovery, agent_orchestration
- **Tools**: mission, workflow, scheduler

## Permission Model

Permissions use a `resource:action` format:

```python
permissions.grant("agent1", "filesystem", "read")
permissions.check("agent1", "filesystem", "read")  # True
permissions.revoke("agent1", "filesystem", "read")
permissions.check("agent1", "filesystem", "read")  # False
```

Role-based permissions are also supported:

```python
permissions.grant_role_permission("admin", "system", "config")
permissions.apply_role_permissions("agent1", "admin")
```

## Event Types (8 events)

| Event | Trigger |
|---|---|
| AgentRegistered | Agent created and registered |
| AgentUnregistered | Agent destroyed |
| AgentStateChanged | State transition occurred |
| AgentTaskStarted | Task execution began |
| AgentTaskCompleted | Task finished successfully |
| AgentTaskFailed | Task encountered error |
| AgentMessageSent | Message transmitted |
| AgentHealthChanged | Health status changed |

## Integration Points

| Integration | File | Pattern |
|---|---|---|
| DI Registration | `boot.py:542` (Step 7o) | `register_singleton("agent_manager", ...)` |
| Health Check | `kernel.py:health()` | `check_service_health("agent_framework", ...)` |
| Health Model | `health.py:KernelHealth` | `agent_framework: SubsystemHealth` field |
| Capability | `boot.py` | `register_capability("MultiAgentFramework", ...)` |
| Events | `events.py` | 8 event types extending `FridayEvent` |

## Health Model

```python
@dataclass
class AgentFrameworkHealth:
    overall_status: str
    running_agents: int
    idle_agents: int
    failed_agents: int
    planning_agents: int
    waiting_agents: int
    paused_agents: int
    completed_agents: int
    cancelled_agents: int
    total_agents: int
    queue_size: int
    pending_tasks: int
    average_execution_time_ms: float
    agents_with_context: int
    bus_subscribers: int
    bus_pending_responses: int
    scheduled_entries: int
    agent_details: List[Dict]
```

## Dependencies

- **Runtime**: Python 3.12+ stdlib only (asyncio, uuid, datetime)
- **Test**: pytest, anyio
- **External**: None (uses `app.events.events.FridayEvent` for event publishing)
