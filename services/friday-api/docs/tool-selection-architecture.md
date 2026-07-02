# Tool Selection Engine — Architecture

## Design Goals

1. **Deterministic selection** — no LLM or agent reasoning; pure rule + score.
2. **Health-aware** — prefers healthy tools, rejects unavailable ones.
3. **Permission-aware** — respects hierarchical permission model.
4. **Fallback chain** — if primary fails, best alternative is chosen.
5. **Optimizer-aware** — respects optimizer recommendations and penalties.
6. **Event-driven** — full event lifecycle for observability.
7. **Telemetry** — tracks selection count, fallback rate, average latency.

## Data Flow

```
ToolRegistry ──► ToolSelectionEngine ──► ToolSelectionResult
                     │
            ┌────────┼────────┐
            ▼        ▼        ▼
          Rules    Scorer   Events
```

## Architecture

```
┌──────────────────────────────────────────────────┐
│                ToolSelectionEngine                │
│                                                   │
│  select(context)                                  │
│    │                                              │
│    ├── filter_candidates() ─────► SelectionRules  │
│    │                                • is_available│
│    │                                • has_permission
│    │                                • matches_category
│    │                                              │
│    ├── score_candidates() ───────► ToolScorer     │
│    │                                • intent match│
│    │                                • health      │
│    │                                • latency     │
│    │                                • cost       │
│    │                                • streaming  │
│    │                                • parallel   │
│    │                                • permission │
│    │                                • category   │
│    │                                • optimizer  │
│    │                                              │
│    ├── try_select() ──────────────► SelectionRules │
│    │                                • is_healthy  │
│    │                                • dependencies│
│    │                                              │
│    ├── find_fallback() ───────────► ToolRegistry  │
│    │                                • same category
│    │                                • best alternative
│    │                                              │
│    └── publish_events() ─────────► EventBus      │
│                                     • ToolSelectionStarted
│                                     • ToolSelected
│                                     • FallbackToolSelected
│                                     • ToolSelectionCompleted
└──────────────────────────────────────────────────┘
```

## Scoring Formula

```
score(tool) =
    intent_match_score    (max 25)
    + health_score        (max 20)
    + latency_score       (max 15)
    + cost_score          (max 10)
    + streaming_score     (max 10)
    + parallel_score      (max 10)
    + permission_score    (max  5)
    + category_score      (max  5)
    + optimizer_boost     (max 15)
    + optimizer_penalty   (min -15)
──────────────────────────────────
    Maximum: 115
```

## File Layout

```
app/tool_selection/
├── __init__.py        # Package exports
├── base.py            # ToolSelectionContext, SelectedTool, ToolSelectionResult
├── rules.py           # SelectionRules (filtering and validation)
├── score.py           # ToolScorer (weighted scoring of candidates)
├── events.py          # 4 event types
├── selector.py        # ToolSelectionEngine (main orchestrator)
```

## Dependency Graph

```
ToolSelectionEngine
├── ToolRegistry (from app.tools)
├── EventBus (from app.events)
├── SelectionRules (stateless)
├── ToolScorer (per-selection instance)
└── Event types (published externally)
```

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Intent match via string containment | Simple, deterministic; no NLP needed at selection time |
| Early filter + score + sort | Efficient: cheap filters first, expensive scoring only on candidates |
| Fallback by same category | Ensures functional equivalence in the fallback chain |
| Optimizer boost/penalty as scores | Keeps optimizer influence measurable and comparable |
| Confidence = selected/total | Simple metric; 0 when nothing selected, 1 when all primary |
| Async `select()` | Future-proof for async health checks or registry lookups |
| Static scoring weights | Deterministic; weights can be tuned via constants |
