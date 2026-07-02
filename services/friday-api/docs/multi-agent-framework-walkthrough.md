# Multi-Agent Framework Walkthrough

## Overview

FRIDAY's Multi-Agent Framework evolves the system from a single intelligent assistant into an operating system capable of orchestrating multiple specialized AI agents concurrently. Phase 8 Sprint 1 establishes the core framework with 7 built-in agents.

## Architecture

```
AgentManager
├── AgentRegistry         — Agent CRUD + capability-based discovery
├── CommunicationBus      — Agent-to-agent messaging
├── AgentContext          — Per-agent and shared context
├── AgentScheduler        — Scheduled task execution
├── PermissionManager     — Resource-based permission control
└── StateMachine          — 8-state lifecycle transitions
```

## Built-in Agents

| Agent | Role | Capabilities | Priority |
|---|---|---|---|
| Planner | planner | task_decomposition, dependency_analysis, resource_allocation, priority_assignment | 10 |
| Research | research | web_search, knowledge_retrieval, information_synthesis, source_verification | 7 |
| Memory | memory | memory_storage, memory_retrieval, context_maintenance, summarization | 8 |
| Code | code | code_generation, code_review, code_execution, dependency_management | 6 |
| Browser | browser | web_navigation, content_extraction, form_interaction, screenshot_capture | 5 |
| Tool | tool | tool_execution, tool_discovery, workflow_execution, result_processing | 9 |
| Mission | mission | mission_planning, mission_monitoring, mission_recovery, agent_orchestration | 10 |

## Agent States

```
    ┌──────────────────────────────────────────────┐
    │                   IDLE                        │
    │         │ plan       │ pause     │ complete   │
    │         ▼            ▼           ▼            │
    │    PLANNING        PAUSED    COMPLETED        │
    │         │            │                        │
    │         ▼            │                        │
    │     RUNNING ◄─────── │                        │
    │    │    │    │       │                        │
    │    ▼    ▼    ▼       │                        │
    │ WAITING  │  CANCELLED│                        │
    │    │     │           │                        │
    │    ▼     ▼           │                        │
    │  RUNNING FAILED ─────┤                        │
    │           │          │                        │
    │           ▼          │                        │
    │          IDLE  ◄─────┘                        │
    └──────────────────────────────────────────────┘
```

## Quick Start

### Create an Agent Manager

```python
from app.agent_framework.manager import AgentManager

mgr = AgentManager()
await mgr.start()
```

### Create Custom Agents

```python
from app.agent_framework.base import AgentCapability

cap = AgentCapability(name="data_processing", description="Process data files")
mgr.create_agent(
    agent_id="data-worker",
    name="Data Worker",
    role="worker",
    capabilities=[cap],
    tools=["filesystem"],
    permissions=["filesystem:read", "filesystem:write"],
    priority=5,
)
```

### Use Built-in Agents

```python
from app.agent_framework.agent import create_all_builtin_agents

agents = create_all_builtin_agents()
for a in agents:
    mgr.create_agent(a.agent_id, a.name, a.role, a.capabilities,
                     a.tools, a.permissions, a.priority)
```

### Assign Missions

```python
mgr.assign_mission(
    agent_id="research-agent",
    mission_id="m1",
    objective="Gather information about topic X",
    assigned_by="user",
    priority=8,
)
```

### Agent-to-Agent Communication

```python
from app.agent_framework.communication import AgentMessage

# Send a request and wait for response
response = await mgr.communication.request(
    recipient="research-agent",
    payload={"query": "What is the capital of France?"},
    sender="planner-agent",
    timeout=30.0,
)

# Broadcast to all agents
await mgr.communication.broadcast(
    sender="mission-agent",
    payload={"event": "system_update", "message": "Maintenance in 5 minutes"},
)
```

### Execute Tasks

```python
async def my_handler(agent, payload):
    print(f"{agent.name} processing: {payload}")
    return {"result": "done"}

mgr.register_task_handler("process", my_handler)
result = await mgr.execute_task("data-worker", "process", {"file": "data.csv"})
```

### Register Task Handlers

```python
async def planner_handler(agent, payload):
    # Decompose the goal into steps
    return {"steps": ["step1", "step2"]}

async def research_handler(agent, payload):
    # Search the web
    return {"findings": ["result1", "result2"]}

mgr.register_task_handler("plan", planner_handler)
mgr.register_task_handler("research", research_handler)
```

### Health Monitoring

```python
h = mgr.health()
print(f"Total: {h.total_agents}, Running: {h.running_agents}, Idle: {h.idle_agents}")
```

### Schedule Tasks

```python
from app.agent_framework.scheduler import AgentScheduler

scheduler = AgentScheduler()
async def periodic_task(entry):
    print(f"Running scheduled task: {entry.task_type}")

scheduler.register_handler("cleanup", periodic_task)
await scheduler.start()
scheduler.schedule("system-agent", "cleanup", {}, interval_seconds=3600)
```

## Integration

Registered in kernel boot as Step 7o with 1 DI service:
- `agent_manager` — AgentManager instance (includes registry, communication, context, scheduler, permissions)

7 built-in agents auto-created at boot:
- planner-agent, research-agent, memory-agent, code-agent, browser-agent, tool-agent, mission-agent

Health is exposed via `KernelHealth.agent_framework` with detailed per-agent state tracking.
