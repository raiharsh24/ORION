import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.execution.context import (
    ExecutionContext, CancellationToken, Stage,
    StageStatus, CancelledError,
)
from app.execution.config import ExecutionConfig, RetryPolicy, TimeoutPolicy
from app.execution.metrics import ExecutionMetrics
from app.execution.middleware import (
    ExecutionMiddleware, MiddlewareChain, LoggingMiddleware,
)
from app.execution.pipeline import ExecutionPipeline
from app.execution.engine import UnifiedExecutionEngine
from app.friday.response import FridayResponse
from app.friday.intent import IntentType


class TestExecutionContext:
    def test_initialization(self):
        ctx = ExecutionContext(prompt="hello", session_id="s1")
        assert ctx.prompt == "hello"
        assert ctx.session_id == "s1"
        assert ctx.execution_id
        assert len(ctx.stage_records) == 8  # 8 stages
        for record in ctx.stage_records.values():
            assert record.status == StageStatus.PENDING

    def test_start_and_complete_stage(self):
        ctx = ExecutionContext(prompt="test")
        ctx.start_stage(Stage.INTENT)
        assert ctx.stage_records[Stage.INTENT.value].status == StageStatus.RUNNING
        ctx.complete_stage(Stage.INTENT, "result")
        assert ctx.stage_records[Stage.INTENT.value].status == StageStatus.COMPLETED
        assert ctx.stage_records[Stage.INTENT.value].duration_ms > 0
        assert ctx.stage_records[Stage.INTENT.value].output == "result"

    def test_fail_stage(self):
        ctx = ExecutionContext(prompt="test")
        ctx.start_stage(Stage.PLANNING)
        ctx.fail_stage(Stage.PLANNING, "something went wrong")
        assert ctx.stage_records[Stage.PLANNING.value].status == StageStatus.FAILED
        assert "planning: something went wrong" in ctx.errors

    def test_skip_stage(self):
        ctx = ExecutionContext(prompt="test")
        ctx.skip_stage(Stage.EXECUTION, "no tools needed")
        assert ctx.stage_records[Stage.EXECUTION.value].status == StageStatus.SKIPPED

    def test_cancellation(self):
        ctx = ExecutionContext(prompt="test")
        assert not ctx.cancelled
        ctx.cancel()
        assert ctx.cancelled

    def test_cancellation_raises(self):
        ctx = ExecutionContext(prompt="test")
        ctx.cancel()
        with pytest.raises(CancelledError):
            ctx.start_stage(Stage.INTENT)

    def test_elapsed_ms(self):
        ctx = ExecutionContext(prompt="test")
        assert ctx.elapsed_ms() == 0.0

    def test_confirmation_flow(self):
        ctx = ExecutionContext(prompt="test", confirmed=False, confirmation_token=None)
        ctx.confirmation_required = True
        ctx.confirmation_token = "tok_123"
        assert ctx.confirmation_required
        assert ctx.confirmation_token == "tok_123"


class TestCancellationToken:
    def test_initial_state(self):
        t = CancellationToken()
        assert not t.cancelled

    def test_cancel(self):
        t = CancellationToken()
        t.cancel()
        assert t.cancelled

    def test_check_raises(self):
        t = CancellationToken()
        t.cancel()
        with pytest.raises(CancelledError):
            t.check()

    def test_check_no_raise(self):
        t = CancellationToken()
        t.check()


class TestExecutionConfig:
    def test_defaults(self):
        cfg = ExecutionConfig()
        assert cfg.retry_policy.max_retries == 3
        assert cfg.retry_policy.base_delay_ms == 500.0
        assert cfg.timeout_policy.execution_timeout_s == 120.0
        assert cfg.track_progress
        assert cfg.emit_events
        assert cfg.collect_metrics

    def test_custom_retry(self):
        cfg = ExecutionConfig(retry_policy=RetryPolicy(max_retries=5, base_delay_ms=100))
        assert cfg.retry_policy.max_retries == 5
        assert cfg.retry_policy.base_delay_ms == 100.0


class TestExecutionMetrics:
    def test_record_execution(self):
        m = ExecutionMetrics()
        m.record_execution(100.0, True)
        assert m.execution_count == 1
        assert m.total_duration_ms == 100.0
        assert m.avg_duration_ms == 100.0
        assert m.successes == 1

    def test_record_stage(self):
        m = ExecutionMetrics()
        m.record_stage("planning", 50.0)
        m.record_stage("planning", 30.0)
        assert len(m.stage_latencies["planning"]) == 2
        assert m.stage_latencies["planning"] == [50.0, 30.0]

    def test_record_cancellation(self):
        m = ExecutionMetrics()
        m.record_cancellation()
        assert m.cancellations == 1

    def test_record_retry(self):
        m = ExecutionMetrics()
        m.record_retry()
        assert m.retries == 1

    def test_snapshot(self):
        m = ExecutionMetrics()
        m.record_execution(100.0, True)
        m.record_stage("planning", 50.0)
        snap = m.snapshot()
        assert snap["execution_count"] == 1
        assert snap["successes"] == 1
        assert snap["stage_average_latencies_ms"]["planning"] == 50.0

    def test_reset(self):
        m = ExecutionMetrics()
        m.record_execution(100.0, True)
        m.reset()
        assert m.execution_count == 0
        assert m.total_duration_ms == 0.0


