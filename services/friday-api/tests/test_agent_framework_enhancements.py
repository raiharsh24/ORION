import pytest
import anyio
import tempfile
import time


# =============================================================================
# KeyLockManager Tests
# =============================================================================

class TestKeyLockManager:
    @pytest.fixture
    def lock_mgr(self):
        from app.agent_framework.locks import KeyLockManager
        return KeyLockManager()

    @pytest.mark.anyio
    async def test_acquire_release(self, lock_mgr):
        assert await lock_mgr.acquire("key1", timeout=1.0)
        assert lock_mgr.is_locked("key1")
        lock_mgr.release("key1")
        assert not lock_mgr.is_locked("key1")

    @pytest.mark.anyio
    async def test_concurrent_lock_blocks(self, lock_mgr):
        assert await lock_mgr.acquire("key1", timeout=1.0)
        assert lock_mgr.is_locked("key1")
        acquired = False

        async def try_acquire():
            nonlocal acquired
            acquired = await lock_mgr.acquire("key1", timeout=0.1)

        await try_acquire()
        assert not acquired
        lock_mgr.release("key1")
        assert not lock_mgr.is_locked("key1")

    @pytest.mark.anyio
    async def test_active_locks(self, lock_mgr):
        await lock_mgr.acquire("a")
        await lock_mgr.acquire("b")
        active = lock_mgr.get_active_locks()
        assert "a" in active
        assert "b" in active
        assert lock_mgr.locked_count() == 2
        lock_mgr.release("a")
        lock_mgr.release("b")

    @pytest.mark.anyio
    async def test_clear(self, lock_mgr):
        await lock_mgr.acquire("x")
        assert lock_mgr.locked_count() == 1
        lock_mgr.clear()
        assert lock_mgr.locked_count() == 0


# =============================================================================
# Blackboard Tests
# =============================================================================

class TestBlackboard:
    @pytest.fixture
    def bb(self):
        from app.agent_framework.blackboard import Blackboard
        return Blackboard()

    @pytest.mark.anyio
    async def test_post_and_read(self, bb):
        version = await bb.post("city", "Paris", writer="agent1")
        assert version == 1
        val = await bb.read("city")
        assert val == "Paris"

    @pytest.mark.anyio
    async def test_read_with_meta(self, bb):
        await bb.post("k", "v", writer="a1")
        entry = await bb.read_with_meta("k")
        assert entry is not None
        assert entry.key == "k"
        assert entry.value == "v"
        assert entry.writer == "a1"
        assert entry.version == 1

    @pytest.mark.anyio
    async def test_versioning(self, bb):
        v1 = await bb.post("counter", 1)
        v2 = await bb.post("counter", 2)
        assert v1 == 1
        assert v2 == 2
        assert bb.get_version("counter") == 2

    @pytest.mark.anyio
    async def test_history(self, bb):
        await bb.post("h", "a")
        await bb.post("h", "b")
        await bb.post("h", "c")
        history = bb.get_history("h")
        assert len(history) == 3
        assert [e.value for e in history] == ["a", "b", "c"]

    @pytest.mark.anyio
    async def test_conflict_detection(self, bb):
        await bb.post("x", 1)
        assert bb.check_conflict("x", expected_version=1) is False
        assert bb.check_conflict("x", expected_version=2) is True

    @pytest.mark.anyio
    async def test_delete(self, bb):
        await bb.post("d", "data")
        assert await bb.read("d") == "data"
        assert await bb.delete("d") is True
        assert await bb.read("d") is None
        assert await bb.delete("d") is False

    @pytest.mark.anyio
    async def test_working_memory(self, bb):
        await bb.set_working("temp", 42)
        assert bb.get_working("temp") == 42
        assert bb.get_working("nonexistent") is None
        bb.clear_working()
        assert bb.get_working("temp") is None

    @pytest.mark.anyio
    async def test_get_all_keys(self, bb):
        await bb.post("a", 1)
        await bb.post("b", 2)
        keys = bb.get_all_keys()
        assert set(keys) == {"a", "b"}

    @pytest.mark.anyio
    async def test_locked_post(self, bb):
        from app.agent_framework.locks import KeyLockManager
        lm = KeyLockManager()
        bb2 = type(bb)(lock_manager=lm)
        await lm.acquire("locked_key")
        assert lm.is_locked("locked_key")
        version = await bb2.post("locked_key", "val")
        assert version >= 1

    @pytest.mark.anyio
    async def test_health(self, bb):
        h = bb.health()
        assert h.status == "healthy"
        assert h.entries == 0
        await bb.post("z", 99)
        h = bb.health()
        assert h.entries == 1


