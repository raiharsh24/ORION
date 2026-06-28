import pytest
import tempfile
import uuid
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, Any, Optional

from app.orion.planner_schema import ExecutionPlan
from app.orion.plan_adapter import execution_plan_to_input, extract_tool_output, format_tool_output_for_prompt
from app.orion.executor import ToolExecutionResult
from app.orion.response import OrionResponse
from app.workflow_runtime.models import (
    RuntimeWorkflow, RuntimeStep, RuntimeStepStatus, RuntimeWorkflowStatus,
    ExecutionPlanInput, RetryPolicy
)


# ───────────────────────────────────────────────────────
# 1. ExecutionPlanAdapter Tests
# ───────────────────────────────────────────────────────

def test_execution_plan_to_input_converts_all_fields():
    plan = ExecutionPlan(
        intent="Terminal Action",
        goal="List current directory",
        memoryRequired=False,
        toolRequired=True,
        clarificationRequired=False,
        capabilities=["terminal", "filesystem"],
        steps=[{"step_id": "s1", "name": "List dir", "type": "tool", "input": {"cmd": "ls -la"}}],
        priority="high",
        confidence=0.95,
        tool_name="terminal",
        reasoning="User wants to list files",
    )
    result = execution_plan_to_input(plan)
    assert isinstance(result, ExecutionPlanInput)
    assert result.goal == "List current directory"
    assert len(result.steps) == 1
    assert result.steps[0]["step_id"] == "s1"
    assert result.variables["intent"] == "Terminal Action"
    assert result.variables["priority"] == "high"
    assert result.variables["confidence"] == 0.95
    assert result.metadata["capabilities"] == ["terminal", "filesystem"]
    assert result.metadata["tool_name"] == "terminal"


def test_execution_plan_to_input_empty_steps():
    plan = ExecutionPlan(
        intent="Conversation",
        goal="Small talk",
        memoryRequired=False,
        toolRequired=False,
        clarificationRequired=False,
    )
    result = execution_plan_to_input(plan)
    assert result.goal == "Small talk"
    assert result.steps == []


def test_extract_tool_output_empty():
    result = extract_tool_output(MagicMock())
    assert result == {}


def test_extract_tool_output_with_results():
    wf = RuntimeWorkflow(workflow_id="wf-test", name="Test")
    s1 = RuntimeStep(step_id="s1", name="S1", step_type="tool",
                     status=RuntimeStepStatus.COMPLETED,
                     result={"output": "hello world"})
    s2 = RuntimeStep(step_id="s2", name="S2", step_type="tool",
                     status=RuntimeStepStatus.PENDING)
    wf.steps = {"s1": s1, "s2": s2}
    outputs = extract_tool_output(wf)
    assert "s1" in outputs
    assert "s2" not in outputs
    assert outputs["s1"]["output"] == "hello world"


def test_format_tool_output():
    outputs = {"s1": {"output": "file.txt"}, "s2": {"response": "done"}}
    formatted = format_tool_output_for_prompt(outputs)
    assert "[s1]: file.txt" in formatted
    assert "[s2]: done" in formatted


def test_format_tool_output_empty():
    assert format_tool_output_for_prompt({}) == ""


# ───────────────────────────────────────────────────────
# 2. Orchestrator Integration Tests
# ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_orchestrator_falls_back_to_tool_executor_without_runtime():
    """When no runtime_bridge is provided, orchestrator uses ToolExecutor."""
    from app.orion.orchestrator import OrionOrchestrator
    from app.orion.intent import IntentClassifier
    from app.memory.conversation import ConversationMemory
    from app.orion.prompt_manager import PromptManager
    from app.orion.tool_registry import ToolRegistry
    from app.memory.embeddings import EmbeddingsManager
    from app.llm.router import LLMRouter

    mock_llm = MagicMock(spec=LLMRouter)
    mock_llm.get_provider = MagicMock()

    mock_classifier = MagicMock(spec=IntentClassifier)
    mock_classifier.classify.return_value = MagicMock(value="Conversation")

    memory = ConversationMemory()
    prompts = PromptManager()
    embeddings = EmbeddingsManager()
    tool_registry = ToolRegistry()

    orchestrator = OrionOrchestrator(
        llm_router=mock_llm,
        intent_classifier=mock_classifier,
        memory=memory,
        prompt_manager=prompts,
        tool_registry=tool_registry,
        embeddings=embeddings,
        runtime_bridge=None,
    )
    assert orchestrator._runtime_bridge is None
    assert orchestrator.tool_executor is not None