class TestMiddlewareChain:
    @pytest.mark.anyio
    async def test_empty_chain(self):
        chain = MiddlewareChain()
        ctx = ExecutionContext(prompt="test")
        await chain.before_intent(ctx)
        await chain.after_intent(ctx)
        # Should not raise

    @pytest.mark.anyio
    async def test_logging_middleware(self):
        chain = MiddlewareChain([LoggingMiddleware()])
        ctx = ExecutionContext(prompt="test")
        await chain.before_intent(ctx)
        await chain.after_intent(ctx)

    @pytest.mark.anyio
    async def test_custom_middleware(self):
        calls = []

        class TestMiddleware(ExecutionMiddleware):
            async def before_intent(self, ctx):
                calls.append("before")
            async def after_intent(self, ctx):
                calls.append("after")

        chain = MiddlewareChain([TestMiddleware()])
        ctx = ExecutionContext(prompt="test")
        await chain.before_intent(ctx)
        await chain.after_intent(ctx)
        assert calls == ["before", "after"]

    @pytest.mark.anyio
    async def test_on_error(self):
        calls = []

        class ErrorMiddleware(ExecutionMiddleware):
            async def on_error(self, ctx, stage, error):
                calls.append((stage, str(error)))

        chain = MiddlewareChain([ErrorMiddleware()])
        ctx = ExecutionContext(prompt="test")
        await chain.on_error(ctx, Stage.PLANNING, ValueError("bad"))
        assert calls == [(Stage.PLANNING, "bad")]


class TestPipeline:
    @pytest.mark.anyio
    async def test_empty_pipeline_skips_unregistered_stages(self):
        config = ExecutionConfig()
        metrics = ExecutionMetrics()
        chain = MiddlewareChain()
        pipeline = ExecutionPipeline(config, chain, metrics)
        ctx = ExecutionContext(prompt="test")
        await pipeline.execute(ctx)
        for stage in Stage:
            record = ctx.stage_records[stage.value]
            assert record.status in (StageStatus.SKIPPED, StageStatus.PENDING)

    @pytest.mark.anyio
    async def test_pipeline_runs_all_stages(self):
        config = ExecutionConfig()
        metrics = ExecutionMetrics()
        chain = MiddlewareChain()
        pipeline = ExecutionPipeline(config, chain, metrics)

        results = {}

        async def plan_handler(ctx):
            results["planning"] = True

        async def mem_handler(ctx):
            results["memory"] = True

        async def tool_sel_handler(ctx):
            results["tool_selection"] = True

        async def exec_handler(ctx):
            results["execution"] = True

        async def enrich_handler(ctx):
            results["enrichment"] = True

        async def llm_handler(ctx):
            results["llm"] = True

        async def resp_handler(ctx):
            results["response"] = True

        pipeline.register_stage(Stage.PLANNING, plan_handler)
        pipeline.register_stage(Stage.MEMORY, mem_handler)
        pipeline.register_stage(Stage.TOOL_SELECTION, tool_sel_handler)
        pipeline.register_stage(Stage.EXECUTION, exec_handler)
        pipeline.register_stage(Stage.ENRICHMENT, enrich_handler)
        pipeline.register_stage(Stage.LLM, llm_handler)
        pipeline.register_stage(Stage.RESPONSE, resp_handler)

        ctx = ExecutionContext(prompt="test")
        await pipeline.execute(ctx)

        pipeline_stages = [
            Stage.PLANNING, Stage.MEMORY, Stage.TOOL_SELECTION,
            Stage.EXECUTION, Stage.ENRICHMENT, Stage.LLM, Stage.RESPONSE,
        ]
        for stage in pipeline_stages:
            record = ctx.stage_records[stage.value]
            assert record.status == StageStatus.COMPLETED, f"Stage {stage.value}: {record.status}"
        assert all(results.values())

    @pytest.mark.anyio
    async def test_cancellation_during_pipeline(self):
        config = ExecutionConfig()
        metrics = ExecutionMetrics()
        chain = MiddlewareChain()
        pipeline = ExecutionPipeline(config, chain, metrics)

        calls = []

        async def plan_handler(ctx):
            calls.append("planning")
            ctx.cancel()

        async def mem_handler(ctx):
            calls.append("memory")

        pipeline.register_stage(Stage.PLANNING, plan_handler)
        pipeline.register_stage(Stage.MEMORY, mem_handler)

        ctx = ExecutionContext(prompt="test")
        with pytest.raises(CancelledError):
            await pipeline.execute(ctx)
        assert calls == ["planning"]
        # Planning stage handler completed (it cancelled, but the handler
        # returned normally). The pipeline cancelled the next stage.
        assert ctx.stage_records[Stage.PLANNING.value].status == StageStatus.COMPLETED
        assert ctx.stage_records[Stage.MEMORY.value].status == StageStatus.PENDING

    @pytest.mark.anyio
    async def test_stage_failure_halts_pipeline(self):
        config = ExecutionConfig(
            retry_policy=RetryPolicy(max_retries=0),
        )
        metrics = ExecutionMetrics()
        chain = MiddlewareChain()
        pipeline = ExecutionPipeline(config, chain, metrics)

        calls = []

        async def plan_handler(ctx):
            calls.append("planning")
            raise ValueError("planning failed")

        async def mem_handler(ctx):
            calls.append("memory")

        pipeline.register_stage(Stage.PLANNING, plan_handler)
        pipeline.register_stage(Stage.MEMORY, mem_handler)

        ctx = ExecutionContext(prompt="test")
        await pipeline.execute(ctx)
        assert calls == ["planning"]
        assert ctx.stage_records[Stage.PLANNING.value].status == StageStatus.FAILED

    @pytest.mark.anyio
    async def test_progress_events(self):
        config = ExecutionConfig()
        metrics = ExecutionMetrics()
        chain = MiddlewareChain()
        pipeline = ExecutionPipeline(config, chain, metrics)
        progress_events = []

        async def progress_cb(event):
            progress_events.append(event)

        pipeline.on_progress(progress_cb)

        async def handler(ctx):
            pass

        pipeline.register_stage(Stage.PLANNING, handler)

        ctx = ExecutionContext(prompt="test")
        await pipeline.execute(ctx)
        assert len(progress_events) > 0
        assert all(e.topic == "Execution.Progress" for e in progress_events)


