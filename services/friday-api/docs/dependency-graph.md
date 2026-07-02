# Dependency Injection Graph

## Container

`FridayServiceContainer` — singleton registry keyed by string name.
`FridayModuleRegistry` — tracks lifecycle metadata per module.

## Dependency Order (topological)

```
event_bus                            Step 3
  │
  ├── intent_analyzer                Step 3a
  ├── strategy_manager               Step 3a
  ├── extractor_registry             Step 3a
  ├── context_ranker                 Step 3a
  ├── token_allocator                Step 3a
  ├── context_validator              Step 3a
  ├── context_compressor             Step 3a
  ├── prompt_assembler               Step 3a
  ├── pipeline_orchestrator          Step 3b
  ├── context_cache                  Step 3b
  ├── universal_tool_registry        Step 7d
  ├── capability_registry_v2         Step 7i
  │
  ├── memory_engine                  Step 4
  │
  ├── knowledge_engine               Step 5
  │
  ├── planner                        Step 6
  │
  ├── desktop_controller             Step 7
  ├── tool_registry (legacy)         Step 7
  │
  ├── desktop_automation             Step 7b
  │
  ├── tool_engine                    Step 7c
  │
  ├── plugin_registry                Step 7k
  ├── plugin_loader                  Step 7k
  │
  ├── telemetry                      Step 8
  ├── history                        Step 8
  ├── mission_engine (legacy)        Step 8
  │
  ├── workflow_history               Step 9
  ├── workflow_engine (legacy)       Step 9
  │
  ├── scheduler                      Step 10
  │
  ├── llm_router                     Step 10b
  │
  ├── agent_message_bus              Step 11
  ├── agent_registry                 Step 11
  ├── agent_scheduler                Step 11
  ├── agent_telemetry                Step 11
  ├── shared_context                 Step 11
  ├── agent_coordinator              Step 11
  │
  ├── workflow_persistence           Step 12
  ├── checkpoint_manager             Step 12
  ├── workflow_worker_agent          Step 12
  ├── workflow_runtime_executor      Step 12
  ├── workflow_runtime_manager       Step 12
  ├── runtime_scheduler_bridge       Step 12
  │
  ├── voice_state_machine            Step 13
  ├── tts_provider_registry          Step 13
  ├── tts_coordinator                Step 13
  ├── voice_output_manager           Step 13
  ├── voice_manager                  Step 13
```

## Phase 6 Subgraph

```
universal_tool_registry ──────────────┐
  (event_bus only)                    │
                                      │
tool_selection_engine ◄───────────────┘
  depends: universal_tool_registry
  depends: event_bus
              │
              ├── capability_resolver
              │     depends: capability_registry_v2
              │     depends: tool_selection_engine
              │     depends: event_bus
              │
              │     capability_registry_v2
              │       depends: event_bus
              │
tool_registry (legacy) ───────────────┐
                                      │
tool_execution_engine ◄───────────────┤
  depends: tool_registry (legacy)     │
  depends: universal_tool_registry    │
  depends: event_bus                  │
              │                       │
              ▼                       │
workflow_engine_v2 ◄──────────────────┘
  depends: tool_execution_engine
  depends: event_bus
              │
              ▼
mission_engine_v2
  depends: workflow_engine_v2
  depends: event_bus
  (also uses MissionStore, CheckpointManager, MissionPlanner)
```

## Lifecycle

All services with `start()`/`shutdown()` lifecycle methods are managed by
`FridayLifecycleManager`. The lifecycle manager calls `initialize_all()`
followed by `start_all()` during boot, and `shutdown_all()` in reverse
topological order during shutdown.

## Cross-layer Dependencies

| Layer | Depends On |
|---|---|
| Phase 3 | `event_bus` |
| Phase 5 | `event_bus` |
| Phase 6 | `event_bus`, `tool_registry` (legacy) |
| Phase 7 | `event_bus` |
| Legacy | `event_bus`, various internal deps |
