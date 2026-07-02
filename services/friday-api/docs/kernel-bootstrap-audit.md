# Kernel Bootstrap Audit

## Summary

The kernel bootstrap (`boot.py`, `kernel.py`, `health.py`) was reverted by a
stash conflict, losing all Phase 3–6 service registrations. This audit
documents what was restored and the verification results.

## What Changed

### `app/kernel/boot.py`

| Change | Description |
|---|---|
| Step 3a | Phase 3 Intelligence Pipeline services (8 services) |
| Step 3b | Phase 5 Pipeline Orchestrator + Context Cache |
| Steps 7d–7j | Phase 6 services (6 engines + 2 registries) |
| Step 7k | Renamed from 7d (Plugin SDK, Phase 7) |

Pre-existing steps (1–3, 4–7c, 8–13) were left unchanged.

### `app/kernel/health.py`

Added 17 health fields to `KernelHealth`:

- Phase 3: `intent_analyzer`, `strategy_manager`, `extractor_registry`,
  `context_ranker`, `token_allocator`, `context_validator`,
  `context_compressor`, `prompt_assembler`
- Phase 5: `pipeline_orchestrator`
- Phase 6: `universal_tool_registry`, `tool_selection_engine`,
  `tool_execution_engine`, `workflow_engine_v2`, `mission_engine_v2`,
  `capability_registry_v2`, `capability_resolver`

Also fixed `check_service_health()` to case-normalize status strings
(`"healthy"` → `"HEALTHY"`), which affected all Phase 6 services.

### `app/kernel/kernel.py`

Added health check lookups, health check variables, health monitor reports,
and KernelHealth fields for all Phase 3, 5, and 6 services. Also added
`w_health`, `s_health`, `l_health` to the `statuses` list (they were
previously missing from overall health computation).

## Services Restored by Phase

### Phase 3 (8 services)

| DI Key | Class | Module |
|---|---|---|
| `intent_analyzer` | `RuleBasedIntentAnalyzer` | `app.intent.analyzer` |
| `strategy_manager` | `StrategyManager` | `app.context.manager` |
| `extractor_registry` | `ExtractorRegistry` | `app.extraction.registry` |
| `context_ranker` | `ContextRanker` | `app.ranking.ranker` |
| `token_allocator` | `AdaptiveTokenBudgetAllocator` | `app.budget.allocator` |
| `context_validator` | `ContextValidator` | `app.validation.validator` |
| `context_compressor` | `ContextCompressor` | `app.compression.compressor` |
| `prompt_assembler` | `PromptAssembler` | `app.assembly.assembler` |

The `extractor_registry` is also populated with 9 default extractors
(`MemoryExtractor`, `KnowledgeExtractor`, `WorkflowExtractor`,
`DesktopExtractor`, `BrowserExtractor`, `TerminalExtractor`,
`MissionExtractor`, `VoiceExtractor`, `SystemStateExtractor`).

### Phase 5 (2 services)

| DI Key | Class | Module |
|---|---|---|
| `pipeline_orchestrator` | `IntelligencePipeline` | `app.intelligence.pipeline` |
| `context_cache` | `ContextCache` | `app.cache.cache` |

### Phase 6 (8 services)

| DI Key | Class | Module |
|---|---|---|
| `universal_tool_registry` | `ToolRegistry` | `app.tools.registry` |
| `tool_selection_engine` | `ToolSelectionEngine` | `app.tool_selection.selector` |
| `tool_execution_engine` | `ToolExecutionEngine` | `app.tool_execution.executor` |
| `workflow_engine_v2` | `WorkflowExecutor` | `app.workflow_engine.executor` |
| `mission_engine_v2` | `MissionExecutor` | `app.mission_engine.executor` |
| `capability_registry_v2` | `CapabilityRegistry` | `app.capabilities.registry` |
| `capability_resolver` | `CapabilityResolver` | `app.capabilities.resolver` |

The `capability_registry_v2` is populated with 11 default capabilities
from `DEFAULT_CAPABILITIES()`.

### Phase 7 (2 services)

| DI Key | Class | Module |
|---|---|---|
| `plugin_registry` | `PluginRegistry` | `app.plugins.registry` |
| `plugin_loader` | `PluginLoader` | `app.plugins.loader` |

## Pre-existing Legacy Services (unchanged)

| DI Key | Class | Step |
|---|---|---|
| `event_bus` | `EventBus` | 3 |
| `memory_engine` | `memory_store` | 4 |
| `knowledge_engine` | `KnowledgeEngine` | 5 |
| `planner` | `Planner` | 6 |
| `desktop_controller` | `desktop_controller` | 7 |
| `tool_registry` | `ToolRegistry` (legacy) | 7 |
| `desktop_automation` | `DesktopAutomationService` | 7b |
| `tool_engine` | `ToolEngine` | 7c |
| `telemetry` | `MissionTelemetry` | 8 |
| `history` | `MissionHistory` | 8 |
| `mission_engine` | `MissionManager` (legacy) | 8 |
| `workflow_history` | `WorkflowHistory` | 9 |
| `workflow_engine` | `WorkflowEngine` (legacy) | 9 |
| `scheduler` | `FridayScheduler` | 10 |
| `llm_router` | `LLMRouter` | 10b |
| Agent subsystem | (6 services) | 11 |
| Workflow Runtime | (5 services) | 12 |
| Voice subsystem | (5 services) | 13 |

## Verification

- **Phase 3 kernel integration tests**: 43 passed
- **Phase 5 kernel integration tests**: 4 passed
- **Phase 6 (no dedicated kernel tests)**: Indirectly verified by boot health
- **Phase 7 plugin SDK tests**: 78 passed
- **Kernel boot/shutdown/restart**: passes
- **Full regression**: **1208 passed, 0 failed**

## Risk Register

| Risk | Status | Mitigation |
|---|---|---|
| Service name collision | None | Each Phase 6 service uses a distinct DI key |
| Circular dependencies | None | Dependency graph is a DAG |
| Singleton lifecycle | Clean | All services have `start()`/`shutdown()` |
| Health enum mismatch | Fixed | `check_service_health` case-normalizes |
| Legacy services disrupted | Unchanged | No edits to existing boot steps |
