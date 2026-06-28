import pytest
import os
import tempfile
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from app.main import app
from app.orion.workspace import WorkspaceManager
from app.memory.embeddings import EmbeddingsManager
from app.orion.vectordb import VectorDB, SimpleVectorDB
from app.orion.indexer import DocumentIndexer
from app.orion.retrieval import RetrievalEngine
from app.tools.knowledge_search import KnowledgeSearchTool

client = TestClient(app)

# ----------------- 1. Workspace Manager Tests -----------------

def test_workspace_manager_git_discovery():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Pre-create standard mock hierarchy
        proj_dir = os.path.join(tmpdir, "my-project")
        git_dir = os.path.join(proj_dir, ".git")
        os.makedirs(git_dir)

        # Mock HEAD file
        with open(os.path.join(git_dir, "HEAD"), "w") as f:
            f.write("ref: refs/heads/feature/knowledge")

        manager = WorkspaceManager(tmpdir)
        projects = manager.discover_projects()

        assert len(projects) == 1
        assert projects[0]["name"] == "my-project"
        assert projects[0]["is_git"] is True
        assert projects[0]["branch"] == "knowledge"


# ----------------- 2. Embeddings Manager Tests -----------------

@pytest.mark.anyio
async def test_embeddings_manager_fallback():
    manager = EmbeddingsManager()
    
    # Offline fallback should generate deterministic 768-dim vectors
    v1 = await manager.embed_text("Orion Brain Engine")
    v2 = await manager.embed_text("Orion Brain Engine")
    v3 = await manager.embed_text("Different query term")

    assert len(v1) == 768
    assert v1 == v2  # Determinism
    assert v1 != v3  # Variance

    # Norm should be 1.0 (normalized)
    norm = sum(x*x for x in v1) ** 0.5
    assert pytest.approx(norm) == 1.0


# ----------------- 3. Local Vector DB Tests -----------------

def test_simple_vector_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = SimpleVectorDB(tmpdir)
        
        # Test addition
        db.add(
            ids=["doc1", "doc2"],
            embeddings=[[0.1] * 768, [0.9] * 768],
            metadatas=[{"name": "doc1_meta"}, {"name": "doc2_meta"}],
            documents=["content one", "content two"]
        )

        assert len(db.ids) == 2

        # Test querying
        query_res = db.query(query_embeddings=[[0.85] * 768], n_results=1)
        assert query_res["ids"][0] == ["doc2"]
        assert query_res["documents"][0] == ["content two"]
        assert query_res["metadatas"][0] == [{"name": "doc2_meta"}]

        # Test persistence reload
        db_reload = SimpleVectorDB(tmpdir)
        assert len(db_reload.ids) == 2
        assert "doc1" in db_reload.ids


# ----------------- 4. Document Indexer & Chunker Tests -----------------

@pytest.mark.anyio
async def test_document_indexer_chunking():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = VectorDB(tmpdir)
        emb = EmbeddingsManager()
        indexer = DocumentIndexer(db, emb)

        # Check overlapping chunk boundaries
        text = "word " * 300  # 1500 chars
        chunks = indexer.chunk_text(text, chunk_size=500, overlap=100)
        assert len(chunks) > 1

        # Test file indexing
        test_file = os.path.join(tmpdir, "doc.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Welcome to the ORION Action and Knowledge OS base.")

        chunks_added = await indexer.index_file(test_file, "orion-test")
        assert chunks_added == 1

        stored = db.get()
        assert len(stored["ids"]) == 1
        assert "orion-test" in stored["metadatas"][0]["project_name"]


# ----------------- 5. Retrieval Engine & Search Tool Tests -----------------

@pytest.mark.anyio
async def test_retrieval_and_search_tool():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = VectorDB(tmpdir)
        emb = EmbeddingsManager()
        
        # Add sample data
        db.add(
            ids=["c1", "c2"],
            embeddings=[emb._get_mock_embedding("python script"), emb._get_mock_embedding("typescript react")],
            metadatas=[{"file_path": "a.py", "project_name": "p1"}, {"file_path": "b.ts", "project_name": "p2"}],
            documents=["import os", "import React from 'react'"]
        )

        retrieval = RetrievalEngine(db, emb)
        tool = KnowledgeSearchTool(retrieval)

        # Test semantic search execution
        tool_res = await tool.execute(query="where do we import React?")
        assert "React" in tool_res
        assert "b.ts" in tool_res


# ----------------- 6. API Route Integration Tests -----------------

@patch("app.orion.indexer.DocumentIndexer.index_directory")
def test_knowledge_index_route(mock_index_dir):
    mock_index_dir.return_value = 15

    response = client.post(
        "/knowledge/index",
        json={"project_name": "test-suite"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["indexed_chunks"] == 15
    assert "test-suite" in data["message"]


def test_workspace_projects_route():
    # Mock discover_projects
    with patch("app.orion.workspace.WorkspaceManager.discover_projects") as mock_discover:
        mock_discover.return_value = [{
            "name": "core-api",
            "path": "/home/warlock/ORION/services/orion-api",
            "is_git": True,
            "branch": "main",
            "files_count": 42,
            "languages": ["Python"]
        }]

        response = client.get("/workspace/projects")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "core-api"
        assert data[0]["branch"] == "main"
        assert data[0]["languages"] == ["Python"]
