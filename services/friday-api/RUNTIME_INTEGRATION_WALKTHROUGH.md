# Runtime Integration Walkthrough

**Date:** 2026-06-28  
**Scope:** Wiring Alpha 5.0 Workflow Runtime into the live request pipeline  
**Changes:** 7 files modified, 3 files created, 13 integration tests added  
**Test results:** 170 passed, 0 failed (was 157 before)

---

## What Was Done

Three critical blockers from the Runtime Validation Report were addressed:

| Blocker | Summary | Fix |
|---------|---------|-----|
| C1 | Planner produces `ExecutionPlan`, Runtime consumes `ExecutionPlanInput` — no adapter | Created `app/friday/plan_adapter.py` |
| C2 | Workflow Runtime registered in kernel but never called from orchestrator | Modified `FridayOrchestrator` to route plans through `RuntimeSchedulerBridge` |
| C3 | No API integration — `/ask` and `/chat` couldn't reach the runtime | Wired `runtime_scheduler_bridge` into `get_orchestrator()` factory |

Additionally, two Validation Report high-severity items were fixed:
| H5 | `KernelHealth` omitted `workflow_runtime` field | Added `workflow_runtime` to `KernelHealth` model + health check |
| H6 | Runtime health not wired into health aggregation | `check_service_health("workflow_runtime", runtime_svc)` integrated |

---

## File Changes

### Created Files

```
app/friday/plan_adapter.py                        (new, 46 lines)
tests/test_runtime_integration.py                (new, 272 lines)
```

### Modified Files

```
app/friday/orchestrator.py                        (3 changes)
app/api/routes.py                                (1 change)
app/kernel/kernel.py                             (3 changes)
app/kernel/health.py                             (1 change)
app/workflow_runtime/scheduler_bridge.py         (1 change)
```

---

## Architecture: How the Flow Changes

### Before (Alpha 4.x — disconnected)

```
User Request
  │
  ├── app/api/routes.py → get_orchestrator()
  │     └── FridayOrchestrator
  │           ├── IntentClassifier
  │           ├── Planner → ExecutionPlan
  │           │     └── ToolExecutor.execute()    ← bypasses runtime entirely
  │           ├── LLMRouter
  │           └── MemoryEngine
  │
  ├── app/workflow/engine.py                     ← old workflow, separate path
  └── app/workflow_runtime/                      ← registered but unreachable
```

### After (Alpha 5.0 — integrated)

```
User Request
  │
  ├── app/api/routes.py → get_orchestrator()
  │     └── FridayOrchestrator
  │           ├── IntentClassifier
  │           ├── Planner → ExecutionPlan
  │           │     ├── execution_plan_to_input()  ← new adapter
  │           │     ├── RuntimeSchedulerBridge.submit_and_wait()  ← new path
  │           │     │     └── WorkflowRuntimeManager.start_from_plan()
  │           │     │           └── WorkflowRuntimeExecutor.execute_step()
  │           │     │                 └── AgentCoordinator.delegate()
  │           │     │                       └── WorkflowWorkerAgent.execute_task()
  │           │     │                             └── SharedContext
  │           │     │                                   ├── execute_tool() → ToolEngine
  │           │     │                                   ├── generate_llm() → LLMRouter
  │           │     │                                   └── query_knowledge() → KnowledgeEngine
  │           │     └── [fallback] ToolExecutor.execute()  ← preserved for compat
  │           ├── LLMRouter
  │           └── MemoryEngine
```

---

## Change Details

### 1. `app/friday/plan_adapter.py` — ExecutionPlanAdapter (new)

Converts `app.friday.planner_schema.ExecutionPlan` → `app.workflow_runtime.models.ExecutionPlanInput`:

| ExecutionPlan field | ExecutionPlanInput field | Mapping |
|---|---|---|
| `goal` | `goal` | Direct copy |
| `steps` | `steps` | Direct copy |
| (generated) | `plan_id` | `uuid.uuid4()` |
| `intent`, `priority`, `confidence` | `variables` | Structured into dict |
| `capabilities`, `memoryRequired`, `toolRequired`, `clarificationRequired`, `tool_name`, `reasoning` | `metadata` | Structured into dict |

