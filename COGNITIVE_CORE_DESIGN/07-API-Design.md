# 7. API Design

Principle: **consolidate** the current scattered inspectors (`memory_inspector`, `planner_inspector`, `runtime_inspector`, `cognitive_inspector`, `agent_inspector`) under a cohesive `/cognitive_core` router, while keeping backward-compatible `/api/*` aliases. All endpoints mount at both `/` and `/api` (existing `main.py` convention).

## 7.1 `CognitiveCore` router — `app/api/cognitive_core.py`

```
GET  /cognitive_core/health
POST /cognitive_core/perceive        { query, session_id }  -> retrieved context blocks + working memory summary
POST /cognitive_core/plan            { query, session_id, intent? } -> UnifiedPlan (steps, tools, confidence)
POST /cognitive_core/act             { plan_id | step } -> execution result
POST /cognitive_core/reflect         { mission_id } -> ReflectionV2Report
POST /cognitive_core/remember        { event_type, payload, session_id } -> ack
GET  /cognitive_core/context/{session_id} -> assembled context preview (debug)
```

## 7.2 Memory v2 — extend `app/api/memory_inspector.py`

```
GET  /memory/stats                      (exists)
GET  /memory/search?q=&type=&k=         (exists; now hybrid: keyword+vector+graph)
GET  /memory/entities                   (exists)
GET  /memory/episodic                   (exists)
GET  /memory/learning                   (exists)
GET  /memory/importance/{entry_key}     (NEW) -> importance/decay
POST /memory/forget                     (NEW) { entry_key } -> archive
POST /memory/pin                        (NEW) { entry_key } -> protect from forgetting
GET  /memory/graph?provider=            (exists via atlas; extend provider=cognitive)
```

## 7.3 Tools v2 — NEW `app/api/tools.py`

```
GET    /tools                              -> list ToolDefinition (metadata)
GET    /tools/{id}                         -> ToolDefinition detail
GET    /tools/health                       -> ToolRegistryHealth
GET    /tools/capabilities                 -> capability list (resolved)
POST   /tools/{id}/execute                 -> ad-hoc execute (guarded by permission + sandbox)
GET    /tools/{id}/history                 -> ExecutionHistory
POST   /tools/{id}/health/reset            -> admin: reset error_count
```

## 7.4 Planner v2 — extend `app/api/planner_inspector.py` (rename concept to planner)

```
GET  /planner/plans                        (exists)
GET  /planner/active                       (exists)
GET  /planner/statistics                   (exists)
POST /planner/plan                         (NEW) { objective, session_id } -> decompose + simulate + confidence
POST /planner/{plan_id}/execute           (NEW) -> run via MissionExecutor/ToolExecutionEngine
POST /planner/{plan_id}/recover            (NEW) { failure } -> RecoveryDecision
GET  /planner/recovery                     (exists)
```

## 7.5 Knowledge Graph — extend `app/api/atlas.py`

```
GET /atlas/graph?provider=cognitive       (NEW) unified CognitiveGraph (code + runtime entities + memory)
POST /atlas/entity                         (NEW) explicit entity upsert (runtime)
```

## 7.6 Response envelope (consistent)

Reuse existing `AskResponse`/`StatusToggleResponse` patterns. New endpoints return typed pydantic models:

```python
class RetrievedContext(BaseModel):
    blocks: List[ContextBlock]
    strategy: str
    latency_ms: float

class UnifiedPlan(BaseModel):
    plan_id: str
    goal: str
    steps: List[PlanStep]
    confidence: float
    requires_confirmation: bool
    fallback_plan_id: Optional[str]

class ReflectionReport(BaseModel):
    planner_accuracy: float
    tool_effectiveness: Dict[str, float]
    recommendations: List[str]
```

## 7.7 Auth / scope

- All new endpoints respect `AuthMiddleware` (enabled when `FRIDAY_AUTH_DISABLED=False`).
- Tool execute/pin/forget/reset require `ADMIN`/`ELEVATED` scope via the unified `PermissionRegistry` + `ConfirmationService`.
- Read endpoints (`/memory/search`, `/tools`, `/planner/plans`) require `USER`.

## 7.8 Event contract (reuse existing `FridayEvent` subclasses)

No new event vocabulary required. Cognitive Core subscribes to and emits: `ConversationCompleted`, `ToolCompleted`, `MissionCompleted`, `WorkflowCompleted`, `PlanCreated`, `PlanValidated`, `ToolRegistered`, `ToolHealthChanged`, `ToolExecutionCompleted/Failed`, `MemoryCreated`, `GraphEntityCreated`, `ReflectionStored`. The `cognitive_core` service is registered so these flow through the kernel `event_bus`.