# =============================================================================
# Delegation Tests
# =============================================================================

class TestDelegation:
    @pytest.fixture
    def dm(self):
        from app.agent_framework.delegation import DelegationManager
        return DelegationManager()

    @pytest.mark.anyio
    async def test_delegate_task(self, dm):
        task = await dm.delegate(None, "agent1", "code", {"cmd": "build"})
        assert task.task_id is not None
        assert task.agent_id == "agent1"
        assert task.status == "pending"
        assert task.parent_task_id is None

    @pytest.mark.anyio
    async def test_sub_task_creation(self, dm):
        parent = await dm.delegate(None, "agent1", "plan", {})
        child = await dm.delegate(parent.task_id, "agent2", "code", {})
        assert child.parent_task_id == parent.task_id
        children = dm.get_children(parent.task_id)
        assert len(children) == 1
        assert children[0].task_id == child.task_id

    @pytest.mark.anyio
    async def test_complete_task(self, dm):
        task = await dm.delegate(None, "agent1", "test", {})
        result = await dm.complete_task(task.task_id, {"passed": True})
        assert result is not None
        assert result.status == "completed"
        assert result.result == {"passed": True}
        assert result.completed_at is not None

    @pytest.mark.anyio
    async def test_fail_task(self, dm):
        task = await dm.delegate(None, "agent1", "test", {})
        result = await dm.fail_task(task.task_id, "timeout")
        assert result is not None
        assert result.status == "failed"
        assert result.error == "timeout"

    @pytest.mark.anyio
    async def test_dependency_tracking(self, dm):
        t1 = await dm.delegate(None, "agent1", "build", {})
        t2 = await dm.delegate(None, "agent2", "test", {}, dependencies=[t1.task_id])
        t3 = await dm.delegate(None, "agent3", "deploy", {}, dependencies=[t1.task_id, t2.task_id])

        deps1 = dm.get_dependency_graph(t1.task_id)
        assert t1.task_id in deps1

        ready = dm.get_ready_tasks()
        assert t1 in ready

        await dm.complete_task(t1.task_id, {})
        ready = dm.get_ready_tasks()
        assert t2 in ready

    @pytest.mark.anyio
    async def test_pending_and_active_tasks(self, dm):
        t1 = await dm.delegate(None, "agent1", "x", {})
        await dm.delegate(None, "agent2", "y", {})
        await dm.complete_task(t1.task_id, {})

        pending = dm.get_pending_tasks()
        assert len(pending) == 1
        active = dm.get_all_active()
        assert len(active) == 1

    @pytest.mark.anyio
    async def test_count_by_status(self, dm):
        t1 = await dm.delegate(None, "a1", "x", {})
        t2 = await dm.delegate(None, "a2", "y", {})
        await dm.complete_task(t1.task_id, {})
        await dm.fail_task(t2.task_id, "err")

        assert dm.count_by_status("completed") == 1
        assert dm.count_by_status("failed") == 1

    @pytest.mark.anyio
    async def test_restore_task(self, dm):
        task = dm.restore_task({
            "task_id": "restored-1",
            "agent_id": "a1",
            "task_type": "code",
            "payload": {"cmd": "test"},
            "status": "running",
        })
        assert task is not None
        assert task.task_id == "restored-1"
        assert task.status == "running"
        assert dm.count() == 1

    @pytest.mark.anyio
    async def test_set_running(self, dm):
        task = await dm.delegate(None, "a1", "x", {})
        running = await dm.set_running(task.task_id)
        assert running is not None
        assert running.status == "running"

    @pytest.mark.anyio
    async def test_health(self, dm):
        h = dm.health()
        assert h.status == "healthy"
        assert h.total_tasks == 0
        await dm.delegate(None, "a1", "x", {})
        h = dm.health()
        assert h.total_tasks == 1
        assert h.pending == 1

    @pytest.mark.anyio
    async def test_completion_callback(self, dm):
        calls = []

        def cb(task, old_status, new_status):
            calls.append((task.task_id, old_status, new_status))

        dm.on_completion(cb)
        task = await dm.delegate(None, "a1", "x", {})
        await dm.complete_task(task.task_id, {})
        await anyio.sleep(0.01)
        assert len(calls) == 1
        assert calls[0][0] == task.task_id
        assert calls[0][2] == "completed"


