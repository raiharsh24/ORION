# FRIDAY AI OS — Cognitive Core Architecture (Design)

**Milestone 2 deliverable set.** Design only — no implementation.
**Date:** 2026-07-08
**Status of codebase reviewed:** `services/friday-api/app` (kernel, memory, tools, planner, planning, cognitive, context, intelligence, runtime, api).

This document set designs the **Cognitive Core** — the subsystem that turns FRIDAY from a conversational runtime into a persistent AI Operating System. It is grounded in a full audit of the existing code: most of the required *capability* already exists as partially-wired modules, but it is fragmented across parallel stacks with critical integration gaps. The design therefore emphasizes **reuse + integration**, and explicitly marks what must be **redesigned**.

---

## 0.1 Design principles

1. **Reuse before rebuild.** Every component below maps to an existing module. We integrate and fill gaps; we do not rewrite working code.
2. **One source of truth per concern.** A single Memory Store, a single Vector Store client, a single Tool Registry, a single Permission model, a single Planner interface.
3. **Cognitive Core = kernel service.** Register as `cognitive_core` so it gains lifecycle, health, and dependency ordering for free.
4. **Semantic by default.** Memory retrieval, knowledge graph, and tool discovery must be embedding-driven, not keyword/regex-driven.
5. **Failure is first-class.** The live request path must have the same recovery/monitoring the mission runtime already has.
6. **No silent duplication.** Consolidate the parallel stacks (two planners, two KGs, two embedding managers, three permission models, two capability registries).

---

## 0.2 Reuse-vs-Redesign matrix

| Required capability | Existing (reuse) | Gap / must redesign |
|---|---|---|
| Persistent long-term memory | `memory/engine.py:MemoryEngine`, `memory/store.py:SQLiteStore` (friday_memory.db) | Unify with `memory/conversation.py` (duplicate, delete) |
| Episodic memory | `memory/episodic.py:EpisodicMemory` | Wire to event bus (currently manual) |
| Semantic memory | `friday/vectordb.py:VectorDB` (Chroma) + `friday/knowledge_engine.py` | **Not connected to memory retrieval** — bridge `EmbeddingsManager` → memory |
| Working memory | `memory/schema.py:WorkingMemory`, `memory/manager.py` | Keep; expose per-session scratchpad |
| Memory retrieval | `memory/retriever.py:MemoryRetriever` | **Keyword/recency only** → add vector + hybrid scoring |
| Reflection engine | `cognitive/reflection_v2.py:ReflectionV2`, `runtime/reflection.py:ReflectionEngine` | Unify (two exist); wire into live path |
| Knowledge graph | `memory/graph.py:KnowledgeGraph` + `friday/atlas_*` (ATLAS) | **Two disconnected graphs** → unified `CognitiveGraph` |
| Vector search | `friday/vectordb.py:VectorDB` | Unify the two embedding managers; shared client |
| Context builder | `intelligence/pipeline.py:IntelligencePipeline` + `context/*` + `ranking/`,`budget/`,`compression/` | Already strong; wire into planner + live path |
| Universal tool registry | `tools/registry.py:ToolRegistry`, `tools/base.py:ToolDefinition` | **Empty at runtime** → add `BaseTool→ToolDefinition` adapter + populate |
| Permission model | `tools/permissions.py:PermissionRegistry` | Unify 3 models; make role-aware |
| Tool execution + retry | `tool_execution/executor.py:ToolExecutionEngine` | Make universal registry the source of truth |
| Planner (decompose/select/monitor/recover) | `planner/planning/*`, `cognitive/*`, `runtime/*` | **Not in live /ask path** → integrate; add recovery to live path |
| Mission framework | `mission_engine/`, `runtime/executor.py` | Reuse as planner execution backend |

---

## 0.3 Three critical integration gaps (the real work)

- **GAP-A — Non-semantic memory.** `MemoryRetriever` scores by recency/importance/keyword; `EmbeddingsManager` is never called by the memory path. Chroma is used *only* by the RAG `KnowledgeEngine`. Result: the assistant "remembers" by string match, not meaning.
- **GAP-B — Tool registry is hollow.** `tools.registry.ToolRegistry` is constructed but never populated (no `register()` call exists). The live path uses the legacy `friday.tool_registry` + `ToolEngine.ExecutionManager`. The rich `tool_selection`/`tool_execution`/`capabilities` stack returns 0 candidates.
- **GAP-C — Planners are parallel, not unified; live path has no recovery.** `friday/planner_manager.py` (regex, flat) runs on `/ask`; the rich `planner/planning/` + `cognitive/` stack is only reached via cognitive missions. The live path has no failure recovery, monitoring, or reflection.

The Cognitive Core design resolves A, B, and C by introducing a thin **integration layer** (`cognitive_core`) that wraps the existing modules, adds the missing adapters/bridges, and registers everything as first-class kernel services.

See `01-Cognitive-Core-Architecture.md` for the layered design, and the remaining files for each subsystem.
