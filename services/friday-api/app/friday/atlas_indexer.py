import os
import hashlib
import time
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from concurrent.futures import ThreadPoolExecutor
from loguru import logger

from app.friday.atlas_store import AtlasStore
from app.friday.atlas_parsers import PythonParser, TypeScriptParser, MarkdownParser

class AtlasIndexer:
    """
    Asynchronous incremental indexer and orchestrator for the ATLAS Knowledge Graph.
    Ensures safe single-run constraints, cancellation, and live SSE progress broadcasts.
    """
    def __init__(self, workspace_root: str = "/home/warlock/ORION") -> None:
        self.workspace_root = os.path.abspath(workspace_root)
        self.store = AtlasStore()
        
        # Parsers
        self.parsers = {
            ".py": PythonParser(workspace_root=self.workspace_root),
            ".ts": TypeScriptParser(workspace_root=self.workspace_root),
            ".tsx": TypeScriptParser(workspace_root=self.workspace_root),
            ".js": TypeScriptParser(workspace_root=self.workspace_root),
            ".jsx": TypeScriptParser(workspace_root=self.workspace_root),
            ".md": MarkdownParser(workspace_root=self.workspace_root)
        }
        
        self.ignore_folders = {
            ".git", "node_modules", ".venv", "venv", "__pycache__",
            "dist", "build", "coverage", ".pytest_cache", ".next", ".cache"
        }
        
        # Concurrency & Lifecycle
        self.is_running = False
        self.is_cancelled = False
        self.pending_reindex = False
        self.active_task: Optional[asyncio.Task] = None
        
        # SSE Broadcast listeners (queues)
        self.listeners: Set[asyncio.Queue] = set()

    def get_file_hash(self, file_path: str) -> str:
        """Computes a SHA-256 hash of a file's contents."""
        hasher = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(65536), b''):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""

    def register_listener(self, queue: asyncio.Queue) -> None:
        """Registers a queue for listening to SSE progress logs."""
        self.listeners.add(queue)

    def unregister_listener(self, queue: asyncio.Queue) -> None:
        """Unregisters a progress queue."""
        self.listeners.discard(queue)

    async def broadcast_progress(self, status: str, progress: float, message: str) -> None:
        """Sends live progress logs to all connected SSE clients."""
        payload = {
            "status": status,
            "progress": round(progress, 2),
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        for q in list(self.listeners):
            await q.put(payload)

    async def trigger_indexing(self, background_tasks: Any) -> Dict[str, Any]:
        """
        Public entrypoint. Safely acquires lock, schedules background runs,
        and queues pending actions if a job is already executing.
        """
        if self.is_running:
            self.pending_reindex = True
            logger.info("ATLAS indexer is already active. Queueing single pending re-index job.")
            return {"status": "QUEUED", "message": "Index request has been queued."}

        self.is_running = True
        self.is_cancelled = False
        
        # Launch indexing in the background
        loop = asyncio.get_running_loop()
        self.active_task = loop.create_task(self._run_indexing_pipeline())
        
        return {"status": "STARTED", "message": "Indexing pipeline started."}

    def cancel_indexing(self) -> Dict[str, Any]:
        """Interrupts and cancels the active index task."""
        if not self.is_running:
            return {"status": "IDLE", "message": "No active indexing job to cancel."}

        self.is_cancelled = True
        if self.active_task:
            self.active_task.cancel()
        
        self.is_running = False
        self.pending_reindex = False
        logger.warning("ATLAS Indexing cancelled by user request.")
        return {"status": "CANCELLED", "message": "Indexing has been cancelled."}

    async def _run_indexing_pipeline(self) -> None:
        start_time = time.time()
        snapshot_id = f"snap_{int(start_time)}_{uuid.uuid4().hex[:8]}"
        
        try:
            logger.info(f"Starting ATLAS index snapshot: {snapshot_id}")
            await self.broadcast_progress("STARTING", 0.0, f"Initializing indexing snapshot {snapshot_id}...")

            # Stage 1: Load previous graph cache to support incremental updates
            active_id = self.store.get_active_snapshot_id()
            cached_files = {}
            cached_nodes_map = {}
            cached_edges_list = []

            if active_id:
                logger.info(f"Loading incremental baseline cache from active snapshot: {active_id}")
                await self.broadcast_progress("SCANNING", 5.0, "Loading incremental cache baseline...")
                old_graph = self.store.get_graph_data(active_id)
                
                # Extract file details from metadata
                for node in old_graph.get("nodes", []):
                    # Cache all non-file nodes to carry them forward
                    if not node["id"].startswith("file:"):
                        cached_nodes_map[node["id"]] = node
                        continue

                    metadata = node.get("metadata", {})
                    path = metadata.get("path")
                    if path:
                        cached_files[path] = {
                            "mtime": metadata.get("mtime"),
                            "hash": metadata.get("hash"),
                            "node": node
                        }
                cached_edges_list = old_graph.get("links", [])

            # Walk filesystem
            await self.broadcast_progress("SCANNING", 10.0, "Scanning workspace files...")
            files_to_parse = []
            unchanged_files = []
            scanned_relative_paths = set()

            for root, dirs, files in os.walk(self.workspace_root):
                # Prune ignored dirs in-place
                dirs[:] = [d for d in dirs if d not in self.ignore_folders]
                
                if self.is_cancelled:
                    raise asyncio.CancelledError()

                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in self.parsers:
                        full_path = os.path.join(root, f)
                        rel_path = os.path.relpath(full_path, self.workspace_root)
                        scanned_relative_paths.add(rel_path)
                        
                        try:
                            mtime = os.path.getmtime(full_path)
                            file_hash = self.get_file_hash(full_path)
                        except Exception:
                            continue

                        # Check if cached baseline matches
                        cached = cached_files.get(rel_path)
                        if cached and cached["mtime"] == mtime and cached["hash"] == file_hash:
                            unchanged_files.append(rel_path)
                        else:
                            files_to_parse.append((full_path, rel_path, mtime, file_hash))

            # Detect deleted files
            deleted_files = set(cached_files.keys()) - scanned_relative_paths
            logger.info(f"Scan complete. New/Modified: {len(files_to_parse)}, Unchanged: {len(unchanged_files)}, Deleted: {len(deleted_files)}")

            # Create Database entries
            self.store.create_snapshot(snapshot_id)

            # Stage 2 & 3: Parse new/modified files concurrently
            new_nodes = []
            new_edges = []
            
            total_jobs = len(files_to_parse)
            processed_jobs = 0
            
            if total_jobs > 0:
                await self.broadcast_progress("PARSING", 20.0, f"Analyzing {total_jobs} new or modified code/markdown files...")
                
                # Execute CPU-bound AST parsers in a ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as executor:
                    loop = asyncio.get_running_loop()
                    
                    def run_parse(item):
                        full, rel, mt, hsh = item
                        ext = os.path.splitext(rel)[1].lower()
                        parser = self.parsers[ext]
                        try:
                            with open(full, 'r', encoding='utf-8', errors='ignore') as f:
                                code_content = f.read()
                            res = parser.parse_file(full, code_content)
                            
                            # Attach incremental verification metadata directly to the file node
                            for node in res.get("nodes", []):
                                if node["id"] == f"file:{rel}":
                                    node["metadata"]["mtime"] = mt
                                    node["metadata"]["hash"] = hsh
                            return res
                        except Exception as parse_err:
                            logger.error(f"Error parsing {rel}: {str(parse_err)}")
                            return {"nodes": [], "edges": []}

                    # Spawn tasks
                    futures = [loop.run_in_executor(executor, run_parse, item) for item in files_to_parse]
                    
                    for fut in futures:
                        if self.is_cancelled:
                            raise asyncio.CancelledError()
                        
                        res = await fut
                        new_nodes.extend(res.get("nodes", []))
                        new_edges.extend(res.get("edges", []))
                        processed_jobs += 1
                        
                        progress_percentage = 20.0 + (float(processed_jobs) / total_jobs) * 60.0
                        if processed_jobs % 10 == 0 or processed_jobs == total_jobs:
                            await self.broadcast_progress(
                                "PARSING", 
                                progress_percentage, 
                                f"Parsed {processed_jobs} of {total_jobs} files..."
                            )

            # Stage 4: Relationship Builder (Merge baseline cache nodes and edges)
            await self.broadcast_progress("BUILDING", 85.0, "Building relationship dependency graph...")
            final_nodes_map = {}
            final_edges = []

            # 1. Bring forward cached nodes for unchanged files
            for rel in unchanged_files:
                cached = cached_files.get(rel)
                if cached:
                    # File node
                    file_node = cached["node"]
                    final_nodes_map[file_node["id"]] = file_node
                    
            # 2. Add non-file cached nodes (like memories, workflows, classes from unchanged files)
            # If the class/function belongs to a deleted or modified file, exclude it so AST stays clean!
            for node_id, node in cached_nodes_map.items():
                file_owner = node.get("metadata", {}).get("file")
                if file_owner and (file_owner in deleted_files or file_owner in [item[1] for item in files_to_parse]):
                    continue
                final_nodes_map[node_id] = node

            # 3. Add newly parsed nodes
            for node in new_nodes:
                final_nodes_map[node["id"]] = node

            # 4. Filter and rebuild edges
            # Carry forward old edges if source and target are still present/valid
            for edge in cached_edges_list:
                src = edge["source"]
                tgt = edge["target"]
                
                # Exclude edges originating from or pointing to deleted/modified files
                def is_affected(node_id):
                    # Extends e.g., file:apps/desktop/src/main.ts
                    if node_id.startswith("file:"):
                        p = node_id[5:]
                        return p in deleted_files or p in [item[1] for item in files_to_parse]
                    # Or children definitions of modified/deleted files
                    if "#" in node_id:
                        p = node_id.split(":")[1].split("#")[0]
                        return p in deleted_files or p in [item[1] for item in files_to_parse]
                    return False

                if not is_affected(src) and not is_affected(tgt):
                    final_edges.append(edge)

            # 5. Add new edges
            for edge in new_edges:
                final_edges.append(edge)

            # 6. Generate Parent Folder containment nodes recursively
            folder_nodes = []
            folder_edges = []
            folder_set = set()

            for node_id, node in list(final_nodes_map.items()):
                if node_id.startswith("file:"):
                    rel_p = node_id[5:]
                    parts = rel_p.split(os.sep)
                    for i in range(len(parts) - 1):
                        folder_path = os.sep.join(parts[:i+1])
                        folder_id = f"folder:{folder_path}"
                        
                        if folder_id not in folder_set:
                            folder_set.add(folder_id)
                            folder_nodes.append({
                                "id": folder_id,
                                "title": parts[i],
                                "description": f"Directory: {folder_path}",
                                "type": "folder",
                                "category": "Development",
                                "tags": ["folder", "hierarchy"],
                                "metadata": {"path": folder_path},
                                "createdAt": node["createdAt"],
                                "updatedAt": node["updatedAt"],
                                "importance": 0.3,
                                "status": "HEALTHY"
                            })
                            # Containment edge from root or parent folder
                            if i == 0:
                                folder_edges.append({
                                    "source": "friday",
                                    "target": folder_id,
                                    "type": "containment",
                                    "weight": 1.0
                                })
                            else:
                                parent_f = f"folder:{os.sep.join(parts[:i])}"
                                folder_edges.append({
                                    "source": parent_f,
                                    "target": folder_id,
                                    "type": "containment",
                                    "weight": 1.0
                                })
                                
                        if i == len(parts) - 2:
                            # Link file to direct parent folder
                            folder_edges.append({
                                "source": folder_id,
                                "target": node_id,
                                "type": "containment",
                                "weight": 1.0
                            })

            # Add FRIDAY manifest root
            manifest_id = "friday"
            if manifest_id not in final_nodes_map:
                final_nodes_map[manifest_id] = {
                    "id": manifest_id,
                    "title": "FRIDAY Root Manifest",
                    "description": "Personal AI Assistant and Core Operating System kernel",
                    "type": "manifest",
                    "category": "Manifest",
                    "tags": ["friday", "system-root"],
                    "metadata": {"path": "FRIDAY.md"},
                    "createdAt": datetime.utcnow().isoformat(),
                    "updatedAt": datetime.utcnow().isoformat(),
                    "importance": 1.0,
                    "status": "HEALTHY"
                }

            # Merge folder nodes and edges
            for fn in folder_nodes:
                if fn["id"] not in final_nodes_map:
                    final_nodes_map[fn["id"]] = fn
            for fe in folder_edges:
                final_edges.append(fe)

            # Stage 5: Persistent Graph Store Writes
            await self.broadcast_progress("SAVING", 90.0, "Persisting workspace nodes and relations to SQLite...")
            self.store.insert_nodes(snapshot_id, list(final_nodes_map.values()))
            self.store.insert_edges(snapshot_id, final_edges)

            # Calculate and save statistics
            duration = time.time() - start_time
            stats = {
                "node_count": len(final_nodes_map),
                "edge_count": len(final_edges),
                "duration_seconds": duration,
                "cache_hit_count": len(unchanged_files),
                "cache_miss_count": len(files_to_parse)
            }
            self.store.save_graph_statistics(snapshot_id, stats)
            
            # Update active snapshot pointer (Switch Snapshots)
            self.store.complete_snapshot(snapshot_id, "SUCCESS")
            self.store.set_active_snapshot_id(snapshot_id)

            logger.info(f"ATLAS Index successful. Active snapshot updated to: {snapshot_id} (elapsed: {duration:.2f}s)")
            await self.broadcast_progress(
                "COMPLETED", 
                100.0, 
                f"Successfully parsed workspace. Generated {len(final_nodes_map)} nodes and {len(final_edges)} edges."
            )

        except asyncio.CancelledError:
            logger.warning(f"ATLAS Indexing task cancelled. Cleaning up temporary snapshot: {snapshot_id}")
            self.store.complete_snapshot(snapshot_id, "FAILED", "Cancelled by user request.")
            self.store.delete_snapshot(snapshot_id)
            await self.broadcast_progress("CANCELLED", 0.0, "Indexing job has been cancelled.")
            
        except Exception as err:
            logger.error(f"ATLAS Index failed: {str(err)}")
            self.store.complete_snapshot(snapshot_id, "FAILED", str(err))
            self.store.delete_snapshot(snapshot_id)
            await self.broadcast_progress("FAILED", 0.0, f"Indexing job failed: {str(err)}")
            
        finally:
            self.is_running = False
            self.active_task = None
            
            # Process queued pending jobs
            if self.pending_reindex:
                self.pending_reindex = False
                logger.info("Processing queued pending ATLAS re-index job.")
                loop = asyncio.get_running_loop()
                self.active_task = loop.create_task(self._run_indexing_pipeline())
                self.is_running = True
