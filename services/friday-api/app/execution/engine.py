import time
from typing import Optional, Dict, Any, AsyncGenerator, List
from loguru import logger

from app.execution.context import ExecutionContext, Stage, CancelledError
from app.execution.state import ExecutionStateModel
from app.goal_planner import GoalPlanner, GoalPlan
from app.reflection import HeuristicReflectionEngine, ExecutionSnapshot, ReflectionReport
from app.workspace import WorkspaceScanner, WorkspaceContext, WorkspaceAnalyzer
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
        self._goal_planner = GoalPlanner()
        self._reflection_engine = HeuristicReflectionEngine()
        self._workspace_scanner = WorkspaceScanner()
        self._workspace_analyzer = WorkspaceAnalyzer()
        self._workspace_context: Optional[WorkspaceContext] = None
        self._workspace_summary: Optional[Any] = None
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

    def _ensure_workspace(self) -> WorkspaceContext:
        if self._workspace_context is None:
            self._workspace_context = self._workspace_scanner.scan()
            self._publish(FridayEvent(topic="WorkspaceUpdated", data=self._workspace_context.to_dict()))

            summary = self._workspace_analyzer.analyze(self._workspace_context)
            self._workspace_summary = summary
            self._publish(FridayEvent(topic="WorkspaceSummaryUpdated", data=summary.to_dict()))

            logger.info(
                f"Workspace scanned: project={self._workspace_context.current_project}, "
                f"langs={self._workspace_context.detected_languages}, "
                f"framework={self._workspace_context.framework}, "
                f"health={summary.health_label}"
            )
            for rec in summary.recommendations:
                logger.info(f"  Recommendation [{rec.priority}]: {rec.message}")
        return self._workspace_context

    def refresh_workspace(self) -> WorkspaceContext:
        self._workspace_context = self._workspace_scanner.rescan()
        self._publish(FridayEvent(topic="WorkspaceUpdated", data=self._workspace_context.to_dict()))

        summary = self._workspace_analyzer.analyze(self._workspace_context)
        self._workspace_summary = summary
        self._publish(FridayEvent(topic="WorkspaceSummaryUpdated", data=summary.to_dict()))

        return self._workspace_context

    @property
    def workspace(self) -> Optional[WorkspaceContext]:
        return self._workspace_context

    def _publish_execution_state(self, ctx: ExecutionContext, stage: str = "") -> None:
        state = ExecutionStateModel()
        state.goal = ctx.prompt[:200]
        state.execution_stage = stage or "idle"
        state.stage_status = "running"

        if ctx.goal_plan and ctx.goal_plan.task_count > 0:
            state.planner_tasks = [
                {"id": t.id, "title": t.title, "capability": t.required_capability,
                 "status": t.status, "dependencies": t.dependencies}
                for t in ctx.goal_plan.tasks
            ]
            running = [t for t in ctx.goal_plan.tasks if t.status == "running"]
            if running:
                state.active_task = running[0].title
            completed = [t for t in ctx.goal_plan.tasks if t.status == "completed"]
            state.completed_tasks = [t.title for t in completed]

        if ctx.selected_tools and hasattr(ctx.selected_tools, 'selected_tools') and ctx.selected_tools.selected_tools:
            top = ctx.selected_tools.selected_tools[0]
            state.selected_tool = top.tool.id
            state.confidence = top.confidence

        if ctx.reflection_report is not None:
            report = ctx.reflection_report
            state.reflection_score = report.execution_quality_score
            state.reflection_summary = (
                f"Succeeded: {len(report.what_succeeded)} | "
                f"Failed: {len(report.what_failed)} | "
                f"Score: {report.execution_quality_score:.2f}"
            )

        self._publish(FridayEvent(topic="ExecutionStateUpdated", data=state.to_dict()))

    def _build_snapshot(self, ctx: ExecutionContext) -> ExecutionSnapshot:
        tools = []
        fallback_used = False
        if ctx.selected_tools and hasattr(ctx.selected_tools, 'selected_tools'):
            for st in ctx.selected_tools.selected_tools:
                tools.append({
                    "id": st.tool.id,
                    "score": getattr(st, "score", 0.0),
                    "confidence": getattr(st, "confidence", 0.0),
                    "is_fallback": getattr(st, "is_fallback", False),
                    "reason": getattr(st, "selection_reason", ""),
                })
                if getattr(st, "is_fallback", False):
                    fallback_used = True

        confidence = tools[0].get("confidence", 0.0) if tools else 0.0

        completed = []
        if ctx.goal_plan and ctx.goal_plan.task_count > 0:
            completed = [
                {"id": t.id, "title": t.title, "status": t.status}
                for t in ctx.goal_plan.tasks
            ]

        exec_stage = ctx.stage_records.get(Stage.EXECUTION.value)
        duration = exec_stage.duration_ms if exec_stage else 0.0

        tool_output_str = ctx.tool_output or ""
        success = bool(tool_output_str) and "Error" not in tool_output_str

        return ExecutionSnapshot(
            execution_id=ctx.execution_id,
            goal=ctx.prompt[:200],
            intent=ctx.intent.value if ctx.intent else "unknown",
            selected_tools=tools,
            confidence=confidence,
            execution_duration_ms=duration,
            success=success,
            fallback_used=fallback_used,
            errors=list(ctx.errors),
            completed_tasks=completed,
            session_id=ctx.session_id or "",
        )

    async def _run_reflection(self, ctx: ExecutionContext) -> Optional[ReflectionReport]:
        try:
            snapshot = self._build_snapshot(ctx)
            report = self._reflection_engine.reflect(snapshot)
            ctx.reflection_report = report

            # Store in memory
            if ctx.session_id:
                session = self._memory.get_or_create_session(ctx.session_id)
                if session.metadata is None:
                    session.metadata = {}
                session.metadata["reflection_report"] = report.to_dict()

            # Publish reflection event
            self._publish(FridayEvent(topic="ReflectionCompleted", data=report.to_dict()))

            # Update execution state with reflection data
            state = ExecutionStateModel()
            state.goal = ctx.prompt[:200]
            state.execution_stage = Stage.REFLECTION.value
            state.stage_status = "completed"
            state.reflection_score = report.execution_quality_score
            state.reflection_summary = (
                f"Succeeded: {len(report.what_succeeded)} | "
                f"Failed: {len(report.what_failed)} | "
                f"Score: {report.execution_quality_score:.2f}"
            )
            self._publish(FridayEvent(topic="ExecutionStateUpdated", data=state.to_dict()))

            logger.info(
                f"Reflection complete: quality={report.execution_quality_score:.2f}, "
                f"succeeded={len(report.what_succeeded)}, "
                f"failed={len(report.what_failed)}"
            )

            return report

        except Exception as e:
            logger.error(f"Reflection failed: {e}")
            return None

    def _register_stages(self) -> None:
        self._pipeline.register_stage(Stage.PLANNING, self._run_planning)
        self._pipeline.register_stage(Stage.MEMORY, self._run_memory)
        self._pipeline.register_stage(Stage.GOAL_PLANNING, self._run_goal_planning)
        self._pipeline.register_stage(Stage.TOOL_SELECTION, self._run_tool_selection)
        self._pipeline.register_stage(Stage.EXECUTION, self._run_execution)
        self._pipeline.register_stage(Stage.REFLECTION, self._run_reflection)
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

        ws = self._workspace_context
        if ws:
            ctx.memory_context = f"[Workspace]\n{ws.to_context_string()}\n\n{history_str}"
        else:
            ctx.memory_context = history_str

        return ctx.memory_context

    async def _run_goal_planning(self, ctx: ExecutionContext) -> Any:
        self._ensure_workspace()
        ctx.workspace_context = self._workspace_context

        # Store workspace summary in memory
        if self._workspace_summary and ctx.session_id:
            try:
                session = self._memory.get_or_create_session(ctx.session_id)
                if session.metadata is None:
                    session.metadata = {}
                session.metadata["workspace_summary"] = self._workspace_summary.to_dict()
            except Exception:
                pass

        goal_plan = self._goal_planner.create_goal_plan(
            prompt=ctx.prompt,
            intent=ctx.intent,
            plan=ctx.plan,
            workspace=self._workspace_context,
        )
        ctx.goal_plan = goal_plan

        logger.info(f"Goal: {goal_plan.goal}")
        logger.info(f"Plan: {goal_plan.task_count} task(s), capabilities={goal_plan.capabilities}")

        self._publish_execution_state(ctx, Stage.GOAL_PLANNING.value)

        return goal_plan

    async def _run_tool_selection(self, ctx: ExecutionContext) -> Any:
        plan = ctx.plan
        if not plan:
            return None

        if not self._tool_selection_engine:
            return None

        has_plan_steps = hasattr(plan, "steps") and plan.steps
        has_goal_tasks = ctx.goal_plan is not None and ctx.goal_plan.task_count > 0

        if not has_plan_steps and not has_goal_tasks:
            return None

        # Derive capabilities from goal_plan if available, otherwise from execution plan
        from app.tool_selection.base import ToolSelectionContext

        if has_goal_tasks:
            capabilities = ctx.goal_plan.capabilities
        else:
            capabilities = getattr(plan, "capabilities", [])

        ws = self._workspace_context
        pipeline_metadata = {}
        if ws:
            pipeline_metadata["workspace_framework"] = ws.framework
            pipeline_metadata["workspace_languages"] = ",".join(ws.detected_languages)
            pipeline_metadata["workspace_project_type"] = ws.project_type

        sel_ctx = ToolSelectionContext(
            required_capabilities=capabilities,
            pipeline_metadata=pipeline_metadata if pipeline_metadata else None,
        )
        sel_result = await self._tool_selection_engine.select(sel_ctx)
        ctx.selected_tools = sel_result

        for st in sel_result.selected_tools:
            logger.info(
                f"Tool selected: {st.tool.id} "
                f"(score={st.score}, confidence={st.confidence}, "
                f"reason=\"{st.selection_reason}\", "
                f"fallback={st.is_fallback})"
            )

        # Log which capabilities mapped to which tools
        logger.info(f"Execution Result: {len(sel_result.selected_tools)} tool(s) selected")

        self._publish_execution_state(ctx)

        return sel_result

    async def _run_execution(self, ctx: ExecutionContext) -> str:
        if ctx.metadata.get("_iterative_done"):
            return ctx.tool_output or ""

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
        log_line = f"Exec Result: {'success' if tool_output and 'Error' not in tool_output else 'completed'}"
        if ctx.selected_tools and hasattr(ctx.selected_tools, 'selected_tools'):
            tools_str = ", ".join(st.tool.id for st in ctx.selected_tools.selected_tools[:3])
            log_line += f" tools=[{tools_str}]"
        logger.info(log_line)

        self._publish_execution_state(ctx)

        return tool_output

        if self._tool_execution_engine and ctx.selected_tools and hasattr(ctx.selected_tools, 'selected_tools') and ctx.selected_tools.selected_tools:
            from app.tool_execution.base import ExecutionMode
            from app.tool_selection.base import ToolSelectionResult

            # Group selected tools by primary: each primary + its dependencies
            all_st = ctx.selected_tools.selected_tools
            primaries = [
                st for st in all_st
                if not st.is_fallback and "Dependency of" not in st.selection_reason
            ]

            fallback_chain: List[str] = []
            final_output = ""
            final_sel_result = None

            for rank, primary in enumerate(primaries):
                if rank > 0:
                    fallback_chain.append(primary.tool.id)
                    logger.info(
                        f"Exec fallback #{rank}: {primary.tool.id} "
                        f"(confidence={primary.confidence})"
                    )

                # Build group: primary + its dependencies
                primary_id = primary.tool.id
                group = [primary]
                for dep in primary.tool.dependencies:
                    dep_st = next(
                        (st for st in all_st if st.tool.id == dep.tool_id),
                        None,
                    )
                    if dep_st is not None:
                        group.append(dep_st)

                group_selection = ToolSelectionResult(
                    selected_tools=group,
                    selection_scores={st.tool.id: st.score for st in group},
                    selection_reasons={st.tool.id: st.selection_reason for st in group},
                )

                sel_result = await self._tool_execution_engine.execute(
                    selection_result=group_selection,
                    mode=ExecutionMode.SEQUENTIAL,
                    global_timeout=120.0,
                    cancellation_token=ctx.cancellation_token,
                )
                final_sel_result = sel_result

                if sel_result and hasattr(sel_result, 'all_succeeded'):
                    outputs = []
                    for r in sel_result.results:
                        if r.output:
                            outputs.append(str(r.output))
                    final_output = "\n".join(outputs)

                    if sel_result.all_succeeded:
                        break
                else:
                    break

            if fallback_chain:
                logger.info(f"Fallback chain: {' -> '.join(fallback_chain)}")

            tool_output = final_output
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
            await self._run_goal_planning(ctx)
            await self._run_tool_selection(ctx)
            await self._run_execution(ctx)
            await self._run_reflection(ctx)
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