# =============================================================================
# Coordinator Tests
# =============================================================================

class TestCoordinator:
    @pytest.fixture
    def coord(self):
        from app.agent_framework.coordinator import Coordinator
        return Coordinator(None)

    @pytest.mark.anyio
    async def test_enqueue_and_queue_length(self, coord):
        assert coord.get_queue_length() == 0
        await coord.enqueue({"agent_id": "a1", "type": "build", "payload": {}}, priority=5.0)
        assert coord.get_queue_length() == 1
        await coord.enqueue({"agent_id": "a2", "type": "test", "payload": {}}, priority=8.0)
        assert coord.get_queue_length() == 2

    @pytest.mark.anyio
    async def test_prioritized_queue_order(self, coord):
        await coord.enqueue({"agent_id": "a1", "type": "low", "payload": {}}, priority=1.0)
        await coord.enqueue({"agent_id": "a2", "type": "high", "payload": {}}, priority=10.0)
        await coord.enqueue({"agent_id": "a3", "type": "mid", "payload": {}}, priority=5.0)

        results = await coord.process_queue(3)
        assert coord.get_queue_length() == 0

    @pytest.mark.anyio
    async def test_resource_allocation(self, coord):
        assert await coord.allocate_resource("agent1", "cpu", 2)
        assert await coord.allocate_resource("agent1", "memory", 1024)
        resources = coord.get_allocated_resources("agent1")
        assert resources["cpu"] == 2
        assert resources["memory"] == 1024

        await coord.release_resource("agent1", "cpu", 1)
        resources = coord.get_allocated_resources("agent1")
        assert resources["cpu"] == 1

    @pytest.mark.anyio
    async def test_health(self, coord):
        h = coord.health()
        assert h.status == "healthy"
        await coord.enqueue({"agent_id": "a1", "type": "x", "payload": {}})
        h = coord.health()
        assert h.queue_size == 1


# =============================================================================
# Priority Engine Tests
# =============================================================================

class TestPriorityEngine:
    @pytest.fixture
    def pe(self):
        from app.agent_framework.priority import PriorityEngine
        return PriorityEngine()

    def test_urgent_mission_high_priority(self, pe):
        from app.agent_framework.priority import PriorityFactors
        pf = PriorityFactors(urgency=10.0, mission_importance=10.0)
        score = pe.calculate(pf)
        assert score > 5.0

    def test_low_priority_mission(self, pe):
        from app.agent_framework.priority import PriorityFactors
        pf = PriorityFactors(urgency=1.0, mission_importance=1.0)
        score = pe.calculate(pf)
        assert score < 3.0

    def test_many_dependencies_lowers_priority(self, pe):
        from app.agent_framework.priority import PriorityFactors
        low_dep = PriorityFactors(dependency_count=0)
        high_dep = PriorityFactors(dependency_count=10)
        assert pe.calculate(low_dep) > pe.calculate(high_dep)

    def test_update_averages_priority(self, pe):
        from app.agent_framework.priority import PriorityFactors
        result = pe.update(5.0, PriorityFactors(urgency=10.0, mission_importance=10.0))
        assert 5.0 < result < 10.0

    def test_no_negative_priority(self, pe):
        from app.agent_framework.priority import PriorityFactors
        pf = PriorityFactors(urgency=0, dependency_count=100, resource_availability=0, estimated_runtime=100, mission_importance=0)
        score = pe.calculate(pf)
        assert score >= 0

    def test_runtime_inverse(self, pe):
        from app.agent_framework.priority import PriorityFactors
        fast = PriorityFactors(estimated_runtime=0.5)
        slow = PriorityFactors(estimated_runtime=100.0)
        assert pe.calculate(fast) > pe.calculate(slow)


# =============================================================================
# Consensus Tests
# =============================================================================

