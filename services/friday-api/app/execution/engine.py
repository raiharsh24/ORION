import time
from typing import Optional, Dict, Any, AsyncGenerator, List
from loguru import logger

from app.execution.context import ExecutionContext, Stage, CancelledError
from app.execution.config import ExecutionConfig
from app.execution.middleware import MiddlewareChain, LoggingMiddleware, MetricsMiddleware
from app.execution.metrics import ExecutionMetrics
from app.execution.pipeline import ExecutionPipeline
from app.execution.events import ExecutionStarted, ExecutionCompleted, ExecutionCancelled

from app.friday.intent import IntentClassifier, IntentType
from app.friday.planner import Planner
from app.friday.response import FridayResponse, FridayTelemetry
from app.friday.executor import ToolExecutor, ToolExecutionResult
from app.friday.plan_adapter import execution_plan_to_input, extract_tool_output, format_tool_output_for_prompt
from app.llm.router import LLMRouter
from app.friday.prompt_manager import PromptManager
from app.friday.context import SystemContext
from app.friday.tool_registry import ToolRegistry
from app.memory import ConversationMemory, EmbeddingsManager
from app.events.events import FridayEvent


class UnifiedExecutionEngine:
    def __init__(
        self,
        llm_router: LLMRouter,
        intent_classifier: IntentClassifier,
        memory: ConversationMemory,
        prompt_manager: PromptManager,
        tool_registry: ToolRegistry,
        embeddings: EmbeddingsManager,
        runtime_bridge: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        mission_runtime: Optional[Any] = None,
        cognitive_core: Optional[Any] = None,
        tool_selection_engine: Optional[Any] = None,
        tool_execution_engine: Optional[Any] = None,
        plugin_runtime: Optional[Any] = None,
        config: Optional[ExecutionConfig] = None,
    ) -> None:
        self._llm_router = llm_router
        self._intent_classifier = intent_classifier
        self._memory = memory
        self._prompt_manager = prompt_manager
        self._tool_registry = tool_registry
        self._embeddings = embeddings
        self._runtime_bridge = runtime_bridge
        self._event_bus = event_bus
        self._mission_runtime = mission_runtime
        self._cognitive_core = cognitive_core
        self._tool_selection_engine = tool_selection_engine
        self._tool_execution_engine = tool_execution_engine
        self._plugin_runtime = plugin_runtime

        self._planner = Planner()
        self._tool_executor = ToolExecutor(tool_registry)
        self._config = config or ExecutionConfig()
        self._metrics = ExecutionMetrics()
        self._middleware = MiddlewareChain()
        self._middleware.add(LoggingMiddleware())
        self._middleware.add(MetricsMiddleware(self._metrics))

        self._pipeline = ExecutionPipeline(self._config, self._middleware, self._metrics)
        self._register_stages()

    def set_event_bus(self, event_bus: Any) -> None:
        self._event_bus = event_bus

    def set_cognitive_core(self, cognitive_core: Any) -> None:
        self._cognitive_core = cognitive_core

    def set_tool_selection_engine(self, engine: Any) -> None:
        self._tool_selection_engine = engine

    def set_tool_execution_engine(self, engine: Any) -> None:
        self._tool_execution_engine = engine

    def set_plugin_runtime(self, runtime: Any) -> None:
        self._plugin_runtime = runtime

    def add_middleware(self, middleware: Any) -> None:
        self._middleware.add(middleware)

    @property
    def middleware(self) -> MiddlewareChain:
        return self._middleware

    @property
    def metrics(self) -> ExecutionMetrics:
        return self._metrics

    @property
    def config(self) -> ExecutionConfig:
        return self._config

    def _publish(self, event: Any) -> None:
        if self._event_bus:
            try:
                self._event_bus.publish_background(event)
            except Exception:
                pass

    def _register_stages(self) -> None:
        self._pipeline.register_stage(Stage.PLANNING, self._run_planning)
        self._pipeline.register_stage(Stage.MEMORY, self._run_memory)
        self._pipeline.register_stage(Stage.TOOL_SELECTION, self._run_tool_selection)
        self._pipeline.register_stage(Stage.EXECUTION, self._run_execution)
        self._pipeline.register_stage(Stage.ENRICHMENT, self._run_enrichment)
        self._pipeline.register_stage(Stage.LLM, self._run_llm)
        self._pipeline.register_stage(Stage.RESPONSE, self._run_response)

    async def _run_intent(self, ctx: ExecutionContext) -> IntentType:
        intent = await self._intent_classifier.classify(ctx.prompt)
        ctx.intent = intent
        logger.info(f"Intent: {intent.value}")
        return intent

    async def _run_planning(self, ctx: ExecutionContext) -> Any:
        plan = await self._planner.plan(ctx.prompt, ctx.intent)
        ctx.plan = plan

        if plan and plan.tool_name:
            ctx.tool_used = plan.tool_name
            ctx.metadata["plan_tool_name"] = plan.tool_name
            ctx.metadata["plan_args"] = plan.args

        return plan

    async def _run_memory(self, ctx: ExecutionContext) -> str:
        session = self._memory.get_or_create_session(ctx.session_id)
        if ctx.tool_used:
            session.tool_used = ctx.tool_used

        history_str = self._memory.get_history_string(ctx.session_id)
        ctx.memory_context = history_str
        return history_str

    async def _run_tool_selection(self, ctx: ExecutionContext) -> Any:
        plan = ctx.plan
        if not plan:
            return None

        if self._tool_selection_engine and hasattr(plan, "steps") and plan.steps:
            from app.tool_selection.base import ToolSelectionContext
            sel_ctx = ToolSelectionContext(
                required_capabilities=getattr(plan, "capabilities", []),
            )
            sel_result = await self._tool_selection_engine.select(sel_ctx)
            ctx.selected_tools = sel_result
            return sel_result

        return None

    async def _run_execution(self, ctx: ExecutionContext) -> str:
        plan = ctx.plan
        if not plan:
            return ""

        tool_output = ""

        if plan.tool_name:
            exec_result = await self._tool_executor.execute(
                plan, ctx.confirmed, ctx.confirmation_token,
            )
            if exec_result.confirmation_required:
                ctx.confirmation_required = True
                ctx.confirmation_token = exec_result.confirmation_token
                return exec_result.output
            if exec_result.success:
                tool_output = exec_result.output
            else:
                tool_output = f"Error executing tool: {exec_result.error}"
            ctx.tool_output = tool_output
            return tool_output

        if self._tool_execution_engine and ctx.selected_tools and hasattr(ctx.selected_tools, 'selected_tools') and ctx.selected_tools.selected_tools:
            from app.tool_execution.base import ExecutionMode
            sel_result = await self._tool_execution_engine.execute(
                selection_result=ctx.selected_tools,
                mode=ExecutionMode.SEQUENTIAL,
                global_timeout=120.0,
                cancellation_token=ctx.cancellation_token,
            )
            if sel_result and hasattr(sel_result, 'results') and sel_result.results:
                outputs = []
                for r in sel_result.results:
                    if r.output:
                        outputs.append(str(r.output))
                tool_output = "\n".join(outputs)
                ctx.tool_output = tool_output

        elif self._runtime_bridge and plan and getattr(plan, "steps", None):
            try:
                runtime_input = execution_plan_to_input(plan)
                workflow = await self._runtime_bridge.submit_and_wait(runtime_input)
                tool_outputs = extract_tool_output(workflow)
                if tool_outputs:
                    tool_output = format_tool_output_for_prompt(tool_outputs)
                else:
                    tool_output = "Workflow completed but no tool output captured."
                ctx.tool_output = tool_output
            except Exception:
                exec_result = await self._tool_executor.execute(
                    plan, confirmed=True, confirmation_token=ctx.confirmation_token,
                )
                if exec_result.success:
                    tool_output = exec_result.output
                else:
                    tool_output = f"Error executing tool: {exec_result.error}"
                ctx.tool_output = tool_output
        else:
            exec_result = await self._tool_executor.execute(
                plan, confirmed=True, confirmation_token=ctx.confirmation_token,
            )
            if exec_result.success:
                tool_output = exec_result.output
            else:
                tool_output = f"Error executing tool: {exec_result.error}"
            ctx.tool_output = tool_output

        return tool_output

    async def _run_enrichment(self, ctx: ExecutionContext) -> str:
        if not self._cognitive_core:
            return ""
        try:
            retrieval = await self._cognitive_core.retrieve_relevant_context(
                ctx.prompt, top_k=3,
            )
            ctx.enrichment_context = retrieval.get("combined_context", "")
            return ctx.enrichment_context
        except Exception as e:
            logger.debug(f"Cognitive enrichment skipped: {e}")
            return ""

    async def _run_llm(self, ctx: ExecutionContext) -> str:
        sys_context = SystemContext()
        session = self._memory.get_or_create_session(ctx.session_id)

        if ctx.tool_output:
            session.tool_output = ctx.tool_output

        available_tools = list(self._tool_registry.list_tools().keys())

        vision_str = ""
        if session.context and isinstance(session.context, dict):
            last_vision = session.context.get("last_vision")
            if last_vision and last_vision.get("has_text"):
                vision_str = f"\n[Previous Screen Context]:\n{last_vision.get('ocr_text', '')}"
                if last_vision.get("element_count", 0) > 0:
                    vision_str += f"\n[UI Elements Detected: {last_vision['element_count']}]"

        system_instruction = "You are FRIDAY, the central AI operating system core. Be helpful and direct."
        if ctx.tool_used:
            system_instruction += f"\n[Executed Tool: {ctx.tool_used}. Output results: {ctx.tool_output}]"
        if vision_str:
            system_instruction += vision_str
        if ctx.enrichment_context:
            system_instruction += f"\n[Relevant Context]:\n{ctx.enrichment_context}"

        session_meta = {
            "session_id": ctx.session_id,
            "created_at": session.created_at,
            "platform": sys_context.platform,
            "status": sys_context.status,
        }

        full_prompt = self._prompt_manager.format_prompt(
            system_instruction=system_instruction,
            user_message=ctx.prompt,
            history=ctx.memory_context,
            available_tools=available_tools,
            session_metadata=session_meta,
            retrieved_context=ctx.tool_output if ctx.tool_used == "knowledge.search" else None,
        )

        provider = self._llm_router.get_provider(ctx.provider_name)
        response = await provider.generate(full_prompt)
        ctx.llm_response = response
        return response

    async def _run_response(self, ctx: ExecutionContext) -> FridayResponse:
        self._memory.add_message(ctx.session_id, "user", ctx.prompt)

        if ctx.confirmation_required:
            exec_output = ctx.stage_records[Stage.EXECUTION.value].output if Stage.EXECUTION.value in ctx.stage_records else ""
            if isinstance(exec_output, str):
                llm_resp = exec_output
            else:
                llm_resp = ctx.llm_response or ""
            return FridayResponse(
                success=False,
                intent=ctx.intent.value,
                response=llm_resp,
                tool_used=ctx.tool_used,
                session_id=ctx.session_id,
                execution_time_ms=ctx.elapsed_ms(),
                telemetry=FridayTelemetry(model=ctx.provider_name, error="ConfirmationRequired"),
                confirmation_required=True,
                confirmation_token=ctx.confirmation_token,
            )

        self._memory.add_message(ctx.session_id, "assistant", ctx.llm_response)
        self._memory.update_context(ctx.session_id, f"Intent: {ctx.intent.value}")

        return FridayResponse(
            success=True,
            intent=ctx.intent.value,
            response=ctx.llm_response,
            tool_used=ctx.tool_used,
            session_id=ctx.session_id,
            execution_time_ms=ctx.elapsed_ms(),
            telemetry=FridayTelemetry(model=ctx.provider_name),
            confirmation_required=ctx.confirmation_required,
            confirmation_token=ctx.confirmation_token,
        )

    async def execute(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        provider_name: str = "gemini",
        confirmed: bool = False,
        confirmation_token: Optional[str] = None,
    ) -> FridayResponse:
        import uuid
        ctx = ExecutionContext(
            session_id=session_id or str(uuid.uuid4()),
            prompt=prompt,
            provider_name=provider_name,
            confirmed=confirmed,
            confirmation_token=confirmation_token,
        )

        self._publish(FridayEvent(topic="ConversationReceived", data={
            "session_id": ctx.session_id, "prompt": prompt,
        }))

        try:
            await self._middleware.before_intent(ctx)
            ctx.start_stage(Stage.INTENT)
            intent = await self._run_intent(ctx)
            ctx.complete_stage(Stage.INTENT, intent)
            await self._middleware.after_intent(ctx)

            if ctx.intent == IntentType.AUTONOMOUS_GOAL and self._mission_runtime:
                return await self._handle_autonomous_goal(ctx)

            await self._pipeline.execute(ctx)

            ctx.final_response = ctx.stage_records[Stage.RESPONSE.value].output
            success = ctx.stage_records[Stage.RESPONSE.value].status.value == "completed"
            self._metrics.record_execution(ctx.elapsed_ms(), success)

            self._publish(FridayEvent(topic="ConversationCompleted", data={
                "session_id": ctx.session_id,
            }))

            return ctx.final_response or FridayResponse(
                success=False,
                intent=str(ctx.intent) if ctx.intent else "unknown",
                response="Execution completed with no response",
                session_id=ctx.session_id,
                execution_time_ms=ctx.elapsed_ms(),
                telemetry=FridayTelemetry(model=provider_name),
            )

        except CancelledError:
            self._metrics.record_cancellation()
            self._publish(FridayEvent(topic="ConversationCompleted", data={
                "session_id": ctx.session_id, "error": "cancelled",
            }))
            return FridayResponse(
                success=False,
                intent=str(ctx.intent) if ctx.intent else "unknown",
                response="Execution cancelled",
                session_id=ctx.session_id,
                execution_time_ms=ctx.elapsed_ms(),
                telemetry=FridayTelemetry(model=provider_name, error="Cancelled"),
            )

        except Exception as e:
            logger.error(f"Execution failed: {e}")
            self._metrics.record_execution(ctx.elapsed_ms(), False)
            self._publish(FridayEvent(topic="ConversationCompleted", data={
                "session_id": ctx.session_id, "error": str(e),
            }))
            return FridayResponse(
                success=False,
                intent=str(ctx.intent) if ctx.intent else "unknown",
                response=f"Execution error: {str(e)}",
                session_id=ctx.session_id,
                execution_time_ms=ctx.elapsed_ms(),
                telemetry=FridayTelemetry(model=provider_name, error=str(e)),
            )

    async def execute_stream(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        provider_name: str = "gemini",
        confirmed: bool = False,
        confirmation_token: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        import uuid
        ctx = ExecutionContext(
            session_id=session_id or str(uuid.uuid4()),
            prompt=prompt,
            provider_name=provider_name,
            confirmed=confirmed,
            confirmation_token=confirmation_token,
        )

        self._publish(FridayEvent(topic="ConversationReceived", data={
            "session_id": ctx.session_id, "prompt": prompt,
        }))

        try:
            if ctx.intent == IntentType.AUTONOMOUS_GOAL and self._mission_runtime:
                mission_id = await self._mission_runtime.submit_background(
                    user_request=prompt,
                    intent="AUTONOMOUS_GOAL",
                    metadata={"session_id": ctx.session_id},
                )
                self._memory.add_message(ctx.session_id, "user", prompt)
                self._memory.add_message(ctx.session_id, "assistant",
                    f"Starting autonomous mission: {mission_id}")
                yield f"Starting autonomous mission: {mission_id}"
                return

            await self._run_intent(ctx)
            await self._run_planning(ctx)
            await self._run_memory(ctx)
            await self._run_tool_selection(ctx)
            await self._run_execution(ctx)
            await self._run_enrichment(ctx)

            self._memory.add_message(ctx.session_id, "user", prompt)

            sys_context = SystemContext()
            session = self._memory.get_or_create_session(ctx.session_id)
            if ctx.tool_output:
                session.tool_output = ctx.tool_output

            available_tools = list(self._tool_registry.list_tools().keys())

            vision_str = ""
            if session.context and isinstance(session.context, dict):
                last_vision = session.context.get("last_vision")
                if last_vision and last_vision.get("has_text"):
                    vision_str = f"\n[Previous Screen Context]:\n{last_vision.get('ocr_text', '')}"

            system_instruction = "You are FRIDAY, the central AI operating system core. Stream text."
            if ctx.tool_used:
                system_instruction += f"\n[Executed Tool: {ctx.tool_used}. Output results: {ctx.tool_output}]"
            if vision_str:
                system_instruction += vision_str
            if ctx.enrichment_context:
                system_instruction += f"\n[Relevant Context]:\n{ctx.enrichment_context}"

            full_prompt = self._prompt_manager.format_prompt(
                system_instruction=system_instruction,
                user_message=prompt,
                history=ctx.memory_context,
                available_tools=available_tools,
                session_metadata={
                    "session_id": ctx.session_id,
                    "created_at": session.created_at,
                    "platform": sys_context.platform,
                    "status": sys_context.status,
                },
                retrieved_context=ctx.tool_output if ctx.tool_used == "knowledge.search" else None,
            )

            provider = self._llm_router.get_provider(provider_name)
            full_response = []
            async for chunk in provider.generate_stream(full_prompt):
                full_response.append(chunk)
                yield chunk

            final = "".join(full_response)
            self._memory.add_message(ctx.session_id, "assistant", final)
            self._memory.update_context(ctx.session_id, f"Intent: {ctx.intent.value} (streamed)")

        except Exception as e:
            logger.error(f"Stream execution failed: {e}")
            yield f"\n[STREAM ERROR: {str(e)}]"

    async def check_confirmation(
        self,
        prompt: str,
        confirmed: bool = False,
        confirmation_token: Optional[str] = None,
    ) -> tuple:
        ctx = ExecutionContext(prompt=prompt, confirmed=confirmed, confirmation_token=confirmation_token)
        await self._run_intent(ctx)
        await self._run_planning(ctx)
        if ctx.plan:
            exec_result = await self._tool_executor.execute(ctx.plan, confirmed, confirmation_token)
            if exec_result and exec_result.confirmation_required:
                return True, exec_result.confirmation_token, exec_result.output, ctx.tool_used
        return False, None, None, None

    async def _handle_autonomous_goal(self, ctx: ExecutionContext) -> FridayResponse:
        mission_id = await self._mission_runtime.submit_background(
            user_request=ctx.prompt,
            intent="AUTONOMOUS_GOAL",
            metadata={"session_id": ctx.session_id},
        )
        self._memory.add_message(ctx.session_id, "user", ctx.prompt)
        self._memory.add_message(ctx.session_id, "assistant",
            f"Starting autonomous mission: {mission_id}")
        self._memory.update_context(ctx.session_id, f"Intent: AUTONOMOUS_GOAL (mission: {mission_id})")

        return FridayResponse(
            success=True,
            intent="AUTONOMOUS_GOAL",
            response=f"Starting autonomous mission for: {ctx.prompt}",
            session_id=ctx.session_id,
            execution_time_ms=0,
            telemetry=FridayTelemetry(model=ctx.provider_name),
            mission_id=mission_id,
        )

    def cancel(self, session_id: Optional[str] = None) -> None:
        logger.info(f"Cancel requested for session: {session_id}")

    def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "metrics": self._metrics.snapshot(),
            "pipeline_stages": [s.value for s in Stage],
            "middleware_count": len(self._middleware._middlewares),
        }
