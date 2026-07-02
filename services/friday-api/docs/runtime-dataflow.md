# Mission Runtime — Data Flow

## Full Mission Lifecycle

```
User submits request
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│ MissionRuntime.submit(user_request, intent)                  │
│                                                              │
│  1. Orchestrator.submit_request()                            │
│     ├── Creates Mission(mission_id, user_request, intent)     │
│     ├── State: created                                       │
│     ├── TelemetryCollector.create_mission()                   │
│     ├── RuntimeMetrics.record_mission_created()              │
│     ├── MissionStore.save_mission()                          │
│     └── Event: MissionStarted                                │
│                                                              │
│  2. MissionQueue.enqueue(mission_id, priority, deps, timeout) │
│     └── heapq.heappush(entry)                                │
│                                                              │
│  3. MissionQueue.start_processing()                          │
│     └── _process_queue() → _find_next_ready()                │
│         └── _execute_entry(entry)                            │
│             └── semaphore.acquire()                          │
│                 └── handler(mission_id)                      │
│                     └── Orchestrator.run_lifecycle(mission)  │
└──────────────────────────────────────────────────────────────┘
```

## Orchestrator.run_lifecycle() — Detailed Flow

### Stage 1: Planning

```
State: created → planning

Orchestrator._run_planning(mission):
  │
  ├── PlanningEngine.create_goal(
  │     name=mission.intent,
  │     description=mission.user_request,
  │     required_capabilities=metadata[...],
  │   )
  │   └── Goal(goal_id, name, ...)
  │     └── mission.goal_ids.append(goal.goal_id)
  │
  ├── PlanningEngine.generate_plan(goal)
  │   ├── decompose_goal() → sub-goals
  │   ├── _find_matching_actions() → PlanSteps
  │   ├── simulate_plan() → risk_score, success_probability
  │   ├── score_plan() → heuristic_scores
  │   └── memory.save_plan()
  │     └── Plan(plan_id, steps, total_cost, ...)
  │       └── mission.plan_id = plan.plan_id
  │
  ├── Telemetry: record_planning_latency(ms)
  ├── Metrics: record_planning_latency(ms)
  └── Store: save_checkpoint("planning")
```

### Stage 2: Capability Resolution

```
Orchestrator._run_capability_resolution(mission, plan):
  │
  ├── [If plan + CapabilityResolver]:
  │   └── For each plan step:
  │       CapabilityResolver.resolve(action_id)
  │       └── CapabilityResolution(resolved_tool_ids, ...)
  │
  ├── [If CapabilityRegistry]:
  │   └── CapabilityRegistry.list_capabilities() → [CapabilityDefinition]
  │
  ├── [If AgentManager]:
  │   └── AgentManager.list_agents() → [AgentModel]
  │     └── agent.capabilities → [AgentCapability]
  │
  ├── Telemetry: record_resolution_latency(ms)
  └── Store: save_checkpoint("capability_resolution")
```

### Stage 3: Tool Selection

```
Orchestrator._run_tool_selection(mission, capabilities):
  │
  ├── [If ToolSelectionEngine + capabilities]:
  │   ├── ToolSelectionContext(
  │   │     required_capabilities=capabilities,
  │   │     intent=mission.intent,
  │   │   )
  │   └── ToolSelectionEngine.select(context)
  │     └── ToolSelectionResult(tool_ids, confidence, ...)
  │       └── mission.metadata["tool_ids"] = tool_ids
  │
  ├── Telemetry: record_tool_latency("tool_selection", ms)
  └── Store: save_checkpoint("tool_selection")
```

### Stage 4: Workflow Generation

```
Orchestrator._run_workflow_generation(mission, plan, capabilities):
  │
  ├── [If plan + WorkflowExecutor]:
  │   ├── Build WorkflowGraph from plan steps
  │   │   └── For each PlanStep:
  │   │       WorkflowNode(id, name, type=TOOL, tool_id=action_id)
  │   │       WorkflowEdge(source, target)
  │   │
  │   └── WorkflowExecutor.execute(graph, global_timeout=...)
  │     └── WorkflowExecutionResult(status, node_results, ...)
  │
  └── (result stored in mission metadata)
```

