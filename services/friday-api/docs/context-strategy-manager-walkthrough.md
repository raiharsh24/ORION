# Context Strategy Manager — Phase 4 Sprint 2 Walkthrough

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         FridayKernel                                 │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    EventBus                                   │   │
│  │  IntentAnalyzed ──► StrategyManager ──► StrategyResolved      │   │
│  └──────────┬──────────────────────┬────────────────────────────┘   │
│             │                      │                                │
│  ┌──────────▼──────────┐  ┌───────▼────────────┐                  │
│  │  Intent Analyzer    │  │  StrategyManager    │                  │
│  │  (Phase 4 Sprint 1) │  │  get_strategy(intent)│                  │
│  └─────────────────────┘  └───────┬────────────┘                  │
│                                   │                                │
│  ┌────────────────────────────────▼────────────────────────────┐   │
│  │              ContextStrategy Registry                        │   │
│  │                                                              │   │
│  │  Conversation  Coding  Terminal  Desktop  Browser           │   │
│  │  Workflow      Planning Memory   Search   Vision  Unknown   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### Sequence Diagram

```
User Request
    │
    ▼
RuleBasedIntentAnalyzer.analyze("fix this bug")
    │
    ├─ IntentResult(intent=CODING, confidence=0.95)
    │
    └─ event_bus.publish(IntentAnalyzed)
         │
         ▼
    StrategyManager._on_intent_analyzed(event)
         │
         ├─ intent = IntentType(event.data["intent"])  # CODING
         │
         ├─ strategy = self.get_strategy(CODING)
         │     └─ returns CodingStrategy instance
         │
         ├─ config = strategy.get_config()
         │     └─ StrategyConfig(extractors=[...], token_budget=8192, ...)
         │
         ├─ self._last_resolved = CODING
         │
         └─ event_bus.publish(StrategyResolved)
               topic="StrategyResolved"
               data={
                 "intent": "coding",
                 "strategy_name": "CodingStrategy",
                 "token_budget": 8192
               }
```

## Files

| File | Purpose |
|------|---------|
| `app/context/base.py` | `ContextStrategy` ABC, `StrategyConfig`, `TokenBudget`, `RetrievalPriority`, `CompressionPolicy`, `CachePolicy` |
| `app/context/strategies.py` | 11 concrete strategy classes (one per `IntentType`) |
| `app/context/manager.py` | `StrategyManager` — subscribes to `IntentAnalyzed`, resolves strategies, publishes `StrategyResolved` |
| `app/context/events.py` | `StrategyResolved` FridayEvent subclass |
| `app/context/__init__.py` | Public API exports |
| `app/kernel/boot.py` | Registration (Step 3c) |
| `app/kernel/kernel.py` | Health check integration |
| `app/kernel/health.py` | `KernelHealth.strategy_manager` field |
| `tests/test_context_strategy_manager.py` | 116 tests |

## Strategy Interface

```python
class ContextStrategy(ABC):
    @property
    @abstractmethod
    def intent_type(self) -> IntentType:
        ...

    @abstractmethod
    def get_config(self) -> StrategyConfig:
        ...
```

## Data Classes

```python
@dataclass
class TokenBudget:
    total: int = 4096          # total token allowance
    system: int = 512           # system prompt
    conversation_history: int = 1024  # recent turns
    working_memory: int = 512   # active tool results, current state
    retrieved_context: int = 1024     # RAG / knowledge base results
    instructions: int = 512     # task instructions, constraints
    reserved: int = 512         # buffer for overhead

@dataclass
class RetrievalPriority:
    sources: List[str]          # ordered list of retrieval backends

@dataclass
class CompressionPolicy:
    strategy: str               # "summarize" | "truncate" | "key_point_extraction" | "none"
    max_tokens: int             # max tokens after compression
    threshold: float            # trigger when usage > threshold (0.0–1.0)

@dataclass
class CachePolicy:
    ttl_seconds: int            # how long to cache
    max_entries: int            # max cached items
    invalidation: str           # "lru" | "ttl_only" | "never"

@dataclass
class StrategyConfig:
    extractors: List[str]       # names of required extractors (placeholders)
    token_budget: TokenBudget
    retrieval_priority: RetrievalPriority
    compression_policy: CompressionPolicy
    cache_policy: CachePolicy
```

