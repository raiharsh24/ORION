# Boot Sequence

## Overview

The `BootManager.run_boot_sequence()` method executes 13 sequential steps
with substeps. Each step registers one or more singleton services into the
`FridayServiceContainer`, registers them in the `FridayModuleRegistry`, and
registers their capability in the `FridayCapabilityRegistry`.

## Step Timeline

```
Step 1:  Load Configuration                 (caller-provided)
Step 2:  Initialize Logger                  (trivial)
Step 3:  Initialize Event Bus               ─── event_bus
Step 3a: Phase 3 Intelligence Services      ─── 8 services
Step 3b: Phase 5 Pipeline + Cache           ─── 2 services
Step 4:  Memory Engine                      ─── memory_engine
Step 5:  Knowledge Engine                   ─── knowledge_engine
Step 6:  Planner (legacy)                   ─── planner
Step 7:  Desktop Controller + Tool Registry ─── desktop_controller, tool_registry
Step 7b: Desktop Automation                 ─── desktop_automation
Step 7c: Tool Engine                        ─── tool_engine
Step 7d: Phase 6 Universal Tool Registry    ─── universal_tool_registry
Step 7e: Phase 6 Tool Selection Engine      ─── tool_selection_engine
Step 7f: Phase 6 Tool Execution Engine      ─── tool_execution_engine
Step 7g: Phase 6 Workflow Engine V2         ─── workflow_engine_v2
Step 7h: Phase 6 Mission Engine V2          ─── mission_engine_v2
Step 7i: Phase 6 Capability Registry V2     ─── capability_registry_v2
Step 7j: Phase 6 Capability Resolver        ─── capability_resolver
Step 7k: Phase 7 Plugin SDK                 ─── plugin_registry, plugin_loader
Step 8:  Mission Engine (legacy)            ─── telemetry, history, mission_engine
Step 9:  Workflow Engine (legacy)           ─── workflow_history, workflow_engine
Step 10: Scheduler                          ─── scheduler
Step 10b: LLM Router                        ─── llm_router
Step 11: Multi-Agent Runtime                ─── 6 services
Step 12: Workflow Runtime                   ─── 5 services
Step 13: Voice Subsystem                    ─── 5 services
```

## Registration Pattern

Each service follows this pattern:

```python
# 1. Create instance
service = SomeService(event_bus=event_bus)

# 2. Register in DI container
self._container.register_singleton("service_name", service)

# 3. Register in module registry (enables lifecycle management)
kernel.module_registry.register_module(
    "service_name", "1.0.0", ["dependency_names"], service
)

# 4. Register capability (enables discovery)
kernel.capability_registry.register_capability(
    name="DisplayName",
    module_name="service_name",
    description="What this service does"
)
```

## Startup (LifecycleManager)

After all registrations:

```python
await lifecycle_manager.initialize_all()
await lifecycle_manager.start_all()
```

This calls `start()` on every registered module that has it. The order is
determined by `FridayModuleRegistry` (respects dependency order).

## Shutdown Order

Shutdown reverses the boot order:

```python
await lifecycle_manager.shutdown_all()
```

Then all services are unregistered from the container.

## Health Check Behavior

After boot, `kernel.health()` checks all 28 registered services:

1. Looks up each service by DI key
2. If found and has `health()` → calls it, parses the result
3. If not found → returns `UNKNOWN` with message "Subsystem not registered"
4. Aggregates all statuses → `ERROR` if any `ERROR`, else `WARNING` if any
   `WARNING`, else `HEALTHY`

## Total Service Count

| Category | Count |
|---|---|
| Legacy services (Steps 3–13, excl. Phases 3/5/6/7) | ~20 |
| Phase 3 intelligence services | 8 |
| Phase 5 pipeline + cache | 2 |
| Phase 6 tool + workflow + capability engines | 8 |
| Phase 7 plugin SDK | 2 |
| **Total** | **~40** |