@pytest.mark.anyio
async def test_orchestrator_runtime_path_with_empty_plan():
    """When plan has no steps, orchestrator skips tool execution."""
    from app.orion.orchestrator import OrionOrchestrator
    from app.orion.intent import IntentClassifier
    from app.memory.conversation import ConversationMemory
    from app.orion.prompt_manager import PromptManager
    from app.orion.tool_registry import ToolRegistry
    from app.memory.embeddings import EmbeddingsManager
    from app.llm.router import LLMRouter

    mock_llm = MagicMock(spec=LLMRouter)
    provider = MagicMock()
    provider.generate = AsyncMock(return_value="Hello!")
    mock_llm.get_provider = MagicMock(return_value=provider)

    mock_classifier = MagicMock(spec=IntentClassifier)
    mock_classifier.classify = AsyncMock(return_value=MagicMock(value="Conversation"))

    memory = ConversationMemory()
    prompts = PromptManager()
    embeddings = EmbeddingsManager()
    tool_registry = ToolRegistry()

    with patch("app.orion.orchestrator.Planner") as MockPlanner:
        instance = MagicMock()
        instance.plan = AsyncMock(return_value=None)
        MockPlanner.return_value = instance

        runtime_bridge = MagicMock()
        runtime_bridge.submit_and_wait = AsyncMock()

        orchestrator = OrionOrchestrator(
            llm_router=mock_llm,
            intent_classifier=mock_classifier,
            memory=memory,
            prompt_manager=prompts,
            tool_registry=tool_registry,
            embeddings=embeddings,
            runtime_bridge=runtime_bridge,
        )

        result = await orchestrator.process_query("Hello", confirmed=True)
        assert result.success is True
        assert result.response == "Hello!"
        runtime_bridge.submit_and_wait.assert_not_called()


@pytest.mark.anyio
async def test_orchestrator_runtime_path_with_plan():
    """When runtime is available and plan has steps, uses runtime path."""
    from app.orion.orchestrator import OrionOrchestrator
    from app.orion.intent import IntentClassifier
    from app.memory.conversation import ConversationMemory
    from app.orion.prompt_manager import PromptManager
    from app.orion.tool_registry import ToolRegistry
    from app.memory.embeddings import EmbeddingsManager
    from app.llm.router import LLMRouter

    mock_llm = MagicMock(spec=LLMRouter)
    provider = MagicMock()
    provider.generate = AsyncMock(return_value="Done!")
    mock_llm.get_provider = MagicMock(return_value=provider)

    mock_classifier = MagicMock(spec=IntentClassifier)
    mock_classifier.classify = AsyncMock(return_value=MagicMock(value="Terminal Action"))

    memory = ConversationMemory()
    prompts = PromptManager()
    embeddings = EmbeddingsManager()
    tool_registry = ToolRegistry()

    with patch("app.orion.orchestrator.Planner") as MockPlanner:
        plan = ExecutionPlan(
            intent="Terminal Action",
            goal="Run command",
            memoryRequired=False,
            toolRequired=True,
            clarificationRequired=False,
            steps=[{"step_id": "s1", "name": "Run", "type": "tool", "input": {"cmd": "echo hi"}}],
            tool_name="terminal",
        )

        instance = MagicMock()
        instance.plan = AsyncMock(return_value=plan)
        MockPlanner.return_value = instance

        runtime_wf = RuntimeWorkflow(workflow_id="wf-rt-1", name="Runtime Test")
        s1 = RuntimeStep(step_id="s1", name="Run", step_type="tool",
                         status=RuntimeStepStatus.COMPLETED,
                         result={"output": "hi"})
        runtime_wf.steps = {"s1": s1}
        runtime_wf.status = RuntimeWorkflowStatus.COMPLETED

        runtime_bridge = MagicMock()
        runtime_bridge.submit_and_wait = AsyncMock(return_value=runtime_wf)

        orchestrator = OrionOrchestrator(
            llm_router=mock_llm,
            intent_classifier=mock_classifier,
            memory=memory,
            prompt_manager=prompts,
            tool_registry=tool_registry,
            embeddings=embeddings,
            runtime_bridge=runtime_bridge,
        )

        result = await orchestrator.process_query("Run command", confirmed=True)
        assert result.success is True
        runtime_bridge.submit_and_wait.assert_called_once()


# ───────────────────────────────────────────────────────
# 3. RuntimeSchedulerBridge Integration Tests
# ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_submit_and_wait_completes():
    import tempfile
    from app.workflow_runtime.scheduler_bridge import RuntimeSchedulerBridge
    from app.workflow_runtime.manager import WorkflowRuntimeManager
    from app.workflow_runtime.executor import WorkflowRuntimeExecutor
    from app.workflow_runtime.persistence import WorkflowPersistence
    from app.workflow_runtime.models import RuntimeStep, RetryPolicy

    coordinator = MagicMock()
    coordinator.delegate = AsyncMock(return_value={"output": "hello from runtime"})
    executor = WorkflowRuntimeExecutor(agent_coordinator=coordinator)

    with tempfile.TemporaryDirectory() as tmp:
        persistence = WorkflowPersistence(persist_dir=tmp)
        manager = WorkflowRuntimeManager(persistence=persistence, executor=executor)
        bridge = RuntimeSchedulerBridge(workflow_manager=manager)

        plan_input = ExecutionPlanInput(
            plan_id="integ-plan-1",
            goal="Integration test",
            steps=[{"step_id": "s1", "name": "Step 1", "type": "tool", "input": {"cmd": "test"}}],
            variables={"env": "test"},
        )
        workflow = await bridge.submit_and_wait(plan_input)
        assert workflow is not None
        assert workflow.workflow_id is not None
        assert workflow.status == RuntimeWorkflowStatus.COMPLETED


