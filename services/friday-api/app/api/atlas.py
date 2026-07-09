import os
import json
import sqlite3
import subprocess
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from loguru import logger

from app.friday.atlas_indexer import AtlasIndexer
from app.friday.atlas_store import AtlasStore
from app.kernel.kernel import FridayKernel

router = APIRouter()

# Share a single global indexer singleton
_indexer_instance: Optional[AtlasIndexer] = None

def get_indexer() -> AtlasIndexer:
    global _indexer_instance
    if _indexer_instance is None:
        _indexer_instance = AtlasIndexer()
    return _indexer_instance

class TriggerResponse(BaseModel):
    status: str
    message: str

class HealthStatsResponse(BaseModel):
    node_count: int
    edge_count: int
    active_snapshot_id: Optional[str]
    last_indexing_duration: float
    cache_status: str
    recent_errors: List[Dict[str, Any]]

# Helper to fetch active memory database connection
def get_memory_db_path() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, ".friday_kb", "friday_memory.db")

@router.post("/atlas/index/trigger", response_model=TriggerResponse)
async def trigger_indexing(background_tasks: BackgroundTasks) -> TriggerResponse:
    """
    Manually triggers incremental workspace indexing in a background task.
    """
    indexer = get_indexer()
    res = await indexer.trigger_indexing(background_tasks)
    return TriggerResponse(status=res["status"], message=res["message"])

@router.post("/atlas/index/cancel", response_model=TriggerResponse)
async def cancel_indexing() -> TriggerResponse:
    """
    Cancels the currently running indexing job.
    """
    indexer = get_indexer()
    res = indexer.cancel_indexing()
    return TriggerResponse(status=res["status"], message=res["message"])

