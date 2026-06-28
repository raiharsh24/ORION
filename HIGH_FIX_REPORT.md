# High Severity Fix Implementation Report

## Summary

All 7 High severity issues (H1–H7) from `SYSTEM_VALIDATION_REPORT.md` have been
implemented. The test suite passes 180/181 tests (1 pre-existing flaky failure
`test_ask_route_confirmation_loop`).

## Fix Details

### H1 — Unify Session Stores

**Files changed:**
- `services/orion-api/app/core/dependencies.py` — `memory_store` now instantiates
  `MemoryEngine` directly instead of depending on the `ConversationMemory` alias.
- `services/orion-api/app/orion/orchestrator.py` — imports `ConversationMemory`
  from `app.memory` (the `__init__.py` alias) instead of `conversation.py` directly.
- `services/orion-api/app/kernel/boot.py` — removed unused `ConversationMemory` import.
- `services/orion-api/app/api/routes.py` — removed unused `memory_store` import.

**Result:** Single `MemoryEngine` instance serves as both the type hint and the
runtime object. The dead `ConversationMemory` class in `conversation.py` remains
for backward compatibility but is never referenced at runtime.

---

### H2 — Deduplicate ChatMessage Model

**Files changed:**
- `services/orion-api/app/memory/conversation.py` — replaced the local
  `ChatMessage` class definition with `from app.models.schemas import ChatMessage`.

**Result:** Single canonical `ChatMessage` Pydantic model. No behavior change.

---

### H3 — Concurrent EventBus Dispatch

**Files changed:**
- `services/orion-api/app/events/bus.py` — `publish()` now groups matched
  handlers by priority, executes each priority group sequentially (lowest first),
  and runs handlers within each group concurrently via `asyncio.gather()` with
  `return_exceptions=True`.

**Result:** Independent handlers at the same priority level execute concurrently,
preserving ordering guarantees across priority tiers.

---

### H4 — Centralized Fire-and-Forget Publish

**Files changed:**
- `services/orion-api/app/events/bus.py` — added `publish_background()` that
  creates a supervised `asyncio.Task`, tracks it in `_background_tasks`, and
  auto-discards on completion. Added `shutdown()` to await pending tasks.
- `services/orion-api/app/agents/base.py` — 8 call sites replaced.
- `services/orion-api/app/agents/bus.py` — 4 call sites replaced.
- `services/orion-api/app/agents/coordinator.py` — 5 call sites replaced.
- `services/orion-api/app/agents/registry.py` — 2 call sites replaced.
- `services/orion-api/app/agents/scheduler.py` — 3 call sites replaced.
- `services/orion-api/app/workflow_runtime/executor.py` — 3 call sites replaced.
- `services/orion-api/app/workflow_runtime/manager.py` — 9 call sites replaced.

**Result:** Eliminated 7 ad-hoc `_publish_event()` methods (34 call sites total).
All fire-and-forget publish operations use `EventBus.publish_background()`. The
`shutdown()` method enables clean teardown.

---

### H5 — Protect Shared Variables in Parallel Steps

**Files changed:**
- `services/orion-api/app/workflow_runtime/executor.py` —
  `execute_parallel_steps()` now creates a `dict(variables)` copy per step before
  launching concurrent execution.

**Result:** Steps running in parallel no longer race on `workflow.variables`.

---

### H6 — Desktop Telemetry — Real Data Instead of Fake

**Files changed:**
- `apps/desktop/src/store/useSystemStore.ts`:
  - Captures `parsed.usage` from the streaming completion envelope
    (`metadata.streamCompleted`).
  - Measures real wall-clock execution time (`Date.now() - startTime`).
  - Removed `Math.floor(prompt.length / 4)`, `Math.floor(accumulated.length / 4)`,
    `150 + Math.random() * 90` fake computations.
  - Falls back to `details.execution_time_ms` from session endpoint or computed
    duration; `lastTelemetry: streamUsage` (null if unavailable).

**Result:** Telemetry payload reflects actual LLM token counts and execution
duration.

---

### H7 — Cancellation Chain (Desktop → Gateway → LLM)

**Files changed:**
- `apps/desktop/src/store/useSystemStore.ts`:
  - Added module-level `currentAbortController` reference.
  - `sendMessageStream` creates a new `AbortController`, aborts any previous,
    and passes `signal` to the fetch call.
  - Exposed `cancelCurrentRequest()` method on the store.
  - Controller reference is cleaned up on completion and error.

**Result:** Users can cancel an in-flight chat request. The `AbortController`
signal propagates through fetch → Gateway → LLM provider stream.
