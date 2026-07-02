# Intent Analyzer — Phase 4 Sprint 1 Walkthrough

## Architecture

```
┌───────────────────────────────────────────────────────────┐
│                    FridayKernel                           │
│  ┌───────────────────────────────────────────────────┐   │
│  │            LifecycleManager                        │   │
│  │  start_all() → shutdown_all()                     │   │
│  └──────────────┬────────────────────────────────────┘   │
│                 │                                        │
│  ┌──────────────▼────────────────────────────────────┐   │
│  │         FridayModuleRegistry                      │   │
│  │  intent_analyzer [dep: event_bus]                 │   │
│  └───────────────────────────────────────────────────┘   │
│                 │                                        │
│  ┌──────────────▼────────────────────────────────────┐   │
│  │         FridayServiceContainer (DI)               │   │
│  │  register_singleton("intent_analyzer", ...)       │   │
│  └───────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────┘
         │
         │ publishes
         ▼
┌─────────────────────┐     ┌────────────────────────┐
│      EventBus       │────►│   IntentAnalyzed event  │
│                     │     │  topic: "IntentAnalyzed"│
│                     │     │  data: {                │
│                     │     │    request, intent,     │
│                     │     │    confidence, reasoning│
│                     │     │  }                      │
└─────────────────────┘     └────────────────────────┘
```

### Files

| File | Purpose |
|------|---------|
| `app/intent/types.py` | `IntentType` enum (11 values) |
| `app/intent/events.py` | `IntentAnalyzed` FridayEvent subclass |
| `app/intent/analyzer.py` | `RuleBasedIntentAnalyzer`, `IntentResult` |
| `app/intent/__init__.py` | Public API exports |
| `app/kernel/boot.py` | Registration (Step 3b) |
| `app/kernel/kernel.py` | Health check integration |
| `app/kernel/health.py` | `KernelHealth.intent_analyzer` field |
| `tests/test_intent_analyzer.py` | 124 tests (unit/integration/regression) |

## Registration Flow (boot.py Step 3b)

```
EventBus created ──► RuleBasedIntentAnalyzer(event_bus) ──►
  │                                                         │
  ├─ container.register_singleton("intent_analyzer", ...)   │
  ├─ module_registry.register_module("intent_analyzer",     │
  │       "1.0.0", ["event_bus"], analyzer)                 │
  └─ capability_registry.register_capability(                │
         "IntentAnalyzer", "intent_analyzer", ...)          │
                                                            ▼
                                              LifecycleManager calls
                                              analyzer.start()/shutdown()
```

## Event Flow

```
User Request
    │
    ▼
RuleBasedIntentAnalyzer.analyze("hello how are you")
    │
    ├─ _sync_analyze(): pattern-matching → IntentResult
    │     intent=CONVERSATION, confidence=0.25, reasoning="..."
    │
    └─ event_bus.publish(IntentAnalyzed(request, intent, confidence, reasoning))
         │
         ▼
    Subscribers on topic "IntentAnalyzed" receive the event
```

## Rule Engine Design

- **Input**: Lowercased, stripped text
- **Scoring**: Per intent, sum of `weight × match_count` across all patterns
- **Patterns**: Precompiled `re.compile()` regexps; `findall()` counts all occurrences
- **Winner**: Intent with highest total score
- **Confidence**: `min(best_score / 10.0, 1.0)`
- **Unknown fallback**: Returned when no patterns match any intent

### Intent Categories & Pattern Counts

| Intent | Patterns | Representative Keywords |
|--------|----------|-----------------------|
| CONVERSATION | 11 | hello, thanks, how are you, who are you |
| CODING | 17 | function, bug, git, def, api, docker, python |
| TERMINAL | 11 | ls, cd, grep, ssh, curl, vim, chmod |
| DESKTOP | 11 | open app, window, minimize, screenshot, click |
| BROWSER | 7 | search for, navigate to, url, browse |
| WORKFLOW | 8 | workflow, pipeline, ci pipeline, cron, when-then |
| PLANNING | 9 | goal, roadmap, sprint, okr, milestone |
| MEMORY | 8 | remember, you said, recall, save this |
| SEARCH | 9 | how to, what is, search, find, define |
| VISION | 9 | image, screenshot, see, detect, ocr |

### Performance

All queries process in **under 2ms** (test verifies < 5ms across 100 iterations).

**Total: 124 tests** — all passing alongside the existing suite of 230 tests (354 total).

## Test Coverage (124 tests)

| Category | Tests | What |
|----------|-------|------|
| Unit — Enum | 2 | IntentType member count, value types |
| Unit — Intent Classification | 98 parametrized | Each intent type with multiple representative queries |
| Unit — Edge Cases & Behavior | 16 | Empty, whitespace, case, bounds, reasoning, perf, lifecycle, health, null bus, domain specifics |
| Integration — EventBus | 4 | Event publication, field correctness, no-publish-when-not-running, null bus safety |
| Regression — Kernel | 4 | Boot, lifecycle, end-to-end flow, restart persistence |

## Running

```bash
# Targeted
.venv/bin/python -m pytest tests/test_intent_analyzer.py -v

# Full suite
.venv/bin/python -m pytest -q
```