## Strategy Configuration Matrix

| Intent | Extractors | Budget | Retrieval Priority | Compression | Cache TTL |
|--------|-----------|--------|-------------------|-------------|-----------|
| Conversation | conversation_history, user_preference | 4096 | session → preferences → working | summarize | 60s |
| Coding | code_context, file_tree, recent_changes, terminal_output | 8192 | working → project → knowledge → session | key_point_extraction | 120s |
| Terminal | terminal_output, shell_history, process_list | 4096 | working → session → project | truncate | 30s |
| Desktop | desktop_state, active_window, notification | 4096 | working → preferences → session | truncate | 30s |
| Browser | web_page, browser_state, bookmark | 4096 | session → preferences → working | summarize | 60s |
| Workflow | workflow_state, step_progress, mission_context | 8192 | working → project → mission → knowledge | key_point_extraction | 120s |
| Planning | project_state, milestone, resource | 8192 | project → working → mission → session | key_point_extraction | 300s |
| Memory | long_term_memory, session_history, user_preference | 8192 | session → preferences → project → knowledge | summarize | 300s |
| Search | web_search, knowledge_base, documentation | 4096 | knowledge → web → project → session | summarize | 120s |
| Vision | image_analysis, screen_capture, object_detection | 8192 | working → session → preferences | key_point_extraction | 60s |
| Unknown | general_context | 2048 | session → working | truncate | 30s |

## Event Flow

```
IntentAnalyzed(topic="IntentAnalyzed")
    │
    ▼
StrategyManager._on_intent_analyzed(event)
    │
    ├─ resolves intent from event.data["intent"]
    │
    ├─ calls get_strategy(intent) → ContextStrategy
    │
    ├─ calls strategy.get_config() → StrategyConfig
    │
    ├─ stores self._last_resolved
    │
    └─ publishes StrategyResolved(topic="StrategyResolved")
         data: { intent, strategy_name, token_budget }
```

**Total: 116 tests** — all passing alongside the existing suite of 354 tests (470 total).

## Registration Flow (boot.py Step 3c)

```
EventBus ──► StrategyManager(event_bus)
               │
               ├─ container.register_singleton("strategy_manager", ...)
               │
               ├─ module_registry.register_module("strategy_manager",
               │       "1.0.0", ["event_bus"], strategy_manager)
               │
               └─ capability_registry.register_capability(
                      "ContextStrategy", "strategy_manager", ...)
               
               LifecycleManager calls start()/shutdown()
               
               EventBus subscription:
                 subscribe("IntentAnalyzed", _on_intent_analyzed)
```

## Test Coverage (116 tests)

| Category | Tests | What |
|----------|-------|------|
| Unit — Data Classes | 9 | TokenBudget, RetrievalPriority, CompressionPolicy, CachePolicy, StrategyConfig defaults and custom |
| Unit — Strategy Contracts | 88 | 8 parametrized checks × 11 strategies each: intent_type, config, extractors, budget > 0, budget totals, retrieval, compression, cache |
| Unit — StrategyManager | 9 | init, get_strategy, fallback, idempotency, list, lifecycle, health, null bus, unknown budget comparison |
| Integration — EventBus | 5 | Subscription, multi-intent resolution, last_resolved tracking, no-publish-when-not-running, unknown fallback |
| Regression — Kernel | 6 | Boot includes service, lifecycle via kernel, end-to-end event flow, restart, get_strategy after boot, all 11 accessible |

## Running

```bash
# Targeted
.venv/bin/python -m pytest tests/test_context_strategy_manager.py -v

# Full suite
.venv/bin/python -m pytest -q
```
