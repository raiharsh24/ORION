import os
import shutil
import tempfile
import pytest
import sqlite3
from datetime import datetime

from app.friday.atlas_store import AtlasStore
from app.friday.atlas_parsers import PythonParser, MarkdownParser, TypeScriptParser
from app.friday.atlas_indexer import AtlasIndexer

@pytest.fixture
def temp_db_path():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_atlas.db")
    yield db_path
    shutil.rmtree(temp_dir)

@pytest.fixture
def temp_workspace():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

def test_store_initialization(temp_db_path):
    store = AtlasStore(db_path=temp_db_path)
    assert os.path.exists(temp_db_path)
    
    # Check initial metadata
    active_snap = store.get_active_snapshot_id()
    assert active_snap is None

def test_python_parser():
    parser = PythonParser()
    py_code = """
import os
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health_check():
    return {"status": "OK"}

class MyService(BaseService):
    def process(self):
        pass
"""
    # Create temp file to parse
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
        f.write(py_code.encode("utf-8"))
        f_path = f.name

    try:
        res = parser.parse_file(f_path, py_code)
        nodes = res["nodes"]
        edges = res["edges"]
        
        # Verify node types
        node_types = [n["type"] for n in nodes]
        assert "code" in node_types
        assert "class" in node_types
        assert "route" in node_types

        # Verify route properties
        route_node = next(n for n in nodes if n["type"] == "route")
        assert route_node["title"] == "health_check (/health)"
        assert route_node["metadata"]["route_path"] == "/health"
        
        # Verify imports references
        edge_types = [e["type"] for e in edges]
        assert "dependency" in edge_types
        assert "containment" in edge_types
    finally:
        os.unlink(f_path)

def test_markdown_parser():
    temp_dir = tempfile.gettempdir()
    parser = MarkdownParser(workspace_root=temp_dir)
    md_code = """---
title: System Overview
tags: [core, docs]
description: Friday core OS guide
---
# Saturday OS
Wiki links: [[Architecture Node]]
Markdown links: [Docs](guides/doc_v1.md)
"""
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
        f.write(md_code.encode("utf-8"))
        f_path = f.name

    try:
        res = parser.parse_file(f_path, md_code)
        nodes = res["nodes"]
        edges = res["edges"]

        assert len(nodes) == 1
        node = nodes[0]
        assert node["title"] == "System Overview"
        assert "core" in node["tags"]
        assert "docs" in node["tags"]
        
        # Verify references edges
        edge_targets = [e["target"] for e in edges]
        assert "wikilink:architecture node" in edge_targets
        assert "file:guides/doc_v1.md" in edge_targets
    finally:
        os.unlink(f_path)

@pytest.mark.anyio
async def test_indexing_pipeline(temp_workspace, temp_db_path):
    # Setup test workspace files
    py_file = os.path.join(temp_workspace, "service.py")
    py_code = "class Controller:\n    pass\n"
    with open(py_file, "w") as f:
        f.write(py_code)

    md_file = os.path.join(temp_workspace, "README.md")
    md_code = "# Main Info\nReference [[service.py]]\n"
    with open(md_file, "w") as f:
        f.write(md_code)

    # Instantiate indexer targeting test folder
    indexer = AtlasIndexer(workspace_root=temp_workspace)
    # Redirect store database to our temp test database
    indexer.store = AtlasStore(db_path=temp_db_path)

    # Run the indexer manually (calling internal loop)
    await indexer._run_indexing_pipeline()

    # Verify active snapshot pointer
    active_snap = indexer.store.get_active_snapshot_id()
    assert active_snap is not None
    assert active_snap.startswith("snap_")

    # Load compiled graph data
    graph = indexer.store.get_graph_data(active_snap)
    nodes = graph["nodes"]
    links = graph["links"]

    node_ids = [n["id"] for n in nodes]
    assert "file:service.py" in node_ids
    assert "file:README.md" in node_ids
    assert "class:service.py#Controller" in node_ids
    assert "friday" in node_ids  # system root should exist

    # Run a second incremental run (with no file changes)
    prev_active = active_snap
    await indexer._run_indexing_pipeline()
    
    new_active = indexer.store.get_active_snapshot_id()
    assert new_active != prev_active
    
    # Statistics should show cache hits
    stats = indexer.store.get_health_stats()
    assert stats["node_count"] > 0
    assert stats["cache_status"] == "NOMINAL"

def test_snapshots_timeline(temp_workspace, temp_db_path):
    store = AtlasStore(db_path=temp_db_path)
    
    # Insert a dummy success snapshot
    store.create_snapshot("snap_test_123")
    store.complete_snapshot("snap_test_123", "SUCCESS")
    
    snaps = store.get_snapshots_list()
    assert len(snaps) == 1
    assert snaps[0]["snapshot_id"] == "snap_test_123"
    assert snaps[0]["status"] == "SUCCESS"