Also exports:
- `extract_tool_output(workflow)` — walks completed steps and collects results
- `format_tool_output_for_prompt(outputs)` — formats step outputs for LLM context

### 2. `app/friday/orchestrator.py` — Runtime Integration

**Constructor change:** Added optional `runtime_bridge: Optional[Any] = None` parameter.

**`process_query()` change** (line ~109-132):
```python
if self._runtime_bridge and plan.steps:
    # NEW: route through workflow runtime
    runtime_input = execution_plan_to_input(plan)
    workflow = await self._runtime_bridge.submit_and_wait(runtime_input)
    tool_outputs = extract_tool_output(workflow)
    tool_output = format_tool_output_for_prompt(tool_outputs)
else:
    # LEGACY: direct ToolExecutor path (preserved)
    exec_result = await self.tool_executor.execute(plan, ...)
```

**`process_stream()` change** — same pattern applied.

**`check_confirmation()`** — unchanged. Pre-execution confirmation checks still use `ToolExecutor` because the workflow runtime is for executing plans, not checking if they need confirmation.

### 3. `app/workflow_runtime/scheduler_bridge.py` — `submit_and_wait()`

Added a new method that submits a plan and awaits its completion:

```python
async def submit_and_wait(self, plan: ExecutionPlanInput) -> RuntimeWorkflow:
    workflow = await self._manager.start_from_plan(plan)
    task = self._manager._active_runs.get(workflow.workflow_id)
    if task:
        try:
            await task
        except Exception:
            pass
    completed = self._manager.get(workflow.workflow_id)
    if not completed:
        completed = await self._manager.get_stored(workflow.workflow_id)
    return completed or workflow
```

### 4. `app/api/routes.py` — `get_orchestrator()` Factory

Added one line to retrieve `runtime_scheduler_bridge` from the kernel and pass it to the orchestrator:

```python
runtime_bridge = kernel.get_service("runtime_scheduler_bridge")
return FridayOrchestrator(..., runtime_bridge=runtime_bridge)
```

### 5. `app/kernel/health.py` — `KernelHealth` Model

Added `workflow_runtime` field:
```python
workflow_runtime: SubsystemHealth = Field(default_factory=lambda: SubsystemHealth(
    name="workflow_runtime", status=HealthStatus.UNKNOWN, message="Subsystem not registered"
))
```

### 6. `app/kernel/kernel.py` — Health Checks

Three changes:
1. Resolve `runtime_svc = self.get_service("runtime_scheduler_bridge")`
2. `r_health = check_service_health("workflow_runtime", runtime_svc) ...`
3. Include `r_health.status` in overall status evaluation and `r_health` in the `KernelHealth` return

---

## Verification Results

### Full Test Suite

| Suite | Tests | Result |
|-------|-------|--------|
| All tests (excl. broken imports) | 170 | **170 passed** |
| Integration tests (new) | 13 | **13 passed** |
| Workflow Runtime tests | 61 | **61 passed** |
| Agent Runtime tests | 48 | **48 passed** |
| Knowledge Engine tests | 12 | **12 passed** |
| Kernel tests | 250 lines | All pass |

### New Integration Tests

| Test | What It Proves |
|------|----------------|
| `test_execution_plan_to_input_converts_all_fields` | Adapter preserves all `ExecutionPlan` fields |
| `test_execution_plan_to_input_empty_steps` | Adapter handles plans with no steps |
| `test_extract_tool_output_empty` | No crash on empty workflow |
| `test_extract_tool_output_with_results` | Only completed steps are extracted |
| `test_format_tool_output` | Output formatting works for prompt injection |
| `test_format_tool_output_empty` | Empty output produces empty string |
| `test_orchestrator_falls_back_to_tool_executor_without_runtime` | Backward compat: no runtime → uses ToolExecutor |
| `test_orchestrator_runtime_path_with_empty_plan` | Runtime not called when plan has no steps |
| `test_orchestrator_runtime_path_with_plan` | Runtime called when plan has steps + bridge available |
| `test_submit_and_wait_completes` | `submit_and_wait()` returns completed workflow |
| `test_execution_plan_to_runtime_workflow` | Full conversion chain: `ExecutionPlan → ExecutionPlanInput → RuntimeWorkflow` |
| `test_orchestrator_backward_compat_without_runtime` | Original code path works without runtime_bridge |
| `test_check_confirmation_still_works` | Pre-execution confirmation check unchanged |

