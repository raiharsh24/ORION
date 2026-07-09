# Phase 1 — Execution Flow Audit

## Current Pipeline (as traced through code)

```
User Request (HTTP POST /ask or /chat)
  │
  ▼
app/api/routes.py
  ├── POST /ask  → orchestrator.process_query()
  └── POST /chat → orchestrator.check_confirmation()
                    ├── true  → return confirmation response
                    ├── stream → orchestrator.process_stream()
                    └── false → orchestrator.process_query()
```

## FridayOrchestrator.process_query() — Full Trace

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Event: ConversationReceived (fire-and-forget)                │
├─────────────────────────────────────────────────────────────────┤
│ 2. IntentClassifier.classify(prompt) → IntentType               │
│    [app/friday/intent.py]                                        │
├─────────────────────────────────────────────────────────────────┤
│ 3. [AUTONOMOUS_GOAL shortcut]                                   │
│    → MissionRuntime.submit_background() → return response       │
│    Bypasses planner, tools, LLM entirely for this intent         │
├─────────────────────────────────────────────────────────────────┤
│ 4. Planner.plan(prompt, intent) → ExecutionPlan                  │
│    [app/friday/planner.py → PlannerEngine → PlannerManager]      │
│    ├── IntentAnalyzer.analyze()                                  │
│    ├── GoalExtractor.extract()                                   │
│    ├── CapabilityResolver.resolve_required_capabilities()        │
│    ├── ClarificationManager.check_clarification()                │
│    ├── TaskClassifier.classify_steps() → plan steps              │
│    ├── PlanValidator.validate()                                   │
│    └── Backward-compat: maps steps → tool_name + args per intent │
├─────────────────────────────────────────────────────────────────┤
│ 5. [If plan]: Tool Execution                                     │
│    ├── PATH A: Workflow Runtime (if _runtime_bridge + steps)     │
│    │   ├── execution_plan_to_input(plan) → ExecutionPlanInput    │
│    │   ├── _runtime_bridge.submit_and_wait()                     │
│    │   └── extract_tool_output() + format_tool_output_for_prompt │
│    │   [Note: RuntimeSchedulerBridge is registered in boot but   │
│    │    may not be properly connected — bridge is optional]       │
│    │                                                              │
│    └── PATH B: Direct ToolExecutor (fallback)                    │
│        ├── ToolExecutor.execute(plan)                            │
│        │   ├── → ToolEngine._manager.execute_tool() (kernel)     │
│        │   └── → _fallback_execute() (no kernel)                 │
│        └── Result: tool_output string                            │
├─────────────────────────────────────────────────────────────────┤
│ 6. Cognitive Core Enrichment (optional)                          │
│    CognitiveCore.retrieve_relevant_context(prompt, top_k=3)      │
│    ├── SemanticStore.search() → semantic chunks                  │
│    ├── CognitiveGraph.graph_context() → graph entities           │
│    └── MemoryRetriever.retrieve() → memory chunks                │
├─────────────────────────────────────────────────────────────────┤
│ 7. Context & History Assembly                                    │
│    ├── SystemContext() (platform, status)                        │
│    ├── Memory.get_or_create_session(session_id)                  │
│    ├── Memory.get_history_string() → conversation history        │
│    ├── ToolRegistry.list_tools() → available tools               │
│    ├── Vision context from session.context["last_vision"]        │
│    └── Cognitive context from step 6                             │
├─────────────────────────────────────────────────────────────────┤
│ 8. Prompt Assembly (PromptManager.format_prompt())               │
│    ├── system_instruction (with tool output + vision + cognitive)│
│    ├── user_message (original prompt)                            │
│    ├── history (conversation history string)                     │
│    ├── available_tools                                           │
│    └── session_metadata                                          │
├─────────────────────────────────────────────────────────────────┤
│ 9. LLM Generation                                                │
│    LLMRouter.get_provider(provider_name).generate(full_prompt)   │
│    [app/llm/router.py → GeminiAdapter (default)]                 │
├─────────────────────────────────────────────────────────────────┤
│ 10. Memory Update                                                │
│     ├── Memory.add_message(session_id, "user", prompt)           │
│     ├── Memory.add_message(session_id, "assistant", response)    │
│     └── Memory.update_context(session_id, intent)                │
├─────────────────────────────────────────────────────────────────┤
│ 11. Event: ConversationCompleted (fire-and-forget)               │
├─────────────────────────────────────────────────────────────────┤
│ 12. Return FridayResponse (success, intent, response, telemetry) │
└─────────────────────────────────────────────────────────────────┘
```

## Duplicated Orchestrations

### 1. CognitiveCore.process_with_cognition()
- **File:** `app/cognitive_core/core.py:46`
- Has its own independent pipeline: `UnifiedPlanner.plan()` → `CognitiveGraph.graph_context()` → `SemanticStore.search()`
- `FridayOrchestrator` already calls `cognitive_core.retrieve_relevant_context()` — but CognitiveCore's `process_with_cognition()` is never called from the orchestrator
- The `UnifiedPlanner` inside CognitiveCore duplicates `PlannerManager` with an additional cognitive path (via `PlanningEngine.create_goal()` + `generate_plan()`)

### 2. MissionRuntime → Orchestrator
- **File:** `app/runtime/orchestrator.py:95`
- Has its own complete lifecycle: planning → capability resolution → tool selection → workflow generation → execution → reflection → memory
- This replicates the same stages that `FridayOrchestrator.process_query()` performs
- When `AUTONOMOUS_GOAL` intent is detected, the orchestrator bypasses entirely and delegates to `MissionRuntime`

### 3. ToolExecutionEngine bypassed
- **File:** `app/tool_execution/executor.py`
- Phase 6 `ToolExecutionEngine` supports: retry, timeout, cancellation tokens, sequential/parallel execution
- But `FridayOrchestrator` → `ToolExecutor` → `ToolEngine._manager.execute_tool()` bypasses this entirely
- `ToolExecutionEngine` is only used by `WorkflowEngineV2` and `MissionRuntime.Orchestrator`

### 4. Three capability registries
- `app/capabilities/registry.py` (ABC-based)
- `app/kernel/capability.py` (`FridayCapabilityRegistry`)
- `app/friday/capability_registry.py` (Pydantic-based)
- All with different schemas, no synchronization — as identified in validation report

### 5. Planner duplication
- `PlannerManager` — used by `PlannerEngine` → `FridayOrchestrator`
- `UnifiedPlanner` — used by `CognitiveCore`, wraps `PlannerManager` with cognitive fallback
- `PlanningEngine` — Phase 8 cognitive planning, used by `UnifiedPlanner._cognitive_plan()`

### 6. Workflow Runtime disconnected
- `WorkflowRuntimeManager`, `WorkflowRuntimeExecutor`, `RuntimeSchedulerBridge` — fully implemented (61 tests) but never invoked
- The `_runtime_bridge` parameter in `FridayOrchestrator` exists but the bridge may not be connected properly
- No HTTP routes for workflow runtime

### 7. Event bus with orphaned subscribers
- 11 event topics published but have zero production subscribers
- Workflow Runtime events all published but never subscribed to
- ToolEngine's 4 event handlers are stubs that only log

## Key Disconnects

| From | To | Status |
|------|----|--------|
| FastAPI routes | FridayOrchestrator | ✅ Connected |
| FridayOrchestrator | IntentClassifier | ✅ Connected |
| FridayOrchestrator | PlannerEngine | ✅ Connected |
| FridayOrchestrator | ToolExecutor | ✅ Connected |
| FridayOrchestrator | ToolExecutionEngine | ❌ Bypassed |
| FridayOrchestrator | LLMRouter | ✅ Connected |
| FridayOrchestrator | MemoryEngine | ✅ Connected |
| FridayOrchestrator | CognitiveCore | ✅ Connected (read-only) |
| FridayOrchestrator | WorkflowRuntime | ❌ Not connected |
| FridayOrchestrator | PluginRuntime | ❌ Not connected |
| FridayOrchestrator | ToolSelectionEngine | ❌ Not connected |
| FridayOrchestrator | MissionRuntime | ✅ (AUTONOMOUS_GOAL only) |
| CognitiveCore | UnifiedPlanner | ✅ Connected |
| CognitiveCore | CognitiveGraph | ✅ Connected |
| MissionRuntime | ToolExecutionEngine | ✅ Connected |
| MissionRuntime | PlanningEngine | ✅ Connected |
| MissionRuntime | ToolSelectionEngine | ✅ Connected |

## Gap Analysis for Unified Engine

The Unified Execution Engine must bridge:
1. **ToolExecutionEngine** (retry, timeout, cancellation, progress events) → currently only used by WorkflowEngineV2
2. **ToolSelectionEngine** (deterministic selection, scoring, fallback) → currently only used by MissionRuntime
3. **PluginRuntime** (sandboxed execution) → currently not used by any request path
4. **CognitiveCore** (semantic + graph enrichment) → currently bolted on as optional step 6
5. **WorkflowRuntime** (step-based execution) → completely disconnected
6. **Shared execution context** → currently each stage rebuilds its own state
7. **Cancellation propagation** → ToolExecutionEngine supports it but orchestrator doesn't propagate
8. **Streaming events** → only at the LLM response level, not during planning/execution
