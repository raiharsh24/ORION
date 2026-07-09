# 8. Implementation Order & Complexity Estimates

Design only — this is the recommended build sequence. Ordered to close the **three critical gaps (A/B/C)** first (they unblock everything else), then assemble the `cognitive_core` facade, then harden.

## 8.1 Phased plan

### Phase 0 — Foundations (no behavior change)
- **P0.1** Register `cognitive_core` + `cognitive_engine`/`agent_orchestrator` as kernel singletons (fixes lazy-per-request gap).
- **P0.2** Unify embedding client: one `EmbeddingProvider`; deprecate `memory/embeddings.py`.
- **P0.3** Delete dead code (`memory/conversation.py`, `capabilities/capability.py:BaseCapability`, unregistered `desktop_input_tools` import, `planner/planner.py` stub).
- **P0.4** Single `VectorDB` kernel singleton; `friday_memory` collection created.

### Phase 1 — GAP-B: Tool Registry population (highest leverage)
- **P1.1** `BaseTool→ToolDefinition` adapter + boot registration of all concrete tools (incl. `desktop_input_tools`, `vision_tools`).
- **P1.2** Unified `PermissionRegistry` + `ConfirmationService` + `SandboxService` (fold `friday.tool_permission`, `policies.*`).
- **P1.3** `ExecutionHistory` (SQLite) + health wiring in `ToolExecutionEngine`.
- **P1.4** Fix `capabilities/defaults.py` tool_ids → real ids; capability discovery works.
- **P1.5** New `app/api/tools.py`.

### Phase 2 — GAP-A: Semantic Memory retrieval
- **P2.1** `SemanticStore` over Chroma `friday_memory` collection; embed on every LTM/episodic/graph write.
- **P2.2** `RetrievalService` + `HybridRetriever` (keyword + vector + graph).
- **P2.3** `ImportanceScorer`; `ForgettingPolicy` + `ArchiveStore`; periodic consolidation extended to episodic.

### Phase 3 — GAP-C: Unified Planner + live-path recovery
- **P3.1** `UnifiedPlanner` facade; wire `FridayOrchestrator.process_query`/`process_stream` to it.
- **P3.2** LLM-assisted decomposition for complex intents; fast heuristic for simple ones.
- **P3.3** Recovery wrapper on live path (`RecoveryPolicies` + `Supervisor`).
- **P3.4** Post-execution `ReflectionV2` + `AdaptiveLearning` loop.

### Phase 4 — Knowledge Graph unification (GAP-D)
- **P4.1** `CognitiveGraph` over `atlas_graph.db` + runtime entities; auto-populate from events.
- **P4.2** Populate `nodes.embeddings BLOB`; semantic graph search.
- **P4.3** `GraphRetriever` feeds hybrid retriever.

### Phase 5 — Facade, API, hardening
- **P5.1** `CognitiveCore.perceive/plan/act/reflect/remember` complete.
- **P5.2** `app/api/cognitive_core.py` + extend memory/planner/atlas APIs.
- **P5.3** DB migrations for `tool_executions`, `memory_archive`, `runtime_entities`.
- **P5.4** End-to-end tests + benchmarks; remove debug prints.

## 8.2 Complexity & effort estimates

| # | Module | Complexity | Est. effort | Risk | Reuse level |
|---|---|---|---|---|---|
| P0.1 | kernel singleton registration | S | 0.5d | Low | High (exists, just register) |
| P0.2 | unify EmbeddingProvider | M | 1d | Low | High |
| P0.3 | delete dead code | S | 0.5d | Low | — |
| P0.4 | VectorDB singleton + collection | S | 0.5d | Low | High |
| P1.1 | Tool adapter + boot population | M | 2d | Med | High (registry exists) |
| P1.2 | unified permission/confirm/sandbox | L | 3d | Med | Med |
| P1.3 | ExecutionHistory + health | M | 1.5d | Low | High |
| P1.4 | capability tool_ids fix | S | 0.5d | Low | High |
| P1.5 | `/tools` API | S | 1d | Low | High |
| P2.1 | SemanticStore + embedding writes | M | 2d | Med | High (VectorDB exists) |
| P2.2 | HybridRetriever + RetrievalService | L | 3d | Med | Med (MemoryRetriever exists) |
| P2.3 | Importance/Forgetting/Archive | M | 2d | Med | Med |
| P3.1 | UnifiedPlanner facade | L | 3d | High | Med (planner/planning exist) |
| P3.2 | live-path decomposition | L | 3d | High | Med |
| P3.3 | recovery wrapper | M | 2d | Med | High (RecoveryPolicies/Supervisor exist) |
| P3.4 | reflection loop | M | 1.5d | Low | High |
| P4.1 | CognitiveGraph | L | 3d | Med | Med (both KGs exist) |
| P4.2 | graph embeddings | M | 1.5d | Low | High (column exists) |
| P4.3 | GraphRetriever | M | 1.5d | Low | Med |
| P5.1 | CognitiveCore facade | M | 2d | Med | High |
| P5.2 | cognitive_core API + extensions | M | 2d | Low | High |
| P5.3 | DB migrations | S | 1d | Low | High |
| P5.4 | tests + benchmarks | L | 3d | Med | — |

**Totals:** ~44 person-days (~9 weeks for 1 engineer, or ~3 weeks for a 3-person team). Complexity is dominated by **integration**, not net-new code — most modules already exist and only need wiring/adapters.

## 8.3 Critical-path dependencies

```
P0 (foundations) ─┬─> P1 (tools) ──────────────┐
                  ├─> P2 (semantic memory) ────┤
                  └─> P4 (graph) ──────────────┤
                                                ├─> P3 (planner+recovery)
                                                └─> P5 (facade+API)
```

P1, P2, P4 can run **in parallel** after P0. P3 and P5 depend on P1 (tools) + P2 (retrieval). The single highest-risk item is **P3.2** (live-path LLM decomposition) — recommend a feature flag (`COGNITIVE_PLANNER=on`) to roll it out behind the fast heuristic.

## 8.4 Definition of done (milestone exit)

- [ ] Memory retrieval is hybrid (keyword+semantic+graph) and measurable.
- [ ] Universal Tool Registry is populated; `ToolSelectionEngine` returns real candidates; selection/execution end-to-end works.
- [ ] Live `/ask` path has failure recovery + monitoring + reflection.
- [ ] Single `cognitive_core` kernel service, health-reported, lifecycle-managed.
- [ ] Two-KG drift resolved into `CognitiveGraph`.
- [ ] One embedding client, one permission model, no dead/duplicate modules.
- [ ] New APIs (`/cognitive_core`, `/tools`) present and auth-scoped.
- [ ] DB migrations applied; no unmanaged SQLite connections.
- [ ] Integration tests + benchmarks green.
