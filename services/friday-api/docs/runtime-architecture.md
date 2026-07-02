# Mission Runtime — Architecture

## Design Principles

1. **Thin orchestrator** — the runtime does not reimplement planning, execution,
   or agent logic. It chains existing subsystems through a unified lifecycle.
2. **State-machine driven** — all mission state changes flow through a single
   validated state machine, ensuring invariants are enforced.
3. **Recovery-first** — timeouts, failures, and retries are first-class concepts.
4. **Observability built-in** — every mission produces telemetry, metrics, and a
   reflection report.
5. **Stdlib-only** — no external dependencies.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                   MissionRuntime (facade)                │
│  submit_and_run()  metrics()  telemetry_summary()       │
│  health()                                                │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                   Orchestrator                           │
│  submit_request() → run_lifecycle() → archive_mission()  │
│  pause_mission()  resume_mission()  list_missions()      │
│  health()                                                │
└────┬──────┬──────┬──────┬──────┬──────┬──────┬─────────┘
     │      │      │      │      │      │      │
     ▼      ▼      ▼      ▼      ▼      ▼      ▼
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐
│State │ │Dispatch│ │Exec. │ │Super-│ │Refl. │ │Tele- │ │Metrics   │
│Mach. │ │       │ │utor  │ │visor │ │Engine│ │metry │ │          │
└──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────────┘
```

## State Machine

```
        ┌──────────┐
        │ created  │
        └────┬─────┘
             │
        ┌────▼─────┐
        │ planning │
        └────┬─────┘
             │
   ┌─────────▼─────────┐
   │      waiting      │
   └─────────┬─────────┘
             │
        ┌────▼─────┐
        │  ready   │
        └────┬─────┘
             │
   ┌─────────▼─────────┐     ┌──────────┐
   │      running      │◄────│  paused  │
   └──┬──────┬──────┬──┘     └──────────┘
      │      │      │
      ▼      ▼      ▼
  ┌──────┐ ┌──────┐ ┌───────────┐
  │compl.│ │failed│ │recovering │
  └──┬───┘ └──┬───┘ └─────┬─────┘
     │       │            │
     ▼       ▼            │
  ┌──────┐ ┌──────┐       │
  │arch. │ │arch. │◄──────┘
  └──────┘ └──────┘
```

## Dispatcher Architecture

```
                    ┌──────────────┐
                    │  Mission     │
                    │  user_request│
                    └──────┬───────┘
                           │
              ┌────────────▼────────────┐
              │     Dispatcher          │
              │  dispatch(mission)      │
              │  → DispatchDecision     │
              │    .strategy            │
              │    .agent_ids           │
              │    .reason              │
              └────┬───────┬───────┬────┘
                   │       │       │
        ┌──────────▼┐ ┌────▼────┐ ┌▼──────────┐
        │ Keyword   │ │Metadata │ │ Default   │
        │ Match     │ │Override │ │ (workflow) │
        └───────────┘ └─────────┘ └───────────┘
```

## Metrics Architecture

```
TelemetryCollector             RuntimeMetrics
┌──────────────────┐          ┌──────────────────┐
│ Per-mission      │  snap()  │ Aggregated       │
│ ┌──────────────┐ │─────────►│ .total_missions  │
│ │ MissionTele. │ │          │ .avg_latency     │
│ │ .latency     │ │          │ .total_retries   │
│ │ .retries     │ │          │ .failure_causes  │
│ │ .utilization │ │          │ .stage_latencies │
│ └──────────────┘ │          └──────────────────┘
└──────────────────┘
```

## Reflection Architecture

```
Mission + ExecutionResult
         │
         ▼
┌────────────────────┐
│ ReflectionEngine   │
│                    │
│ 1. Bottleneck      │──► List[Bottleneck]
│    detection       │
│                    │
│ 2. Lesson          │──► List[Lesson]
│    extraction      │    (performance, failure, success)
│                    │
│ 3. Experience      │──► List[Experience]
│    storage         │    (stored in _experiences)
└────────────────────┘
```

## Data Flow: Full Mission Lifecycle

```
User Request
     │
     ▼
Orchestrator.submit_request()
     │
     ├──→ Create Mission(id, request, intent)
     │
     ▼
Orchestrator.run_lifecycle(mission)
     │
     ├──→ [State: created → planning]
     │     resolve() → planning_engine.plan()
     │     [State: planning → ready]
     │
     ├──→ Dispatcher.dispatch(mission)
     │     → DispatchDecision(strategy, agents, reason)
     │
     ├──→ MissionExecutor.execute_mission(mission)
     │     │
     │     ├──→ [State: ready → running]
     │     ├──→ strategy: single/parallel/workflow/tool/plugin
     │     ├──→ checkpoint after each stage
     │     ├──→ [State: running → completed|failed]
     │     │
     │     └──→ ExecutionResult(success, duration, stages)
     │
     ├──→ Supervisor.monitor(timeout, failures)
     │     → auto-recover if needed
     │
     ├──→ ReflectionEngine.reflect(mission, result)
     │     → ReflectionReport(lessons, bottlenecks)
     │
     └──→ [State: → archived]
```

## Service Registration

In `boot.py` (Step 7r):

```python
runtime_svc = RuntimeService(runtime)
_kernel.register_module(
    name="mission_runtime",
    version="9.0.0",
    service=runtime_svc,
    depends=["planning_engine"],
)
kernel_di.register("mission_runtime", runtime)
```

## Health Model

```
RuntimeHealth:
  status: healthy | degraded | unhealthy
  running_missions: int
  completed_missions: int
  failed_missions: int
  average_duration_ms: float
  total_retries: int
  total_recoveries: int
  uptime_hours: float
  checked_at: datetime
```

## Counting

| Metric | Count |
|--------|-------|
| Files | 13 |
| Events | 7 |
| States | 10 |
| Transitions | 17 |
| Dispatch strategies | 5 |
| Test count | 74 |
