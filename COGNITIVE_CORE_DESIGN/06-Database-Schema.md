# 6. Database Schema

Goal: **one SQLite store** (`friday_memory.db`) for all memory/tool/episodic/learning data, **one Chroma** instance with two collections (`friday_knowledge`, `friday_memory`), and **one graph store** (`atlas_graph.db`, reused). Removes the current 3× SQLite + JSON-KV + Chroma-fallback drift. All schemas are additive (no breaking change to existing tables).

## 6.1 SQLite — `friday_memory.db` (existing + additions)

Existing `memory_kv(key TEXT PK, value TEXT)` is retained as the generic KV for `session:`, `user:`, `project:`, `episodic:`, `consolidated:`, `learning:`, `graph:entity:`, `graph:relation:` (per audit). Add:

```sql
-- Tool execution history (GAP-B §3.8)
CREATE TABLE IF NOT EXISTS tool_executions (
    execution_id   TEXT PRIMARY KEY,
    tool_id        TEXT NOT NULL,
    session_id     TEXT,
    mission_id     TEXT,
    args_hash      TEXT,
    status         TEXT,            -- success|failed|timeout|cancelled
    latency_ms     REAL,
    retries        INTEGER,
    error          TEXT,
    created_at     REAL
);
CREATE INDEX IF NOT EXISTS idx_tool_exec_tool ON tool_executions(tool_id);
CREATE INDEX IF NOT EXISTS idx_tool_exec_session ON tool_executions(session_id);

-- Forgetting/archive (§2.11)
CREATE TABLE IF NOT EXISTS memory_archive (
    id             TEXT PRIMARY KEY,
    original_key   TEXT,
    payload        TEXT,            -- JSON of the archived MemoryEntry
    archived_at    REAL,
    reason         TEXT             -- decay|ttl|user_request
);

-- Unified importance/decay bookkeeping (optional denormalized index for fast forgetting scans)
CREATE TABLE IF NOT EXISTS memory_importance (
    entry_key      TEXT PRIMARY KEY,
    importance     REAL,
    last_accessed  REAL,
    decay          REAL,
    consolidated   INTEGER,
    FOREIGN KEY(entry_key) REFERENCES memory_kv(key)
);
```

## 6.2 Chroma — single client, two collections

Unify via `friday/vectordb.py:VectorDB` (already tries Chroma, falls back to JSON). Configure two collections:

| Collection | Purpose | Source |
|---|---|---|
| `friday_knowledge` | Document/RAG chunks (existing) | `KnowledgeEngine` |
| `friday_memory` (NEW) | Memory entries / episodic / graph-entity embeddings | `SemanticStore` (§2.5) |

```python
# Conceptual
kb = VectorDB(persist_dir)                 # existing
memory_vec = VectorDB(persist_dir, collection="friday_memory")  # NEW
```

No SQL schema (Chroma manages its own store). Each memory point metadata: `{type, entry_key, session_id, importance, created_at}`.

## 6.3 Graph — `atlas_graph.db` (reused, extended)

Reuse `friday/atlas_store.py` schema (`metadata`, `snapshots`, `nodes`, `edges`, `graph_statistics`). The `nodes.embeddings BLOB` column **already exists but is unused** — populate it for semantic graph search (§2.9). Add a runtime-entity table for dynamic (non-code) entities:

```sql
CREATE TABLE IF NOT EXISTS runtime_entities (
    id          TEXT PRIMARY KEY,
    type        TEXT,            -- person|goal|mission|tool|file|preference
    title       TEXT,
    description TEXT,
    embedding   BLOB,            -- optional
    created_at  REAL,
    source_event TEXT
);
CREATE TABLE IF NOT EXISTS runtime_relations (
    source      TEXT,
    target      TEXT,
    type        TEXT,
    weight      REAL,
    created_at  REAL,
    PRIMARY KEY(source, target, type)
);
```

## 6.4 Migration / consistency notes

- Existing `memory_kv` + `missions` tables stay (Alembic-managed). New tables added via the same `run_database_migrations` (`app/kernel/migrate.py`).
- `AtlasStore` currently uses raw `CREATE TABLE IF NOT EXISTS` (not Alembic) — bring it under `migrate.py` for one migration path.
- Connection management: today three manual `sqlite3.connect` patterns. Add a single `DBPool` (or `sqlite3` with `check_same_thread=False` + lock, already the pattern in `SQLiteStore`) shared by `MemoryStore`, tool history, archive. Avoid connection-per-call.
- Vector store connection is already singleton-ish via `VectorDB` instances; ensure `KnowledgeEngine` and `SemanticStore` share one `PersistentClient` (Chroma allows only one client per path — make `VectorDB` a kernel singleton).