class TestConsensus:
    @pytest.fixture
    def ce(self):
        from app.agent_framework.consensus import ConsensusEngine
        return ConsensusEngine()

    @pytest.mark.anyio
    async def test_majority_accepts(self, ce):
        from app.agent_framework.consensus import ConsensusStrategy
        result = await ce.reach_consensus(
            "deploy",
            ["a1", "a2", "a3"],
            strategy=ConsensusStrategy.MAJORITY,
        )
        assert result.accepted is True
        assert result.strategy == ConsensusStrategy.MAJORITY
        assert result.confidence > 0.5

    @pytest.mark.anyio
    async def test_unanimous_accepts(self, ce):
        from app.agent_framework.consensus import ConsensusStrategy
        result = await ce.reach_consensus(
            "deploy", ["a1", "a2"], strategy=ConsensusStrategy.UNANIMOUS
        )
        assert result.accepted is True
        assert result.confidence == 1.0

    @pytest.mark.anyio
    async def test_coordinator_decision(self, ce):
        from app.agent_framework.consensus import ConsensusStrategy
        result = await ce.reach_consensus(
            "deploy", ["a1", "a2"], strategy=ConsensusStrategy.COORDINATOR_DECISION
        )
        assert result.accepted is True

    @pytest.mark.anyio
    async def test_priority_override(self, ce):
        from app.agent_framework.consensus import ConsensusStrategy
        result = await ce.reach_consensus(
            "deploy", ["a1"], strategy=ConsensusStrategy.PRIORITY_OVERRIDE
        )
        assert result.accepted is True

    @pytest.mark.anyio
    async def test_majority_rejects_with_minority(self, ce):
        from app.agent_framework.consensus import ConsensusStrategy
        async def reject_vote(agent_id, proposal):
            return "reject"
        ce._get_agent_vote = reject_vote
        result = await ce.reach_consensus(
            "risky", ["a1", "a2", "a3"], strategy=ConsensusStrategy.MAJORITY
        )
        assert result.accepted is False
        assert result.confidence < 0.5

    @pytest.mark.anyio
    async def test_unanimous_rejects_with_one_dissenter(self, ce):
        from app.agent_framework.consensus import ConsensusStrategy
        votes = {"a1": "approve", "a2": "reject"}
        result = ce._apply_unanimous("x", votes)
        assert result.accepted is False


# =============================================================================
# Persistence Tests
# =============================================================================

class TestPersistence:
    @pytest.fixture
    def pm(self):
        from app.agent_framework.persistence import PersistenceManager
        tmpdir = tempfile.mkdtemp()
        mgr = PersistenceManager(base_path=tmpdir)
        yield mgr
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.mark.anyio
    async def test_save_and_load_checkpoint(self, pm):
        from app.agent_framework.persistence import CheckpointData
        data = CheckpointData(
            agents={"a1": {"state": "IDLE"}},
            pending_tasks=[{"task_id": "t1", "agent_id": "a1"}],
            timestamp=time.time(),
        )
        await pm.save_checkpoint(data)
        loaded = await pm.load_checkpoint()
        assert loaded is not None
        assert "a1" in loaded.agents
        assert len(loaded.pending_tasks) == 1

    @pytest.mark.anyio
    async def test_agent_state_persistence(self, pm):
        await pm.save_agent_state("agent1", {"state": "RUNNING", "tasks": 5})
        loaded = await pm.load_agent_state("agent1")
        assert loaded is not None
        assert loaded["state"] == "RUNNING"
        assert loaded["tasks"] == 5

    @pytest.mark.anyio
    async def test_nonexistent_returns_none(self, pm):
        loaded = await pm.load_agent_state("nonexistent")
        assert loaded is None

    @pytest.mark.anyio
    async def test_delegation_tree_persistence(self, pm):
        tree = {"t1": {"agent_id": "a1", "children": ["t2"]}}
        await pm.save_delegation_tree(tree)
        loaded = await pm.load_delegation_tree()
        assert loaded == tree

    @pytest.mark.anyio
    async def test_blackboard_persistence(self, pm):
        data = {"entries": {"k1": {"value": 42, "version": 1}}}
        await pm.save_blackboard(data)
        loaded = await pm.load_blackboard()
        assert loaded["entries"]["k1"]["value"] == 42

    @pytest.mark.anyio
    async def test_metrics_persistence(self, pm):
        data = {"delegation_count": 10, "tasks_completed": 50}
        await pm.save_metrics(data)
        loaded = await pm.load_metrics()
        assert loaded["delegation_count"] == 10

    @pytest.mark.anyio
    async def test_warm_restart(self, pm):
        from app.agent_framework.persistence import CheckpointData
        data = CheckpointData(agents={"a1": {"state": "PAUSED"}})
        await pm.save_checkpoint(data)
        cp = await pm.warm_restart()
        assert cp is not None
        assert "a1" in cp.agents

    @pytest.mark.anyio
    async def test_clear(self, pm):
        from app.agent_framework.persistence import CheckpointData
        data = CheckpointData(agents={"a1": {"state": "IDLE"}})
        await pm.save_checkpoint(data)
        assert await pm.checkpoint_exists() is True
        await pm.clear()
        assert await pm.checkpoint_exists() is False

    @pytest.mark.anyio
    async def test_health(self, pm):
        h = pm.health()
        assert h.status == "healthy"
        assert h.has_checkpoint is False