class TestUnifiedExecutionEngine:
    @pytest.mark.anyio
    async def test_execute_returns_friday_response(self):
        engine = UnifiedExecutionEngine(
            llm_router=MagicMock(),
            intent_classifier=MagicMock(),
            memory=MagicMock(),
            prompt_manager=MagicMock(),
            tool_registry=MagicMock(),
            embeddings=MagicMock(),
        )
        # Mock the LLM router
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = "Hello from FRIDAY"
        engine._llm_router.get_provider.return_value = mock_provider

        # Mock intent classifier
        engine._intent_classifier.classify = AsyncMock(return_value=IntentType.CHAT)

        # Mock memory
        mock_session = MagicMock()
        mock_session.created_at = "2024-01-01"
        engine._memory.get_or_create_session.return_value = mock_session
        engine._memory.get_history_string.return_value = ""
        engine._memory.get_session.return_value = mock_session

        # Mock tool registry
        engine._tool_registry.list_tools.return_value = {}

        # Mock prompt manager
        engine._prompt_manager.format_prompt.return_value = "formatted prompt"

        result = await engine.execute(prompt="hello")

        assert isinstance(result, FridayResponse)
        assert result.success
        assert result.response == "Hello from FRIDAY"
        assert result.session_id is not None

    @pytest.mark.anyio
    async def test_execute_handles_cancellation(self):
        engine = UnifiedExecutionEngine(
            llm_router=MagicMock(),
            intent_classifier=MagicMock(),
            memory=MagicMock(),
            prompt_manager=MagicMock(),
            tool_registry=MagicMock(),
            embeddings=MagicMock(),
        )

        class CancellingMiddleware(ExecutionMiddleware):
            async def before_intent(self, ctx):
                ctx.cancel()

        engine.add_middleware(CancellingMiddleware())

        result = await engine.execute(prompt="test")
        assert isinstance(result, FridayResponse)
        assert result.response == "Execution cancelled"

    @pytest.mark.anyio
    async def test_execute_with_plan_tool(self):
        engine = UnifiedExecutionEngine(
            llm_router=MagicMock(),
            intent_classifier=MagicMock(),
            memory=MagicMock(),
            prompt_manager=MagicMock(),
            tool_registry=MagicMock(),
            embeddings=MagicMock(),
        )

        mock_provider = AsyncMock()
        mock_provider.generate.return_value = "Result with tool output"
        engine._llm_router.get_provider.return_value = mock_provider
        engine._intent_classifier.classify = AsyncMock(return_value=IntentType.FILE_OPERATION)

        mock_session = MagicMock()
        mock_session.created_at = "2024-01-01"
        engine._memory.get_or_create_session.return_value = mock_session
        engine._memory.get_history_string.return_value = ""
        engine._tool_registry.list_tools.return_value = {"filesystem": MagicMock()}
        engine._prompt_manager.format_prompt.return_value = "formatted"

        class MockPlan:
            tool_name = "filesystem"
            args = {"op": "read", "path": "/tmp/test.txt"}

        engine._planner.plan = AsyncMock(return_value=MockPlan())

        mock_exec_result = MagicMock()
        mock_exec_result.success = True
        mock_exec_result.output = "file contents"
        mock_exec_result.confirmation_required = False
        engine._tool_executor.execute = AsyncMock(return_value=mock_exec_result)

        result = await engine.execute(prompt="read /tmp/test.txt")
        assert result.success
        assert result.tool_used == "filesystem"

    @pytest.mark.anyio
    async def test_execute_autonomous_goal(self):
        engine = UnifiedExecutionEngine(
            llm_router=MagicMock(),
            intent_classifier=MagicMock(),
            memory=MagicMock(),
            prompt_manager=MagicMock(),
            tool_registry=MagicMock(),
            embeddings=MagicMock(),
            mission_runtime=AsyncMock(),
        )

        engine._intent_classifier.classify = AsyncMock(return_value=IntentType.AUTONOMOUS_GOAL)
        engine._mission_runtime.submit_background = AsyncMock(return_value="mission_123")

        mock_session = MagicMock()
        engine._memory.get_or_create_session.return_value = mock_session

        result = await engine.execute(prompt="deploy the system")
        assert result.success
        assert result.intent == "AUTONOMOUS_GOAL"
        assert result.mission_id == "mission_123"

    @pytest.mark.anyio
    async def test_execute_stream_yields_chunks(self):
        engine = UnifiedExecutionEngine(
            llm_router=MagicMock(),
            intent_classifier=MagicMock(),
            memory=MagicMock(),
            prompt_manager=MagicMock(),
            tool_registry=MagicMock(),
            embeddings=MagicMock(),
        )

        engine._intent_classifier.classify = AsyncMock(return_value=IntentType.CHAT)

        async def mock_stream(_):
            yield "chunk1"
            yield "chunk2"

        mock_provider = MagicMock()
        mock_provider.generate_stream = mock_stream
        engine._llm_router.get_provider.return_value = mock_provider

        mock_session = MagicMock()
        mock_session.created_at = "2024-01-01"
        engine._memory.get_or_create_session.return_value = mock_session
        engine._memory.get_history_string.return_value = ""
        engine._tool_registry.list_tools.return_value = {}
        engine._prompt_manager.format_prompt.return_value = "formatted"

        chunks = []
        async for chunk in engine.execute_stream(prompt="hello"):
            chunks.append(chunk)

        assert len(chunks) == 2
        assert chunks == ["chunk1", "chunk2"]

    @pytest.mark.anyio
    async def test_check_confirmation(self):
        engine = UnifiedExecutionEngine(
            llm_router=MagicMock(),
            intent_classifier=MagicMock(),
            memory=MagicMock(),
            prompt_manager=MagicMock(),
            tool_registry=MagicMock(),
            embeddings=MagicMock(),
        )

        engine._intent_classifier.classify = AsyncMock(return_value=IntentType.SYSTEM_COMMAND)

        class MockPlan:
            tool_name = "terminal"
            args = {"cmd": "rm -rf /"}

        engine._planner.plan = AsyncMock(return_value=MockPlan())

        mock_conf = MagicMock()
        mock_conf.confirmation_required = True
        mock_conf.confirmation_token = "tok_456"
        mock_conf.output = "Are you sure?"
        engine._tool_executor.execute = AsyncMock(return_value=mock_conf)

        requires_conf, token, warning, tool = await engine.check_confirmation(
            prompt="delete everything"
        )

        assert requires_conf
        assert token == "tok_456"
        assert tool == "terminal"

    def test_health(self):
        engine = UnifiedExecutionEngine(
            llm_router=MagicMock(),
            intent_classifier=MagicMock(),
            memory=MagicMock(),
            prompt_manager=MagicMock(),
            tool_registry=MagicMock(),
            embeddings=MagicMock(),
        )
        health = engine.health()
        assert health["status"] == "healthy"
        assert "metrics" in health
        assert "pipeline_stages" in health

    def test_cancel(self):
        engine = UnifiedExecutionEngine(
            llm_router=MagicMock(),
            intent_classifier=MagicMock(),
            memory=MagicMock(),
            prompt_manager=MagicMock(),
            tool_registry=MagicMock(),
            embeddings=MagicMock(),
        )
        engine.cancel("session_1")


