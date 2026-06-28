import pytest
import tempfile
import os
from app.workflow_runtime.persistence import WorkflowPersistence
from app.workflow_runtime.models import RuntimeWorkflow, RuntimeWorkflowStatus


@pytest.mark.anyio
async def test_save_and_load():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = WorkflowPersistence(persist_dir=tmp)
        wf = RuntimeWorkflow(workflow_id="wf-1", name="Test")
        await persistence.save(wf)
        loaded = await persistence.load("wf-1")
        assert loaded is not None
        assert loaded.workflow_id == "wf-1"
        assert loaded.name == "Test"


@pytest.mark.anyio
async def test_load_missing():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = WorkflowPersistence(persist_dir=tmp)
        result = await persistence.load("nonexistent")
        assert result is None


@pytest.mark.anyio
async def test_list():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = WorkflowPersistence(persist_dir=tmp)
        wf1 = RuntimeWorkflow(workflow_id="wf-1", name="WF1")
        wf2 = RuntimeWorkflow(workflow_id="wf-2", name="WF2")
        await persistence.save(wf1)
        await persistence.save(wf2)
        all_wf = await persistence.list()
        assert len(all_wf) == 2


@pytest.mark.anyio
async def test_delete():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = WorkflowPersistence(persist_dir=tmp)
        wf = RuntimeWorkflow(workflow_id="wf-1", name="Test")
        await persistence.save(wf)
        await persistence.delete("wf-1")
        assert await persistence.load("wf-1") is None


@pytest.mark.anyio
async def test_delete_missing():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = WorkflowPersistence(persist_dir=tmp)
        await persistence.delete("nonexistent")
        assert persistence.count() == 0


@pytest.mark.anyio
async def test_count():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = WorkflowPersistence(persist_dir=tmp)
        assert persistence.count() == 0
        wf = RuntimeWorkflow(workflow_id="wf-1", name="Test")
        await persistence.save(wf)
        assert persistence.count() == 1


@pytest.mark.anyio
async def test_recover_incomplete():
    with tempfile.TemporaryDirectory() as tmp:
        persistence = WorkflowPersistence(persist_dir=tmp)
        completed = RuntimeWorkflow(workflow_id="wf-done", name="Done")
        completed.status = RuntimeWorkflowStatus.COMPLETED
        running = RuntimeWorkflow(workflow_id="wf-run", name="Running")
        running.status = RuntimeWorkflowStatus.RUNNING
        await persistence.save(completed)
        await persistence.save(running)
        recovered = await persistence.recover_incomplete()
        assert len(recovered) == 1
        assert recovered[0].workflow_id == "wf-run"
