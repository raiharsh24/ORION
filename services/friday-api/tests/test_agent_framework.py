import pytest
import anyio
from unittest.mock import MagicMock

from app.agent_framework.state import AgentState, StateMachine
from app.agent_framework.base import (
    AgentModel, AgentCapability, MissionAssignment, AgentTelemetry,
)
from app.agent_framework.permissions import PermissionManager
from app.agent_framework.communication import CommunicationBus, AgentMessage
from app.agent_framework.registry import AgentRegistry
from app.agent_framework.context import AgentContext
from app.agent_framework.scheduler import AgentScheduler
from app.agent_framework.health import AgentFrameworkHealth
from app.agent_framework.manager import AgentManager
from app.agent_framework.agent import (
    PlannerAgent, ResearchAgent, MemoryAgent, CodeAgent,
    BrowserAgent, ToolAgent, MissionAgent,
    create_all_builtin_agents, BUILTIN_AGENTS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def manager():
    return AgentManager()


@pytest.fixture
def registry():
    return AgentRegistry()


@pytest.fixture
def bus():
    return CommunicationBus()


@pytest.fixture
def ctx():
    return AgentContext()


@pytest.fixture
def scheduler():
    return AgentScheduler()


@pytest.fixture
def agent_model():
    return AgentModel(
        agent_id="test-agent",
        name="Test Agent",
        role="tester",
        capabilities=[AgentCapability(name="test_cap")],
        tools=["tool1"],
        permissions=["filesystem:read"],
    )


@pytest.fixture
def permissions():
    return PermissionManager()


# ---------------------------------------------------------------------------
# State Machine Tests
# ---------------------------------------------------------------------------

class TestStateMachine:
    def test_initial_state(self):
        sm = StateMachine()
        assert sm.state == AgentState.IDLE

    def test_valid_transition(self):
        sm = StateMachine(AgentState.IDLE)
        assert sm.transition(AgentState.PLANNING) is True
        assert sm.state == AgentState.PLANNING

    def test_invalid_transition(self):
        sm = StateMachine(AgentState.COMPLETED)
        assert sm.transition(AgentState.RUNNING) is False
        assert sm.state == AgentState.COMPLETED

    def test_full_lifecycle(self):
        sm = StateMachine()
        assert sm.transition(AgentState.PLANNING) is True
        assert sm.transition(AgentState.RUNNING) is True
        assert sm.transition(AgentState.COMPLETED) is True

    def test_failure_path(self):
        sm = StateMachine(AgentState.RUNNING)
        assert sm.transition(AgentState.FAILED) is True
        assert sm.transition(AgentState.IDLE) is True

    def test_cancellation(self):
        sm = StateMachine(AgentState.RUNNING)
        assert sm.transition(AgentState.CANCELLED) is True

    def test_pause_resume(self):
        sm = StateMachine(AgentState.RUNNING)
        assert sm.transition(AgentState.PAUSED) is True
        assert sm.transition(AgentState.IDLE) is True

    def test_can_transition(self):
        sm = StateMachine(AgentState.IDLE)
        assert sm.can_transition(AgentState.PLANNING) is True
        assert sm.can_transition(AgentState.RUNNING) is False

    def test_reset(self):
        sm = StateMachine(AgentState.RUNNING)
        sm.transition(AgentState.COMPLETED)
        sm.reset()
        assert sm.state == AgentState.IDLE


# ---------------------------------------------------------------------------
# AgentModel Tests
# ---------------------------------------------------------------------------

class TestAgentModel:
    def test_defaults(self, agent_model):
        assert agent_model.is_idle is True
        assert agent_model.is_busy is False
        assert agent_model.is_terminal is False

    def test_has_capability(self, agent_model):
        assert agent_model.has_capability("test_cap") is True
        assert agent_model.has_capability("missing") is False

    def test_has_tool(self, agent_model):
        assert agent_model.has_tool("tool1") is True
        assert agent_model.has_tool("tool2") is False

    def test_can_execute(self, agent_model):
        assert agent_model.can_execute("test_cap") is True
        assert agent_model.can_execute("missing") is False

    def test_busy_state(self, agent_model):
        agent_model.state = AgentState.RUNNING
        assert agent_model.is_idle is False
        assert agent_model.is_busy is True

    def test_terminal_state(self):
        m = AgentModel(agent_id="a", name="A", role="r",
                        state=AgentState.COMPLETED)
        assert m.is_terminal is True

    def test_capability_names(self):
        m = AgentModel(agent_id="a", name="A", role="r",
                        capabilities=[
                            AgentCapability(name="c1"),
                            AgentCapability(name="c2"),
                        ])
        assert m.capability_names == ["c1", "c2"]


# ---------------------------------------------------------------------------
# PermissionManager Tests
# ---------------------------------------------------------------------------

class TestPermissionManager:
    def test_grant_and_check(self, permissions):
        permissions.grant("agent1", "filesystem", "read")
        assert permissions.check("agent1", "filesystem", "read") is True

    def test_revoke(self, permissions):
        permissions.grant("agent1", "filesystem", "read")
        assert permissions.revoke("agent1", "filesystem", "read") is True
        assert permissions.check("agent1", "filesystem", "read") is False

    def test_check_ungranted(self, permissions):
        assert permissions.check("agent1", "filesystem", "read") is False

    def test_role_permissions(self, permissions):
        permissions.grant_role_permission("admin", "system", "config")
        assert len(permissions.get_role_permissions("admin")) == 1

    def test_apply_role(self, permissions):
        permissions.grant_role_permission("admin", "system", "config")
        count = permissions.apply_role_permissions("agent1", "admin")
        assert count == 1
        assert permissions.check("agent1", "system", "config") is True

    def test_clear_agent(self, permissions):
        permissions.grant("agent1", "fs", "r")
        permissions.clear_agent("agent1")
        assert permissions.check("agent1", "fs", "r") is False


# ---------------------------------------------------------------------------
# CommunicationBus Tests
# ---------------------------------------------------------------------------

class TestCommunicationBus:
    @pytest.mark.anyio
    async def test_send_and_receive(self, bus):
        received = []
        async def handler(msg):
            received.append(msg)
        bus.subscribe("agent2", handler)
        msg = AgentMessage(sender="agent1", recipient="agent2",
                           message_type="request", payload={"key": "value"})
        await bus.send(msg)
        assert len(received) == 1
        assert received[0].payload["key"] == "value"

    @pytest.mark.anyio
    async def test_broadcast(self, bus):
        received = []
        async def h1(msg):
            received.append("a1:" + str(msg.payload))
        async def h2(msg):
            received.append("a2:" + str(msg.payload))
        bus.subscribe("agent1", h1)
        bus.subscribe("agent2", h2)
        await bus.broadcast("sender", {"msg": "hello"})
        assert len(received) == 2

    @pytest.mark.anyio
    async def test_request_response(self, bus):
        async def handler(msg):
            await bus.respond(msg, {"result": "ok"})
        bus.subscribe("agent2", handler)
        response = await bus.request("agent2", {"task": "do_something"},
                                     sender="agent1", timeout=5.0)
        assert response is not None
        assert response.payload["result"] == "ok"

    @pytest.mark.anyio
    async def test_request_timeout(self, bus):
        response = await bus.request("nonexistent", {"task": "x"},
                                     sender="agent1", timeout=0.5)
        assert response is None

    def test_subscribe_unsubscribe(self, bus):
        async def handler(msg):
            pass
        bus.subscribe("agent1", handler)
        assert bus.handler_count() == 1
        bus.unsubscribe("agent1", handler)
        assert bus.handler_count() == 0

    def test_health(self, bus):
        h = bus.health()
        assert "subscribers" in h
        assert "handlers" in h


# ---------------------------------------------------------------------------
# AgentRegistry Tests
# ---------------------------------------------------------------------------

class TestAgentRegistry:
    def test_register_and_get(self, registry, agent_model):
        assert registry.register(agent_model) is True
        assert registry.get("test-agent") is agent_model

    def test_register_duplicate(self, registry, agent_model):
        registry.register(agent_model)
        assert registry.register(agent_model) is False

    def test_unregister(self, registry, agent_model):
        registry.register(agent_model)
        assert registry.unregister("test-agent") is True
        assert registry.get("test-agent") is None

    def test_find_by_capability(self, registry, agent_model):
        registry.register(agent_model)
        found = registry.find_by_capability("test_cap")
        assert len(found) == 1

    def test_find_by_role(self, registry, agent_model):
        registry.register(agent_model)
        found = registry.find_by_role("tester")
        assert len(found) == 1

    def test_find_idle_by_capability(self, registry, agent_model):
        registry.register(agent_model)
        found = registry.find_idle_by_capability("test_cap")
        assert len(found) == 1
        assert found[0].is_idle is True

    def test_update_state(self, registry, agent_model):
        registry.register(agent_model)
        assert registry.update_state("test-agent", AgentState.RUNNING) is True
        assert registry.get("test-agent").state == AgentState.RUNNING

    def test_capability_index(self, registry, agent_model):
        registry.register(agent_model)
        idx = registry.get_capability_index()
        assert "test_cap" in idx

    def test_health(self, registry, agent_model):
        registry.register(agent_model)
        h = registry.health()
        assert h["total_agents"] == 1


# ---------------------------------------------------------------------------
# AgentContext Tests
# ---------------------------------------------------------------------------

class TestAgentContext:
    def test_set_and_get(self, ctx):
        ctx.set("agent1", "key1", "value1")
        assert ctx.get("agent1", "key1") == "value1"

    def test_get_default(self, ctx):
        assert ctx.get("agent1", "missing", "default") == "default"

    def test_get_all(self, ctx):
        ctx.set("agent1", "a", 1)
        ctx.set("agent1", "b", 2)
        assert len(ctx.get_all("agent1")) == 2

    def test_clear_agent(self, ctx):
        ctx.set("agent1", "key", "val")
        ctx.clear_agent("agent1")
        assert ctx.get("agent1", "key") is None

    def test_shared_context(self, ctx):
        ctx.set_shared("global_key", "global_val")
        assert ctx.get_shared("global_key") == "global_val"

    def test_history(self, ctx):
        ctx.add_to_history("agent1", "step1")
        ctx.add_to_history("agent1", "step2")
        history = ctx.get_history("agent1")
        assert len(history) == 2

    def test_transfer(self, ctx):
        ctx.set("agent1", "key1", "value1")
        ctx.set("agent1", "key2", "value2")
        count = ctx.transfer("agent1", "agent2", ["key1"])
        assert count == 1
        assert ctx.get("agent2", "key1") == "value1"
        assert ctx.get("agent2", "key2") is None

    def test_health(self, ctx):
        ctx.set("agent1", "k", "v")
        h = ctx.health()
        assert h["agents_with_context"] == 1


# ---------------------------------------------------------------------------
# Scheduler Tests
# ---------------------------------------------------------------------------

class TestAgentScheduler:
    @pytest.mark.anyio
    async def test_schedule_and_cancel(self, scheduler):
        executed = []
        async def handler(entry):
            executed.append(entry.entry_id)
        scheduler.register_handler("test", handler)
        await scheduler.start()
        entry_id = scheduler.schedule("agent1", "test", {"key": "val"},
                                       delay_seconds=0.0)
        await anyio.sleep(0.2)
        assert len(executed) >= 1
        await scheduler.shutdown()

    @pytest.mark.anyio
    async def test_cancel_scheduled(self, scheduler):
        await scheduler.start()
        eid = scheduler.schedule("agent1", "nonexistent", {})
        assert scheduler.cancel(eid) is True
        await scheduler.shutdown()

    def test_list_by_agent(self, scheduler):
        scheduler.schedule("agent1", "type1", {})
        scheduler.schedule("agent1", "type2", {})
        scheduler.schedule("agent2", "type1", {})
        entries = scheduler.list_by_agent("agent1")
        assert len(entries) == 2

    def test_health(self, scheduler):
        h = scheduler.health()
        assert "scheduled_entries" in h


# ---------------------------------------------------------------------------
# AgentManager Tests
# ---------------------------------------------------------------------------

class TestAgentManager:
    def test_create_agent(self, manager):
        cap = AgentCapability(name="test_cap")
        agent = manager.create_agent(
            "test-agent", "Test Agent", "tester",
            capabilities=[cap],
            tools=["tool1"],
            permissions=["filesystem:read"],
        )
        assert agent.agent_id == "test-agent"
        assert manager.registry.count() == 1

    def test_destroy_agent(self, manager):
        manager.create_agent("a1", "Agent 1", "role1")
        assert manager.destroy_agent("a1") is True
        assert manager.registry.get("a1") is None

    def test_transition_agent(self, manager):
        manager.create_agent("a1", "Agent 1", "role1")
        assert manager.transition_agent("a1", AgentState.PLANNING) is True
        assert manager.get_agent("a1").state == AgentState.PLANNING

    def test_invalid_transition(self, manager):
        manager.create_agent("a1", "Agent 1", "role1")
        assert manager.transition_agent("a1", AgentState.WAITING) is False
        assert manager.get_agent("a1").state == AgentState.IDLE

    def test_assign_mission(self, manager):
        manager.create_agent("a1", "Agent 1", "role1")
        assert manager.assign_mission("a1", "m1", "Do the thing") is True
        assert manager.get_agent("a1").mission is not None
        assert manager.get_agent("a1").mission.objective == "Do the thing"

    def test_assign_mission_nonexistent(self, manager):
        assert manager.assign_mission("missing", "m1", "x") is False

    def test_find_agents_for_task(self, manager):
        cap = AgentCapability(name="test_cap")
        manager.create_agent("a1", "Agent 1", "role1", capabilities=[cap])
        found = manager.find_agents_for_task("test_cap")
        assert len(found) == 1

    def test_find_agents_busy_excluded(self, manager):
        cap = AgentCapability(name="test_cap")
        manager.create_agent("a1", "Agent 1", "role1", capabilities=[cap])
        manager.transition_agent("a1", AgentState.PLANNING)
        manager.transition_agent("a1", AgentState.RUNNING)
        found = manager.find_agents_for_task("test_cap")
        assert len(found) == 0

    @pytest.mark.anyio
    async def test_execute_task(self, manager):
        cap = AgentCapability(name="test_cap")
        manager.create_agent("a1", "Agent 1", "role1", capabilities=[cap])
        results = []
        async def handler(agent, payload):
            results.append(payload)
            return {"status": "done"}
        manager.register_task_handler("test_task", handler)
        result = await manager.execute_task("a1", "test_task", {"key": "val"})
        assert result is not None
        assert result["status"] == "done"

    @pytest.mark.anyio
    async def test_execute_task_no_handler(self, manager):
        cap = AgentCapability(name="test_cap")
        manager.create_agent("a1", "Agent 1", "role1", capabilities=[cap])
        result = await manager.execute_task("a1", "no_handler", {})
        assert result is None

    def test_health(self, manager):
        manager.create_agent("a1", "Agent 1", "role1")
        h = manager.health()
        assert h.total_agents == 1
        assert h.overall_status == "healthy"

    def test_list_agents(self, manager):
        manager.create_agent("a1", "A1", "r1")
        manager.create_agent("a2", "A2", "r2")
        assert len(manager.list_agents()) == 2


# ---------------------------------------------------------------------------
# Built-in Agent Tests
# ---------------------------------------------------------------------------

class TestBuiltinAgents:
    def test_planner_agent_creation(self):
        agent = PlannerAgent.create()
        assert agent.agent_id == "planner-agent"
        assert agent.role == "planner"
        assert agent.priority == 10
        assert len(agent.capabilities) == 4

    def test_research_agent_creation(self):
        agent = ResearchAgent.create()
        assert agent.role == "research"
        assert "web_search" in agent.capability_names

    def test_memory_agent_creation(self):
        agent = MemoryAgent.create()
        assert agent.role == "memory"
        assert agent.memory_scope == "persistent"

    def test_code_agent_creation(self):
        agent = CodeAgent.create()
        assert agent.role == "code"
        assert "code_generation" in agent.capability_names

    def test_browser_agent_creation(self):
        agent = BrowserAgent.create()
        assert agent.role == "browser"
        assert "web_navigation" in agent.capability_names

    def test_tool_agent_creation(self):
        agent = ToolAgent.create()
        assert agent.role == "tool"
        assert "tool_execution" in agent.capability_names

    def test_mission_agent_creation(self):
        agent = MissionAgent.create()
        assert agent.role == "mission"
        assert "mission_planning" in agent.capability_names

    def test_create_all_builtin_agents(self):
        agents = create_all_builtin_agents()
        assert len(agents) == 7
        agent_ids = {a.agent_id for a in agents}
        assert "planner-agent" in agent_ids
        assert "mission-agent" in agent_ids

    def test_builtin_agents_dict(self):
        assert "planner-agent" in BUILTIN_AGENTS
        assert "mission-agent" in BUILTIN_AGENTS
        assert len(BUILTIN_AGENTS) == 7


# ---------------------------------------------------------------------------
# Health Tests
# ---------------------------------------------------------------------------

class TestAgentFrameworkHealth:
    def test_defaults(self):
        h = AgentFrameworkHealth()
        assert h.overall_status == "healthy"
        assert h.total_agents == 0

    def test_to_dict(self):
        h = AgentFrameworkHealth(total_agents=7, running_agents=2, idle_agents=5)
        d = h.to_dict()
        assert d["total_agents"] == 7
        assert d["running_agents"] == 2
        assert "checked_at" in d


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestIntegration:
    @pytest.mark.anyio
    async def test_full_agent_lifecycle(self, manager):
        cap = AgentCapability(name="process")
        manager.create_agent("worker", "Worker", "worker", capabilities=[cap])

        assert manager.transition_agent("worker", AgentState.PLANNING) is True
        assert manager.get_agent("worker").state == AgentState.PLANNING

        results = []
        async def handler(agent, payload):
            results.append(payload)
            return {"ok": True}
        manager.register_task_handler("work", handler)

        manager.transition_agent("worker", AgentState.RUNNING)
        assert manager.get_agent("worker").state == AgentState.RUNNING

        manager.transition_agent("worker", AgentState.COMPLETED)
        assert manager.get_agent("worker").state == AgentState.COMPLETED

        agent = manager.get_agent("worker")
        assert agent.telemetry.tasks_completed == 0

    @pytest.mark.anyio
    async def test_agent_communication(self):
        mgr = AgentManager()
        messages = []
        async def handler(msg):
            messages.append(msg)
        mgr.communication.subscribe("agent2", handler)
        await mgr.communication.send(
            AgentMessage(sender="agent1", recipient="agent2",
                          message_type="request", payload={"hello": "world"})
        )
        assert len(messages) == 1

    def test_agent_manager_with_builtins(self):
        mgr = AgentManager()
        agents = create_all_builtin_agents()
        for a in agents:
            mgr.create_agent(a.agent_id, a.name, a.role, a.capabilities,
                              a.tools, a.permissions, a.priority)
        assert mgr.registry.count() == 7
        h = mgr.health()
        assert h.idle_agents == 7

    def test_find_by_capability_and_role(self, manager):
        cap = AgentCapability(name="analysis")
        manager.create_agent("a1", "Analyst", "analyst", capabilities=[cap])
        manager.create_agent("a2", "Worker", "worker")

        assert len(manager.find_by_capability("analysis")) == 1
        assert len(manager.find_by_role("analyst")) == 1
        assert len(manager.find_by_role("worker")) == 1

    def test_state_counts_in_health(self, manager):
        cap = AgentCapability(name="test")
        manager.create_agent("a1", "A1", "r1", capabilities=[cap])
        manager.create_agent("a2", "A2", "r2", capabilities=[cap])

        manager.transition_agent("a1", AgentState.PLANNING)
        manager.transition_agent("a1", AgentState.RUNNING)

        h = manager.health()
        assert h.running_agents == 1
        assert h.idle_agents == 1


# ---------------------------------------------------------------------------
# Kernel Integration Tests
# ---------------------------------------------------------------------------

class TestKernelIntegration:
    @pytest.mark.anyio
    async def test_kernel_registers_agent_framework(self):
        from app.kernel.kernel import FridayKernel
        from app.kernel.config import FridayKernelConfig
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        config.api_keys.gemini_api_key = "test"
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            mgr = kernel.get_service("agent_manager")
            assert mgr is not None
            assert hasattr(mgr, "create_agent")
            assert hasattr(mgr, "registry")
            assert hasattr(mgr, "communication")

            modules = kernel.module_registry.list_modules()
            assert "agent_manager" in modules

            h = kernel.health()
            assert hasattr(h, "agent_framework")
        finally:
            await kernel.shutdown()
            FridayKernel.reset_instance()

    @pytest.mark.anyio
    async def test_agent_framework_health_in_kernel_health(self):
        from app.kernel.kernel import FridayKernel
        from app.kernel.config import FridayKernelConfig
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        config.api_keys.gemini_api_key = "test"
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            health = kernel.health()
            assert health.agent_framework.status.value == "HEALTHY"
        finally:
            await kernel.shutdown()
            FridayKernel.reset_instance()