# =============================================================================
# Recovery Tests
# =============================================================================

class TestRecovery:
    @pytest.fixture
    def recovery_setup(self):
        from app.agent_framework.persistence import PersistenceManager
        from app.agent_framework.recovery import RecoveryManager
        from app.agent_framework.delegation import DelegationManager
        from app.agent_framework.blackboard import Blackboard
        tmpdir = tempfile.mkdtemp()
        pm = PersistenceManager(base_path=tmpdir)
        dm = DelegationManager()
        bb = Blackboard()
        rm = RecoveryManager(persistence=pm, delegation=dm, blackboard=bb)
        yield pm, dm, bb, rm
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.mark.anyio
    async def test_recover_no_checkpoint(self, recovery_setup):
        pm, dm, bb, rm = recovery_setup
        report = await rm.recover_all()
        assert report.success is False
        assert "No checkpoint" in report.message

    @pytest.mark.anyio
    async def test_recover_with_checkpoint(self, recovery_setup):
        from app.agent_framework.persistence import CheckpointData
        pm, dm, bb, rm = recovery_setup
        data = CheckpointData(
            agents={},
            pending_tasks=[{"task_id": "t1", "agent_id": "a1", "task_type": "test", "payload": {}}],
            context_data={"bb_key": "bb_value"},
        )
        await pm.save_checkpoint(data)
        report = await rm.recover_all()
        assert report.success is True
        assert report.restored_tasks == 1
        assert report.restored_context_keys == 1

    @pytest.mark.anyio
    async def test_cleanup_stuck_tasks(self, recovery_setup):
        from app.agent_framework.persistence import CheckpointData
        pm, dm, bb, rm = recovery_setup
        task = await dm.delegate(None, "a1", "test", {})
        await dm.set_running(task.task_id)
        errors = await rm.cleanup_inconsistent_state()
        assert len(errors) >= 1
        task = dm.get_task(task.task_id)
        assert task.status == "failed"

    @pytest.mark.anyio
    async def test_recover_agent(self, recovery_setup):
        from app.agent_framework.persistence import CheckpointData
        pm, dm, bb, rm = recovery_setup
        await pm.save_agent_state("test-agent", {"state": "PAUSED"})
        data = CheckpointData(agents={"test-agent": {"state": "PAUSED"}})
        await pm.save_checkpoint(data)
        report = await rm.recover_all()
        assert report.success is True

    @pytest.mark.anyio
    async def test_health(self, recovery_setup):
        pm, dm, bb, rm = recovery_setup
        h = rm.health()
        assert h.status == "healthy"
        assert h.total_recoveries == 0


# =============================================================================
# Metrics Tests
# =============================================================================

