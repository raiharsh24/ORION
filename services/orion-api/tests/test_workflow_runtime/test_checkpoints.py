import pytest
import tempfile
import os
from app.workflow_runtime.checkpoints import CheckpointManager


@pytest.mark.anyio
async def test_save_and_load_checkpoint():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = CheckpointManager(persist_dir=tmp)
        await mgr.save_checkpoint("wf-1", "s1", {"status": "done", "value": 42})
        data = await mgr.load_checkpoint("wf-1", "s1")
        assert data is not None
        assert data["status"] == "done"
        assert data["value"] == 42


@pytest.mark.anyio
async def test_load_missing():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = CheckpointManager(persist_dir=tmp)
        data = await mgr.load_checkpoint("wf-none", "s99")
        assert data is None


@pytest.mark.anyio
async def test_clear_checkpoint():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = CheckpointManager(persist_dir=tmp)
        await mgr.save_checkpoint("wf-1", "s1", {"x": 1})
        assert await mgr.load_checkpoint("wf-1", "s1") is not None
        await mgr.clear_checkpoint("wf-1", "s1")
        assert await mgr.load_checkpoint("wf-1", "s1") is None


@pytest.mark.anyio
async def test_clear_workflow_checkpoints():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = CheckpointManager(persist_dir=tmp)
        await mgr.save_checkpoint("wf-1", "s1", {"x": 1})
        await mgr.save_checkpoint("wf-1", "s2", {"x": 2})
        await mgr.save_checkpoint("wf-2", "s1", {"x": 3})
        await mgr.clear_workflow_checkpoints("wf-1")
        assert await mgr.load_checkpoint("wf-1", "s1") is None
        assert await mgr.load_checkpoint("wf-1", "s2") is None
        assert await mgr.load_checkpoint("wf-2", "s1") is not None


@pytest.mark.anyio
async def test_health():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = CheckpointManager(persist_dir=tmp)
        await mgr.save_checkpoint("wf-1", "s1", {"x": 1})
        health = mgr.health()
        assert health["status"] == "HEALTHY"
        assert health["details"]["checkpoint_count"] >= 1
