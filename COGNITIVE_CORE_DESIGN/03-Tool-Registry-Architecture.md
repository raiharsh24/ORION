# 3. Universal Tool Registry Architecture

Fixes **GAP-B** (the universal registry is constructed but never populated; the live path uses the legacy `friday.tool_registry` + `ToolEngine.ExecutionManager`). Reuses `tools/registry.py`, `tools/base.py`, `tool_execution/`, `tool_selection/`, `capabilities/`; adds the missing adapter + boot population + unified permissions.

## 3.1 Current state (audit)

- `tools/registry.py:ToolRegistry` — rich: `ToolDefinition` dataclass, discovery (`search_by_name/description/capability/tags`), health (`update_tool_health`, `registry_health()`), dependency graph, permission passthrough. **Never populated** (no `register()` call exists anywhere).
- `tools/base_tool.py:BaseTool` — the real executable ABC all concrete tools subclass (`execute(**kwargs)`, `requires_confirmation`).
- `tool_selection/` — `ToolSelectionEngine` built on `universal_tool_registry`; returns **0 candidates** because registry is empty.
- `tool_execution/executor.py:ToolExecutionEngine` — has retry/timeout/cancel/dependency-scheduling, but `_execute_single` fails every tool when universal registry is set but empty.
- `tools/permissions.py:PermissionRegistry` — ordinal levels USER<ELEVATED<ADMIN<SYSTEM (role-agnostic).
- Parallel models: `policies/permissions.PermissionManager` (scope-based, unused in exec path), `friday.tool_permission.PermissionManager` (role-based, the one actually used), `capabilities/capability.py:BaseCapability` (orphan).

## 3.2 Target architecture

```mermaid
graph TD
    BOOT[Boot: register all tools] --> ADAPT[BaseTool → ToolDefinition adapter]
    ADAPT --> REG[ToolRegistry  (universal, populated)]
    REG --> PERM[Unified PermissionRegistry]
    REG --> HEALTH[ToolHealth monitor]
    REG --> DISC[Capability Discovery]
    REG --> SEL[ToolSelectionEngine]
    SEL --> EXEC[ToolExecutionEngine]
    EXEC --> HIST[ExecutionHistory]
    EXEC --> RETRY[RetryPolicy]
    EXEC --> SANDBOX[Sandbox/Confirmation]
    EXEC --> DESK[Concrete BaseTool instances]
```

## 3.3 Dynamic registration (the missing piece)

Add `app/tools/adapter.py`:

```python
def register_tool(registry, permission_registry, tool: BaseTool,
                  permission_level: PermissionLevel, category: ToolCategory):
    definition = ToolDefinition(
        id=tool.name, name=tool.name, description=tool.description,
        category=category, version="1.0.0",
        input_schema=tool.args_schema() if hasattr(tool,'args_schema') else {},
        output_schema={}, permission_level=permission_level,
        supports_streaming=getattr(tool,'supports_streaming',False),
        supports_cancellation=getattr(tool,'supports_cancellation',False),
    )
    registry.register(definition)
    permission_registry.register(tool.name, permission_level)
```

Populate at boot (`kernel/boot.py` step 7) from the **already-instantiated** concrete tools in `core/dependencies.py` + `vision_tools` + `desktop_input_tools` (which is currently dead — register it). Also register `workflow_engine` and `mission_runtime` as "capability tools" so the planner can invoke them.

## 3.4 Permissions (unify 3 → 1)

- Keep `tools/permissions.PermissionRegistry` (ordinal) as the single source.
- Add `role` to the request context (`UserContext.role`): viewer/operator/developer/admin mapped to a max `PermissionLevel`.
- `ToolSelectionEngine` filters by `has_permission(tool_id, user_role_level)`.
- **Delete** `policies/permissions.py` and `friday.tool_permission.PermissionManager` (fold their confirmation-token + `requires_confirmation` logic into one `ConfirmationService` used by `ToolExecutionEngine`).
- Confirmation policy: reuse `policies/confirmation.ConfirmationPolicy` (`DESTRUCTIVE_ACTIONS`) + per-tool `BaseTool.requires_confirmation`; terminal tool keeps its `ALLOWED/BLOCKED_COMMANDS`; unify with `policies/safety.SafetyPolicy` and `friday.tool_sandbox.SandboxManager` into a single `SandboxService` (validate command + path).