### Stage 5: Execution

```
State: planning → ready → running

MissionExecutor.execute_mission(mission, plan, selection_result):
  │
  ├── Dispatcher.dispatch(mission)
  │   └── DispatchDecision(strategy, agent_ids, reason)
  │
  ├── Strategy routing:
  │   ├── SINGLE_AGENT:
  │   │   └── AgentManager.execute_task(agent_id, "mission", payload)
  │   │
  │   ├── PARALLEL_AGENTS:
  │   │   └── asyncio.gather(*[AgentManager.execute_task(...)])
  │   │
  │   ├── WORKFLOW_ENGINE:
  │   │   └── WorkflowExecutor.execute(graph)
  │   │
  │   ├── TOOL_EXECUTION:
  │   │   └── ToolExecutionEngine.execute(selection_result, mode)
  │   │
  │   ├── PLUGIN_EXECUTION:
  │   │   └── PluginRuntime.execute("mission_handler", mission)
  │   │
  │   └── (no backend) → succeeds (no-op)
  │
  ├── Checkpoint: save after execution
  │
  ├── [If failed]:
  │   └── Supervisor:
  │       ├── record_failure(mission_id)
  │       ├── can_retry()? → recover_failure()
  │       │   └── MissionExecutor.retry_mission()
  │       └── Event: MissionRecovered
  │
  └── State: → completed | failed
```

### Stage 6: Reflection

```
Orchestrator._reflection.reflect(mission, result, telemetry):
  │
  ├── _find_bottlenecks()
  │   └── Identifies slow stages from stage timings
  │
  ├── _generate_lessons()
  │   ├── Success lesson (if completed)
  │   ├── Failure lesson (if failed)
  │   ├── Reliability lesson (if retries > 0)
  │   └── Complexity lesson (if stages > 10)
  │
  └── _store_experience()
      └── PlanMemory.store_template(exp_id, plan)
```

### Stage 7: Memory Update

```
Orchestrator._run_memory_update(mission, report):
  │
  ├── MemoryManager.get_working_memory().set(
  │     "mission:{id}",
  │     {request, intent, status, duration_ms, lessons}
  │   )
  │
  └── MemoryManager.retrieve_relevant_context(
        query=mission.user_request
      )
```

### Completion

```
[If success]:
  ├── State: completed
  ├── Metrics: record_mission_completed()
  ├── Event: MissionCompleted(id, duration, stages)
  └── Telemetry: record_completion(id, True, ms)

[If failure]:
  ├── State: failed
  ├── Metrics: record_mission_failed()
  ├── Event: MissionFailed(id, "execution", error)
  └── Telemetry: record_completion(id, False, ms)

Then:
  ├── Metrics: record_duration(ms)
  ├── Store: save_mission(mission)
  ├── Store: save_telemetry(id, telemetry)
  └── Store: save_reflection(id, report)
```

## Queue Processing Detail

```
enqueue(mission_id, priority)
  │
  ├── QueueEntry(priority=-priority, mission_id, deps, timeout)
  └── heapq.heappush(_heap)
        │
        ▼
start_processing()
  └── _process_queue()
        │
        ├── _find_next_ready()
        │   ├── Scan heap for entry with all deps met
        │   ├── heapq.heappop() → ready entry
        │   └── Re-push not-ready entries
        │
        └── _execute_entry(entry)
              │
              ├── semaphore.acquire() (max_concurrent)
              ├── Create task: handler(mission_id)
              ├── Track in _running dict
              ├── asyncio.wait_for(task, timeout=entry.timeout_s)
              │   ├── Success → _completed.add(id)
              │   ├── TimeoutError → _failed[id] = "timeout"
              │   └── Exception → _failed[id] = str(e)
              └── semaphore.release()
                    │
                    └── _process_queue() → next entry
```

## State Transitions

```
created → planning → ready → running → completed → archived
                              ↓
                           paused → running
                              ↓
                           failed → recovering → running
```

All transitions validated by `MissionStateMachine.TRANSITIONS` dict.