@router.get("/atlas/index/progress")
async def index_progress():
    """
    Exposes a Server-Sent Events (SSE) stream yielding live progress ticks from the indexer.
    """
    async def event_generator():
        queue = asyncio.Queue()
        indexer = get_indexer()
        indexer.register_listener(queue)
        try:
            # Yield initial connect event
            yield f"data: {json.dumps({'status': 'CONNECTED', 'progress': 0.0, 'message': 'SSE listener registered.'})}\n\n"
            
            while True:
                payload = await queue.get()
                yield f"data: {json.dumps(payload)}\n\n"
                if payload.get("status") in ("COMPLETED", "FAILED", "CANCELLED"):
                    break
        except asyncio.CancelledError:
            pass
        finally:
            indexer.unregister_listener(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/atlas/health", response_model=HealthStatsResponse)
async def get_health() -> HealthStatsResponse:
    """
    Exposes indexing metrics, node counts, cache status, and error logs.
    """
    indexer = get_indexer()
    stats = indexer.store.get_health_stats()
    return HealthStatsResponse(
        node_count=stats.get("node_count", 0),
        edge_count=stats.get("edge_count", 0),
        active_snapshot_id=stats.get("active_snapshot_id"),
        last_indexing_duration=stats.get("last_indexing_duration", 0.0),
        cache_status=stats.get("cache_status", "NOMINAL"),
        recent_errors=stats.get("recent_errors", [])
    )

@router.get("/atlas/snapshots", response_model=List[Dict[str, Any]])
async def list_snapshots() -> List[Dict[str, Any]]:
    """
    Retrieves all chronologically completed indexing snapshot records.
    """
    indexer = get_indexer()
    return indexer.store.get_snapshots_list()

@router.get("/atlas/graph")
async def get_graph(provider: str = "knowledge", snapshot_id: Optional[str] = None):
    """
    Retrieves and slices the active graph snapshot matching the requested provider category.
    """
    indexer = get_indexer()
    store = indexer.store
    active_id = snapshot_id or store.get_active_snapshot_id()

    # Case 1: Load SQLite memory database entries directly
    if provider == "memory":
        return get_live_memory_graph()

    # Case 2: Load workflow plans directly from the local store
    if provider == "workflow":
        return get_live_workflows_graph()

    # Case 3: Load chronological commit branches via Git
    if provider == "timeline":
        return get_live_git_timeline_graph()

    # Case 4: Default fallback. Return file & codebase dependency slices from the active snapshot database
    if not active_id:
        # Return empty response if no indexing run has succeeded yet
        return {"nodes": [], "links": []}

    graph = store.get_graph_data(active_id)
    return slice_snapshot_graph(graph, provider)

def slice_snapshot_graph(graph: Dict[str, Any], provider: str) -> Dict[str, Any]:
    """Filters code/document nodes according to category queries."""
    nodes = graph.get("nodes", [])
    links = graph.get("links", [])

    filtered_nodes = []
    filtered_node_ids = set()

    for n in nodes:
        ntype = n.get("type")
        ncat = n.get("category")
        
        # 1. Knowledge provider: manifest, folders, and markdown files
        if provider == "knowledge":
            if ntype in ("manifest", "folder", "document", "research"):
                filtered_nodes.append(n)
                filtered_node_ids.add(n["id"])
                
        # 2. Code provider: code files, classes, interfaces, routes, functions
        elif provider == "code":
            if ntype in ("code", "class", "interface", "function", "route"):
                filtered_nodes.append(n)
                filtered_node_ids.add(n["id"])

        # 3. Document provider: markdown files
        elif provider == "document":
            if ntype in ("document", "manifest"):
                filtered_nodes.append(n)
                filtered_node_ids.add(n["id"])

        # 4. Research provider: research articles and notes
        elif provider == "research":
            if ntype == "research":
                filtered_nodes.append(n)
                filtered_node_ids.add(n["id"])

        # 5. Agent provider: system manifest and active agent sub-nodes
        elif provider == "agent":
            if ntype == "manifest" or n.get("id").startswith("agent_"):
                filtered_nodes.append(n)
                filtered_node_ids.add(n["id"])

    # Filter links to connect only retained nodes
    filtered_links = []
    for l in links:
        src = l["source"]
        tgt = l["target"]
        if src in filtered_node_ids and tgt in filtered_node_ids:
            filtered_links.append(l)

    return {
        "nodes": filtered_nodes,
        "links": filtered_links
    }

def get_live_memory_graph() -> Dict[str, Any]:
    """Queries friday_memory.db directly to build live memory nodes and links."""
    db_path = get_memory_db_path()
    nodes = []
    links = []

    # Default root anchor
    nodes.append({
        "id": "agent_memory",
        "title": "Cognitive Memory Root",
        "description": "Active session checkpoints and episodic memory",
        "type": "manifest",
        "category": "Memory",
        "tags": ["memory", "root"],
        "metadata": {},
        "createdAt": datetime.utcnow().isoformat(),
        "updatedAt": datetime.utcnow().isoformat(),
        "importance": 0.8,
        "status": "HEALTHY"
    })

    if not os.path.exists(db_path):
        return {"nodes": nodes, "links": links}

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Load memory entities
        cursor.execute("SELECT key, value FROM memory_kv")
        rows = cursor.fetchall()
        
        for r in rows:
            key = r["key"]
            val_str = r["value"]
            try:
                val = json.loads(val_str)
            except Exception:
                continue

            if key.startswith("graph:entity:"):
                # Knowledge Graph Entity
                entity_id = val.get("id", key)
                nodes.append({
                    "id": f"entity:{entity_id}",
                    "title": val.get("name", entity_id),
                    "description": f"Entity Type: {val.get('type', 'unknown')}",
                    "type": "memory",
                    "category": "Memory",
                    "tags": ["entity", val.get("type", "unknown")],
                    "metadata": val.get("properties", {}),
                    "createdAt": val.get("created_at", datetime.utcnow().isoformat()),
                    "updatedAt": val.get("updated_at", datetime.utcnow().isoformat()),
                    "importance": 0.5,
                    "status": "HEALTHY"
                })
                # Link to root
                links.append({
                    "source": "agent_memory",
                    "target": f"entity:{entity_id}",
                    "type": "memory",
                    "weight": 1.0,
                    "confidence": 1.0,
                    "metadata": {}
                })

            elif key.startswith("graph:relation:"):
                # Knowledge Graph Relationship
                links.append({
                    "source": f"entity:{val.get('source_id')}",
                    "target": f"entity:{val.get('target_id')}",
                    "type": val.get("type", "related_to"),
                    "weight": 1.0,
                    "confidence": 1.0,
                    "metadata": val.get("properties", {})
                })

            elif key.startswith("session:"):
                # Chat sessions
                session_id = val.get("session_id", key.split(":")[-1])
                nodes.append({
                    "id": f"session:{session_id}",
                    "title": f"Session: {session_id[:8]}",
                    "description": val.get("summary") or "Active chat history log",
                    "type": "memory",
                    "category": "Memory",
                    "tags": ["session"],
                    "metadata": {"messages_count": len(val.get("messages", [])), "updated_at": val.get("updated_at")},
                    "createdAt": val.get("created_at", datetime.utcnow().isoformat()),
                    "updatedAt": val.get("updated_at", datetime.utcnow().isoformat()),
                    "importance": 0.6,
                    "status": "HEALTHY"
                })
                links.append({
                    "source": "agent_memory",
                    "target": f"session:{session_id}",
                    "type": "memory",
                    "weight": 1.0,
                    "confidence": 1.0,
                    "metadata": {}
                })

        conn.close()
    except Exception as e:
        logger.error(f"Failed to load memory graph from SQLite: {str(e)}")

    return {"nodes": nodes, "links": links}

def get_live_workflows_graph() -> Dict[str, Any]:
    """Loads workflow definitions directly from the workspace pipeline store."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    workflows_dir = os.path.join(base_dir, ".friday_kb", "workflows")
    
    nodes = []
    links = []

    # Workflow anchor
    nodes.append({
        "id": "agent_automation",
        "title": "Workflow Runtime Root",
        "description": "Core task scheduler and active automation loops",
        "type": "manifest",
        "category": "Workflow",
        "tags": ["workflow", "root"],
        "metadata": {},
        "createdAt": datetime.utcnow().isoformat(),
        "updatedAt": datetime.utcnow().isoformat(),
        "importance": 0.8,
        "status": "HEALTHY"
    })

    if not os.path.exists(workflows_dir):
        return {"nodes": nodes, "links": links}

    try:
        for f in os.listdir(workflows_dir):
            if f.startswith("plan-") and f.endswith(".json"):
                full_path = os.path.join(workflows_dir, f)
                try:
                    with open(full_path, "r", encoding="utf-8") as file:
                        wf = json.load(file)
                        
                    wf_id = wf.get("id") or wf.get("workflow_id")
                    wf_name = wf.get("name", wf_id)
                    
                    if not wf_id:
                        continue

                    # Workflow pipeline Node
                    nodes.append({
                        "id": f"wf:{wf_id}",
                        "title": wf_name,
                        "description": wf.get("description", "Registered pipeline"),
                        "type": "workflow",
                        "category": "Workflow",
                        "tags": ["workflow-plan", wf.get("flow_type", "SEQUENTIAL")],
                        "metadata": {"flow_type": wf.get("flow_type"), "tags": wf.get("tags", [])},
                        "createdAt": wf.get("created_at", datetime.utcnow().isoformat()),
                        "updatedAt": wf.get("updated_at", datetime.utcnow().isoformat()),
                        "importance": 0.6,
                        "status": "HEALTHY"
                    })
                    links.append({
                        "source": "agent_automation",
                        "target": f"wf:{wf_id}",
                        "type": "workflow",
                        "weight": 1.0,
                        "confidence": 1.0,
                        "metadata": {}
                    })

                    # Map nodes inside workflow
                    nodes_data = wf.get("nodes", {})
                    if isinstance(nodes_data, dict):
                        for node_id, node in nodes_data.items():
                            task_node_id = f"wf_task:{wf_id}#{node_id}"
                            nodes.append({
                                "id": task_node_id,
                                "title": node.get("name", node_id),
                                "description": f"Step Type: {node.get('type', 'action')}",
                                "type": "function",
                                "category": "Workflow",
                                "tags": ["task-step"],
                                "metadata": {"status": node.get("status"), "inputs": list(node.get("inputs", {}).keys())},
                                "createdAt": wf.get("created_at", datetime.utcnow().isoformat()),
                                "updatedAt": wf.get("updated_at", datetime.utcnow().isoformat()),
                                "importance": 0.4,
                                "status": "HEALTHY"
                            })
                            # Link task step to workflow parent
                            links.append({
                                "source": f"wf:{wf_id}",
                                "target": task_node_id,
                                "type": "containment",
                                "weight": 1.1,
                                "confidence": 1.0,
                                "metadata": {}
                            })
                            # Sequential dependencies
                            for dep in node.get("depends_on", []):
                                links.append({
                                    "source": f"wf_task:{wf_id}#{dep}",
                                    "target": task_node_id,
                                    "type": "workflow",
                                    "weight": 1.0,
                                    "confidence": 1.0,
                                    "metadata": {"label": "depends"}
                                })

                except Exception as file_err:
                    logger.error(f"Failed to parse workflow file '{f}': {str(file_err)}")
    except Exception as e:
        logger.error(f"Failed to load workflows: {str(e)}")

    return {"nodes": nodes, "links": links}

def get_live_git_timeline_graph() -> Dict[str, Any]:
    """Retrieves Git history logs and maps commits directly to modified file nodes."""
    nodes = []
    links = []

    # Timeline anchor
    nodes.append({
        "id": "agent_timeline",
        "title": "Chronological Timeline",
        "description": "Workspace commit branch log and developer schedules",
        "type": "manifest",
        "category": "Timeline",
        "tags": ["timeline", "root"],
        "metadata": {},
        "createdAt": datetime.utcnow().isoformat(),
        "updatedAt": datetime.utcnow().isoformat(),
        "importance": 0.8,
        "status": "HEALTHY"
    })

    try:
        # Run git log command to fetch last 30 commits
        res = subprocess.run(
            ["git", "log", "-n", "30", "--pretty=format:%H|%an|%ad|%s", "--date=iso"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if res.returncode == 0 and res.stdout.strip():
            lines = res.stdout.strip().split('\n')
            for line in lines:
                parts = line.split('|')
                if len(parts) >= 4:
                    commit_hash = parts[0]
                    author = parts[1]
                    date_str = parts[2]
                    subject = parts[3]

                    commit_id = f"commit:{commit_hash}"
                    
                    # Create commit node
                    nodes.append({
                        "id": commit_id,
                        "title": subject,
                        "description": f"Commit by {author} ({commit_hash[:8]})",
                        "type": "class", # Maps visually to routines/timeline anchors
                        "category": "Timeline",
                        "tags": ["commit"],
                        "metadata": {"author": author, "hash": commit_hash},
                        "createdAt": date_str,
                        "updatedAt": date_str,
                        "importance": 0.5,
                        "status": "HEALTHY"
                    })
                    links.append({
                        "source": "agent_timeline",
                        "target": commit_id,
                        "type": "workflow",
                        "weight": 1.0,
                        "confidence": 1.0,
                        "metadata": {}
                    })

                    # Optional: get list of files changed in commit and link them
                    files_res = subprocess.run(
                        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_hash],
                        capture_output=True,
                        text=True,
                        timeout=3
                    )
                    if files_res.returncode == 0 and files_res.stdout.strip():
                        changed_files = files_res.stdout.strip().split('\n')[:5] # limit to top 5
                        for cf in changed_files:
                            links.append({
                                "source": commit_id,
                                "target": f"file:{cf}",
                                "type": "documentation",
                                "weight": 1.1,
                                "confidence": 1.0,
                                "metadata": {"label": "modified"}
                            })
    except Exception as e:
        logger.error(f"Failed to fetch git timeline: {str(e)}")

    return {"nodes": nodes, "links": links}