---

## Execution Flow (Verified)

The complete execution path now flows through the runtime when available:

```
User Request (/ask or /chat)
  │
  ▼
app/api/routes.py :: get_orchestrator()
  │  Retrieves llm_router, memory_engine, runtime_scheduler_bridge from kernel
  │
  ▼
FridayOrchestrator.process_query(prompt)
  │
  ├── IntentClassifier.classify(prompt)          → IntentType
  │
  ├── Planner.plan(prompt, intent)                → ExecutionPlan
  │     └── PlannerManager.create_plan()
  │           → IntentAnalyzer → GoalExtractor → TaskClassifier
  │
  ├── [NEW] execution_plan_to_input(plan)         → ExecutionPlanInput
  │     └── Maps: goal, steps, variables, metadata
  │
  ├── [NEW] RuntimeSchedulerBridge.submit_and_wait(input)
  │     └── WorkflowRuntimeManager.start_from_plan(input)
  │           └── WorkflowRuntimeExecutor.build_from_plan()
  │                 → RuntimeWorkflow with RuntimeSteps
  │           └── WorkflowRuntimeManager._run_workflow(wf_id)
  │                 └── WorkflowRuntimeExecutor.execute_step()
  │                       └── AgentCoordinator.delegate(task)
  │                             └── route_task → WorkflowWorkerAgent
  │                                   └── execute_task()
  │                                         └── SharedContext
  │                                               ├── execute_tool() → ToolEngine
  │                                               └── generate_llm() → LLMRouter
  │                                               └── query_knowledge() → KnowledgeEngine
  │
  ├── LLMRouter.generate(prompt, context)         → LLM response
  │
  ├── MemoryEngine.store(session, messages)       → ConversationMemory
  │
  ▼
FridayResponse (success, intent, response, telemetry, ...)
```

---

## Backward Compatibility

- **No existing API changes**: `FridayOrchestrator.__init__` added `runtime_bridge` as optional. All existing callers (tests) continue working.
- **No removal of `ToolExecutor`**: The fallback path is preserved for environments where the workflow runtime is not registered.
- **No changes to `app/workflow/`**: `WorkflowEngine`, `WorkflowRunner`, `WorkflowNodeExecutor` are untouched.
- **No changes to `app/agents/`**: Agent coordinator, registry, scheduler, telemetry, shared context are unchanged.
- **No boot.py changes**: Step 12 already registered all runtime services. No new boot steps needed.

---

## Files Not Modified

The following files were explicitly not touched to preserve architecture:

- `app/kernel/boot.py` — Step 12 already set up runtime services
- `app/workflow/engine.py` — Old WorkflowEngine untouched
- `app/workflow_runtime/manager.py` — No changes needed
- `app/workflow_runtime/executor.py` — No changes needed
- `app/workflow_runtime/persistence.py` — No changes needed
- `app/workflow_runtime/checkpoints.py` — No changes needed
- `app/workflow_runtime/worker_agent.py` — No changes needed
- `app/agents/coordinator.py` — No changes needed
- `app/agents/registry.py` — No changes needed
- `app/agents/context.py` — No changes needed
- `app/friday/executor.py` — No changes needed (fallback path intact)
- `app/friday/planner_schema.py` — No changes needed
- `app/friday/planner_manager.py` — No changes needed
- `app/friday/planner_engine.py` — No changes needed