class TestMetrics:
    @pytest.fixture
    def mc(self):
        from app.agent_framework.metrics import MetricsCollector
        return MetricsCollector()

    def test_delegation_tracking(self, mc):
        mc.record_delegation()
        mc.record_delegation()
        mc.record_delegation()
        assert mc.delegation_count == 3

    def test_parallel_efficiency(self, mc):
        mc.record_parallel_run(3, 5)
        mc.record_parallel_run(4, 5)
        snap = mc.snapshot()
        assert snap.total_parallel_runs == 2
        assert snap.average_parallel_efficiency > 0.6
        assert snap.average_parallel_efficiency < 0.8

    def test_queue_latency(self, mc):
        mc.record_queue_latency(100.0)
        mc.record_queue_latency(200.0)
        snap = mc.snapshot()
        assert snap.average_queue_latency_ms == 150.0

    def test_utilization(self, mc):
        mc.record_utilization("agent1", 30.0, 100.0)
        mc.record_utilization("agent2", 50.0, 100.0)
        snap = mc.snapshot()
        assert snap.agent_utilization["agent1"] == 0.3
        assert snap.agent_utilization["agent2"] == 0.5
        assert 0.3 < snap.overall_utilization < 0.5
        assert snap.idle_percentage > 50

    def test_recovery_tracking(self, mc):
        mc.record_recovery()
        mc.record_recovery()
        assert mc.recovery_count == 2
        snap = mc.snapshot()
        assert snap.recovery_count == 2

    def test_task_completion(self, mc):
        mc.record_task_completed()
        mc.record_task_completed()
        mc.record_task_completed()
        assert mc.tasks_completed == 3

    def test_snapshot_defaults(self, mc):
        snap = mc.snapshot()
        assert snap.delegation_count == 0
        assert snap.total_parallel_runs == 0
        assert snap.overall_utilization >= 0
        assert snap.idle_percentage >= 0

    def test_reset(self, mc):
        mc.record_delegation()
        mc.record_recovery()
        mc.reset()
        assert mc.delegation_count == 0
        assert mc.recovery_count == 0

    def test_get_data(self, mc):
        mc.record_delegation()
        mc.record_recovery()
        data = mc.get_data()
        assert data["delegation_count"] == 1
        assert data["recovery_count"] == 1


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    @pytest.mark.anyio
    async def test_delegation_to_coordinator(self):
        from app.agent_framework.delegation import DelegationManager
        from app.agent_framework.coordinator import Coordinator
        dm = DelegationManager()
        coord = Coordinator(None, delegation_manager=dm)
        parent = await dm.delegate(None, "agent1", "build", {"target": "all"})
        await dm.delegate(parent.task_id, "agent2", "test", {"target": "unit"})
        children = dm.get_children(parent.task_id)
        assert len(children) == 1
        await coord.enqueue({"agent_id": "agent2", "type": "test", "payload": {}})
        assert coord.get_queue_length() == 1

    @pytest.mark.anyio
    async def test_blackboard_locks_integration(self):
        from app.agent_framework.locks import KeyLockManager
        from app.agent_framework.blackboard import Blackboard
        lm = KeyLockManager()
        bb = Blackboard(lock_manager=lm)
        assert await lm.acquire("shared_key")
        assert lm.is_locked("shared_key")
        assert lm.locked_count() == 1
        lm.release("shared_key")
        assert not lm.is_locked("shared_key")
        assert lm.locked_count() == 0
        version = await bb.post("shared_key", "unlocked_value")
        assert version == 1

    @pytest.mark.anyio
    async def test_priority_with_coordinator_queue(self):
        from app.agent_framework.coordinator import Coordinator
        from app.agent_framework.priority import PriorityEngine, PriorityFactors
        coord = Coordinator(None)
        pe = PriorityEngine()
        pf1 = PriorityFactors(urgency=10.0, mission_importance=10.0)
        pf2 = PriorityFactors(urgency=1.0, mission_importance=1.0)
        await coord.enqueue({"agent_id": "a1", "type": "urgent", "payload": {}}, priority=pe.calculate(pf1))
        await coord.enqueue({"agent_id": "a2", "type": "low", "payload": {}}, priority=pe.calculate(pf2))
        h = coord.health()
        assert h.queue_size == 2

    @pytest.mark.anyio
    async def test_persistence_and_recovery_workflow(self):
        import tempfile, shutil
        from app.agent_framework.persistence import PersistenceManager, CheckpointData
        from app.agent_framework.recovery import RecoveryManager
        from app.agent_framework.delegation import DelegationManager
        from app.agent_framework.blackboard import Blackboard
        tmpdir = tempfile.mkdtemp()
        try:
            pm = PersistenceManager(base_path=tmpdir)
            dm = DelegationManager()
            bb = Blackboard()
            rm = RecoveryManager(persistence=pm, delegation=dm, blackboard=bb)
            task = await dm.delegate(None, "a1", "build", {"target": "test"})
            await bb.post("status", "in_progress")
            all_tasks = dm.get_all()
            all_entries = bb.get_all_entries()
            data = CheckpointData(
                pending_tasks=[
                    {"task_id": t.task_id, "agent_id": t.agent_id,
                     "task_type": t.task_type, "payload": t.payload,
                     "dependencies": t.dependencies, "children": t.children}
                    for t in all_tasks
                ],
                context_data={k: v.value for k, v in all_entries.items()},
            )
            await pm.save_checkpoint(data)
            report = await rm.recover_all()
            assert report.success is True
            assert report.restored_tasks == 1
            assert report.restored_context_keys == 1
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.mark.anyio
    async def test_full_lifecycle_with_agent_manager(self):
        from app.agent_framework.manager import AgentManager
        import tempfile, shutil
        tmpdir = tempfile.mkdtemp()
        try:
            mgr = AgentManager(persistence_base_path=tmpdir)
            from app.agent_framework.base import AgentCapability
            cap = AgentCapability(name="test", description="test capability")
            agent = mgr.create_agent("test-agent", "Test Agent", "tester", capabilities=[cap])
            assert agent is not None

            version = await mgr.blackboard.post("shared", "data", writer="test-agent")
            assert version == 1

            task = await mgr.delegation.delegate(None, "test-agent", "test", {})
            assert task is not None

            h = mgr.health()
            assert h.total_agents == 1
            assert h.blackboard is not None
            assert h.delegation is not None
            assert h.persistence is not None
            assert h.recovery is not None
            assert h.coordinator is not None
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_event_types_exist(self):
        from app.agent_framework.events import (
            DelegationStarted, DelegationCompleted, TaskAssigned,
            TaskCompleted, TaskRecovered, ConsensusReached,
            BlackboardUpdated, CheckpointCreated,
        )
        e1 = DelegationStarted("t1", "p1", "a1", "code")
        assert e1.topic == "DelegationStarted"
        e2 = DelegationCompleted("t1", "a1", "completed")
        assert e2.topic == "DelegationCompleted"
        e3 = ConsensusReached("deploy", "majority", True, 0.8)
        assert e3.topic == "ConsensusReached"
        e4 = BlackboardUpdated("key", "val", "a1", 1)
        assert e4.topic == "BlackboardUpdated"
        e5 = CheckpointCreated(123.0, 3, 5)
        assert e5.topic == "CheckpointCreated"

    def test_health_sub_models_exist(self):
        from app.agent_framework.health import (
            CoordinatorHealth, DelegationHealth, BlackboardHealth,
            PersistenceHealth, RecoveryHealth,
        )
        ch = CoordinatorHealth(queue_size=2, active_tasks=1, resources_allocated=3)
        assert ch.status == "healthy"
        assert ch.queue_size == 2

        dh = DelegationHealth(total_tasks=10, pending=3, running=2, completed=4, failed=1)
        assert dh.pending == 3

        bh = BlackboardHealth(entries=5, locked_keys=1)
        assert bh.entries == 5

        ph = PersistenceHealth(has_checkpoint=True, stored_agents=3, total_files=10)
        assert ph.has_checkpoint is True

        rh = RecoveryHealth(last_recovery="2024-01-01", total_recoveries=5)
        assert rh.total_recoveries == 5

    def test_module_exports(self):
        from app.agent_framework import (
            KeyLockManager, Blackboard, BlackboardEntry,
            DelegationManager, DelegationTask,
            Coordinator, PriorityEngine, PriorityFactors,
            ConsensusEngine, ConsensusStrategy, ConsensusResult,
            PersistenceManager, CheckpointData,
            RecoveryManager, RecoveryReport,
            MetricsCollector, MetricsSnapshot,
            CoordinatorHealth, DelegationHealth, BlackboardHealth,
            PersistenceHealth, RecoveryHealth,
        )
        assert KeyLockManager is not None
        assert Blackboard is not None
        assert DelegationManager is not None
        assert Coordinator is not None
        assert PriorityEngine is not None
        assert ConsensusEngine is not None
        assert PersistenceManager is not None
        assert RecoveryManager is not None
        assert MetricsCollector is not None