# ───────────────────────────────────────────────────────
# 4. End-to-End Orchestrator → Runtime → Agent Tests
# ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_execution_plan_to_runtime_workflow():
    """Verifies the complete conversion chain: ExecutionPlan → ExecutionPlanInput → RuntimeWorkflow."""
    from app.workflow_runtime.executor import WorkflowRuntimeExecutor

    plan = ExecutionPlan(
        intent="Filesystem Action",
        goal="Read config file",
        memoryRequired=False,
        toolRequired=True,
        clarificationRequired=False,
        capabilities=["filesystem"],
        steps=[{"step_id": "s1", "name": "Read file", "type": "tool", "input": {"path": "/tmp/config.json"}}],
        priority="medium",
    )
    plan_input = execution_plan_to_input(plan)

    coordinator = MagicMock()
    executor = WorkflowRuntimeExecutor(agent_coordinator=coordinator)
    wf = executor.build_from_plan(plan_input)

    assert wf.workflow_id.startswith("plan-")
    assert wf.name == "Read config file"
    assert len(wf.steps) == 1
    assert "s1" in wf.steps
    assert wf.steps["s1"].input["path"] == "/tmp/config.json"
    assert wf.variables["intent"] == "Filesystem Action"
    assert wf.metadata["capabilities"] == ["filesystem"]


# ───────────────────────────────────────────────────────
# 5. Backward Compatibility Tests
# ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_orchestrator_backward_compat_without_runtime():
    """Original ToolExecutor path still works when runtime_bridge is None."""
    from app.orion.orchestrator import OrionOrchestrator
    from app.orion.intent import IntentClassifier
    from app.memory.conversation import ConversationMemory
    from app.orion.prompt_manager import PromptManager
    from app.orion.tool_registry import ToolRegistry
    from app.memory.embeddings import EmbeddingsManager
    from app.llm.router import LLMRouter

    mock_llm = MagicMock(spec=LLMRouter)
    provider = MagicMock()
    provider.generate = AsyncMock(return_value="Compat OK")
    mock_llm.get_provider = MagicMock(return_value=provider)

    mock_classifier = MagicMock(spec=IntentClassifier)
    mock_classifier.classify = AsyncMock(return_value=MagicMock(value="Conversation"))

    memory = ConversationMemory()
    prompts = PromptManager()
    embeddings = EmbeddingsManager()
    tool_registry = ToolRegistry()

    with patch("app.orion.orchestrator.Planner") as MockPlanner:
        instance = MagicMock()
        instance.plan = AsyncMock(return_value=None)
        MockPlanner.return_value = instance

        orchestrator = OrionOrchestrator(
            llm_router=mock_llm,
            intent_classifier=mock_classifier,
            memory=memory,
            prompt_manager=prompts,
            tool_registry=tool_registry,
            embeddings=embeddings,
        )
        result = await orchestrator.process_query("Hello", confirmed=True)
        assert result.success is True


@pytest.mark.anyio
async def test_check_confirmation_still_works():
    """check_confirmation still uses ToolExecutor directly for pre-execution checks."""
    from app.orion.orchestrator import OrionOrchestrator
    from app.orion.intent import IntentClassifier
    from app.memory.conversation import ConversationMemory
    from app.orion.prompt_manager import PromptManager
    from app.orion.tool_registry import ToolRegistry
    from app.memory.embeddings import EmbeddingsManager
    from app.llm.router import LLMRouter

    mock_llm = MagicMock(spec=LLMRouter)
    mock_classifier = MagicMock(spec=IntentClassifier)
    mock_classifier.classify = AsyncMock(return_value=MagicMock(value="Conversation"))

    memory = ConversationMemory()
    prompts = PromptManager()
    embeddings = EmbeddingsManager()
    tool_registry = ToolRegistry()

    with patch("app.orion.orchestrator.Planner") as MockPlanner:
        instance = MagicMock()
        instance.plan = AsyncMock(return_value=None)
        MockPlanner.return_value = instance

        orchestrator = OrionOrchestrator(
            llm_router=mock_llm,
            intent_classifier=mock_classifier,
            memory=memory,
            prompt_manager=prompts,
            tool_registry=tool_registry,
            embeddings=embeddings,
        )
        requires, token, msg, tool = await orchestrator.check_confirmation("Hello")
        assert requires is False