## 3.5 Capability discovery

- `capabilities/registry.py:CapabilityRegistry` already supports alias resolution + health.
- **Fix fictional links:** `capabilities/defaults.py:DEFAULT_CAPABILITIES` `tool_ids` must equal real registered `ToolDefinition.id`s. Use a single source: each `ToolDefinition` declares `capabilities: List[str]`; capabilities are derived from tools (not hardcoded). `CapabilityResolver.resolve_with_selection` then works end-to-end.
- `tool_selection/selector.py` already does scoring (intent 25 / health 20 / latency 15 / cost 10 / streaming 10 / parallel 10 / permission 5 / category 5). Reuse as-is.

## 3.6 Schema validation

- `ToolDefinition.input_schema` (JSON Schema) validated by `ToolExecutionEngine` before `tool.execute(**args)` (reuse `jsonschema` or pydantic). Reject with `ToolExecutionFailed` + clear message on mismatch.
- `BaseTool` gains an optional `args_schema()` (pydantic model) → converted to JSON Schema by the adapter.

## 3.7 Tool health

- Reuse `tools/health.py:ToolHealth` + `ToolRegistry.update_tool_health`.
- `ToolExecutionEngine` updates health on every call (success/failure/latency). `registry_health()` aggregates → `ToolRegistryHealth`. Surfaced via `GET /tools/health` (new) and existing `/runtime/*` monitors.
- Unhealthy tools are excluded by `SelectionRules.is_healthy` and trigger `_find_fallback` within the same category.

## 3.8 Execution history

- New `ExecutionHistory` (SQLite table `tool_executions` in `friday_memory.db`, or in-memory ring + persisted). Records: `execution_id, tool_id, args_hash, status, latency_ms, retries, error, timestamp, session_id, mission_id`.
- Consumed by `LearningEngine.record_tool_effectiveness` and `AdaptiveLearning` (tool success rates) and `planner/analytics.py:MissionAnalytics`.

## 3.9 Retry policies

- Reuse `tool_execution/executor.py` retry loop (TimeoutError/Exception → retry up to `max_retries`).
- Add declarative `RetryPolicy` on `ToolDefinition` (max_retries, backoff, retry_on=[Exception types], circuit_breaker threshold). `planner/recovery.py:RecoveryPolicies` (retry → alternative_tool → alternative_workflow → ask_user → abort) operates one level above, at the plan/mission scope.

## 3.10 Deletes (dead code)

- `memory/conversation.py` (duplicate session logic) — delete; `engine.py`/`manager.py` are canonical.
- `capabilities/capability.py:BaseCapability` (orphan ABC) — delete.
- `tools/__init__.py` must export `desktop_input_tools` + `vision_tools` so they get registered.

## 3.11 Module → file mapping

| New/changed | File |
|---|---|
| `BaseTool→ToolDefinition` adapter | `app/tools/adapter.py` (new) |
| Boot population | `app/kernel/boot.py` (extend step 7) |
| Unified `ConfirmationService` | `app/tools/confirmation.py` (new, consolidates `friday.tool_permission` + `policies.confirmation`) |
| Unified `SandboxService` | `app/tools/sandbox.py` (new, consolidates `friday.tool_sandbox` + `policies.safety`) |
| `ExecutionHistory` | `app/tools/history.py` (new, persisted to `friday_memory.db`) |
| `RetryPolicy` | `app/tools/base.py:ToolDefinition` extension (field) |
| API | `app/api/tools.py` (new: `/tools`, `/tools/{id}`, `/tools/health`) |
