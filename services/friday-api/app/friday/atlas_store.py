import os
import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from loguru import logger

class AtlasStore:
    """
    Manages persistent SQLite storage for the ATLAS Knowledge Graph,
    supporting schema versioning, incremental snapshots, and instant rollbacks.
    """
    SCHEMA_VERSION = 1

    def __init__(self, db_path: Optional[str] = None) -> None:
        if not db_path:
            # Default to Friday KB path
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            kb_dir = os.path.join(base_dir, ".friday_kb")
            os.makedirs(kb_dir, exist_ok=True)
            db_path = os.path.join(kb_dir, "atlas_graph.db")

        self.db_path = db_path
        self.initialize_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize_db(self) -> None:
        """Creates database schema tables and initializes version metadata."""
        logger.info(f"Initializing ATLAS graph store at '{self.db_path}'...")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Metadata
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    schema_version INTEGER PRIMARY KEY,
                    generated_at TEXT,
                    workspace_id TEXT,
                    active_snapshot_id TEXT
                )
            """)

            # 2. Snapshots
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    created_at TEXT,
                    status TEXT,
                    error_msg TEXT
                )
            """)

            # 3. Nodes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT,
                    snapshot_id TEXT,
                    title TEXT,
                    description TEXT,
                    type TEXT,
                    category TEXT,
                    tags TEXT,
                    metadata TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    importance REAL,
                    status TEXT,
                    embeddings BLOB,
                    PRIMARY KEY (id, snapshot_id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_snapshot ON nodes(snapshot_id)")

            # 4. Edges
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    source TEXT,
                    target TEXT,
                    snapshot_id TEXT,
                    type TEXT,
                    weight REAL,
                    confidence REAL,
                    metadata TEXT,
                    PRIMARY KEY (source, target, snapshot_id, type)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_edges_snapshot ON edges(snapshot_id)")

            # 5. Statistics
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS graph_statistics (
                    snapshot_id TEXT PRIMARY KEY,
                    node_count INTEGER,
                    edge_count INTEGER,
                    duration_seconds REAL,
                    cache_hit_count INTEGER,
                    cache_miss_count INTEGER
                )
            """)

            # Initialize metadata if not present
            cursor.execute("SELECT schema_version FROM metadata WHERE schema_version = ?", (self.SCHEMA_VERSION,))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO metadata (schema_version, generated_at, workspace_id, active_snapshot_id) VALUES (?, ?, ?, ?)",
                    (self.SCHEMA_VERSION, datetime.utcnow().isoformat(), "friday_workspace", None)
                )
            conn.commit()

    def get_active_snapshot_id(self) -> Optional[str]:
        """Retrieves the active snapshot ID from metadata."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT active_snapshot_id FROM metadata LIMIT 1").fetchone()
            return row["active_snapshot_id"] if row else None

    def set_active_snapshot_id(self, snapshot_id: str) -> None:
        """Updates the active snapshot pointer in database metadata."""
        with self._get_connection() as conn:
            conn.execute("UPDATE metadata SET active_snapshot_id = ?, generated_at = ?", (snapshot_id, datetime.utcnow().isoformat()))
            conn.commit()

    def create_snapshot(self, snapshot_id: str) -> None:
        """Registers a new pending snapshot in the tracking table."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO snapshots (snapshot_id, created_at, status, error_msg) VALUES (?, ?, ?, ?)",
                (snapshot_id, datetime.utcnow().isoformat(), "PENDING", None)
            )
            conn.commit()

    def complete_snapshot(self, snapshot_id: str, status: str, error_msg: Optional[str] = None) -> None:
        """Updates the status of a snapshot (e.g. SUCCESS or FAILED)."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE snapshots SET status = ?, error_msg = ? WHERE snapshot_id = ?",
                (status, error_msg, snapshot_id)
            )
            conn.commit()

    def delete_snapshot(self, snapshot_id: str) -> None:
        """Cleans up nodes and edges associated with a snapshot (useful on rollback)."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM nodes WHERE snapshot_id = ?", (snapshot_id,))
            conn.execute("DELETE FROM edges WHERE snapshot_id = ?", (snapshot_id,))
            conn.execute("DELETE FROM snapshots WHERE snapshot_id = ?", (snapshot_id,))
            conn.commit()

    def get_snapshots_list(self) -> List[Dict[str, Any]]:
        """Retrieves a list of all successful snapshots chronologically."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT snapshot_id, created_at, status FROM snapshots WHERE status = 'SUCCESS' ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    def insert_nodes(self, snapshot_id: str, nodes_list: List[Dict[str, Any]]) -> None:
        """Inserts a list of graph nodes associated with a snapshot."""
        if not nodes_list:
            return
        
        with self._get_connection() as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO nodes (
                    id, snapshot_id, title, description, type, category,
                    tags, metadata, created_at, updated_at, importance, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    n["id"],
                    snapshot_id,
                    n.get("title", ""),
                    n.get("description", ""),
                    n.get("type", "unknown"),
                    n.get("category", "General"),
                    json.dumps(n.get("tags", [])),
                    json.dumps(n.get("metadata", {})),
                    n.get("createdAt", datetime.utcnow().isoformat()),
                    n.get("updatedAt", datetime.utcnow().isoformat()),
                    n.get("importance", 0.5),
                    n.get("status", "HEALTHY")
                ) for n in nodes_list
            ])
            conn.commit()

    def insert_edges(self, snapshot_id: str, edges_list: List[Dict[str, Any]]) -> None:
        """Inserts a list of relationship edges associated with a snapshot."""
        if not edges_list:
            return

        with self._get_connection() as conn:
            conn.executemany("""
                INSERT OR REPLACE INTO edges (
                    source, target, snapshot_id, type, weight, confidence, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    e["source"],
                    e["target"],
                    snapshot_id,
                    e.get("type", "dependency"),
                    e.get("weight", 1.0),
                    e.get("confidence", 1.0),
                    json.dumps(e.get("metadata", {}))
                ) for e in edges_list
            ])
            conn.commit()

    def save_graph_statistics(self, snapshot_id: str, stats: Dict[str, Any]) -> None:
        """Persists run execution statistics."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO graph_statistics (
                    snapshot_id, node_count, edge_count, duration_seconds,
                    cache_hit_count, cache_miss_count
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                snapshot_id,
                stats.get("node_count", 0),
                stats.get("edge_count", 0),
                stats.get("duration_seconds", 0.0),
                stats.get("cache_hit_count", 0),
                stats.get("cache_miss_count", 0)
            ))
            conn.commit()

    def get_graph_data(self, snapshot_id: str) -> Dict[str, Any]:
        """Loads and structures all graph data for a target snapshot."""
        nodes = []
        links = []

        with self._get_connection() as conn:
            # Load nodes
            node_rows = conn.execute("SELECT * FROM nodes WHERE snapshot_id = ?", (snapshot_id,)).fetchall()
            for r in node_rows:
                nodes.append({
                    "id": r["id"],
                    "title": r["title"],
                    "description": r["description"],
                    "type": r["type"],
                    "category": r["category"],
                    "tags": json.loads(r["tags"]),
                    "metadata": json.loads(r["metadata"]),
                    "createdAt": r["created_at"],
                    "updatedAt": r["updated_at"],
                    "importance": r["importance"],
                    "status": r["status"]
                })

            # Load edges
            edge_rows = conn.execute("SELECT * FROM edges WHERE snapshot_id = ?", (snapshot_id,)).fetchall()
            for r in edge_rows:
                links.append({
                    "source": r["source"],
                    "target": r["target"],
                    "type": r["type"],
                    "weight": r["weight"],
                    "confidence": r["confidence"],
                    "metadata": json.loads(r["metadata"])
                })

        return {
            "nodes": nodes,
            "links": links
        }

    def get_health_stats(self) -> Dict[str, Any]:
        """Aggregates metrics and diagnostics for the health status dashboard."""
        stats = {
            "node_count": 0,
            "edge_count": 0,
            "active_snapshot_id": None,
            "last_indexing_duration": 0.0,
            "recent_errors": [],
            "cache_status": "NOMINAL"
        }
        
        try:
            active_id = self.get_active_snapshot_id()
            stats["active_snapshot_id"] = active_id
            
            if active_id:
                with self._get_connection() as conn:
                    # Node and edge counts
                    stats["node_count"] = conn.execute("SELECT COUNT(*) FROM nodes WHERE snapshot_id = ?", (active_id,)).fetchone()[0]
                    stats["edge_count"] = conn.execute("SELECT COUNT(*) FROM edges WHERE snapshot_id = ?", (active_id,)).fetchone()[0]
                    
                    # Duration statistics
                    stat_row = conn.execute("SELECT duration_seconds FROM graph_statistics WHERE snapshot_id = ?", (active_id,)).fetchone()
                    if stat_row:
                        stats["last_indexing_duration"] = stat_row["duration_seconds"]

            # Load recent failures
            with self._get_connection() as conn:
                error_rows = conn.execute("SELECT snapshot_id, created_at, error_msg FROM snapshots WHERE status = 'FAILED' ORDER BY created_at DESC LIMIT 5").fetchall()
                stats["recent_errors"] = [
                    {"snapshot_id": r["snapshot_id"], "timestamp": r["created_at"], "error": r["error_msg"]}
                    for r in error_rows
                ]
        except Exception as e:
            logger.error(f"Failed to fetch graph store health stats: {str(e)}")
            stats["cache_status"] = "ERROR"
            
        return stats
