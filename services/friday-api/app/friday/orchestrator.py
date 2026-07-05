import time
import uuid
import socket
from loguru import logger
from typing import List, Dict, Any, AsyncGenerator, Optional

from app.friday.intent import IntentClassifier, IntentType as IntentTypeEnum
from app.memory import ConversationMemory, EmbeddingsManager
from app.friday.prompt_manager import PromptManager
from app.friday.context import SystemContext
from app.friday.tool_registry import ToolRegistry
from app.llm.router import LLMRouter
from app.friday.response import FridayResponse, FridayTelemetry
from app.friday.planner import Planner
from app.friday.executor import ToolExecutor
from app.friday.plan_adapter import execution_plan_to_input, extract_tool_output, format_tool_output_for_prompt
from app.events.events import FridayEvent

class FridayOrchestrator:
    """
    Coordinates FRIDAY Core intelligence logic and pipeline pathways:
    API -> Intent Classifier -> Planner -> Tool Executor / Workflow Runtime -> Tools -> Prompts -> LLM Router -> Response Formatter.
    """
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
    ) -> None:
        self.llm_router = llm_router
        self.intent_classifier = intent_classifier
        self.memory = memory
        self.prompt_manager = prompt_manager
        self.tool_registry = tool_registry
        self.embeddings = embeddings
        self.planner = Planner()
        self.tool_executor = ToolExecutor(tool_registry)
        self._runtime_bridge = runtime_bridge
        self._event_bus = event_bus
        self._mission_runtime = mission_runtime
        logger.info("FridayOrchestrator coordinates initialized with Action Engine modules.")

    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    async def _calculate_telemetry(self, provider_name: str, prompt: str, response: str) -> FridayTelemetry:
        try:
            provider = self.llm_router.get_provider(provider_name)
            if hasattr(provider, 'api_key') and provider.api_key and provider.api_key.startswith("AQ."):
                raise ValueError("Bypassing network call for mock key.")
            if hasattr(provider, '_get_model'):
                model = provider._get_model()
                p_count = model.count_tokens(prompt).total_tokens
                c_count = model.count_tokens(response).total_tokens
                return FridayTelemetry(
                    model=provider_name,
                    prompt_tokens=p_count,
                    completion_tokens=c_count,
                    total_tokens=p_count + c_count
                )
        except Exception:
            pass
        
        p_est = self._estimate_tokens(prompt)
        c_est = self._estimate_tokens(response)
        return FridayTelemetry(
            model=provider_name,
            prompt_tokens=p_est,
            completion_tokens=c_est,
            total_tokens=p_est + c_est
        )

    async def check_confirmation(
        self,
        prompt: str,
        confirmed: bool = False,
        confirmation_token: str | None = None
    ) -> tuple[bool, str | None, str | None, str | None]:
        """
        Check if the prompt triggers a tool call requiring user confirmation.
        Returns: (requires_confirmation, token, warning_message, tool_name)
        """
        print("[DEBUG ORCH] Entering check_confirmation", flush=True)
        intent = await self.intent_classifier.classify(prompt)
        print(f"[DEBUG ORCH] intent classified: {intent}", flush=True)
        plan = await self.planner.plan(prompt, intent)
        print(f"[DEBUG ORCH] plan resolved: {plan}", flush=True)
        if plan:
            print("[DEBUG ORCH] plan is not None, executing tool_executor.execute", flush=True)
            exec_result = await self.tool_executor.execute(plan, confirmed, confirmation_token)
            print(f"[DEBUG ORCH] tool_executor.execute returned success={exec_result.success if exec_result else None}", flush=True)
            if exec_result.confirmation_required:
                return True, exec_result.confirmation_token, exec_result.output, plan.tool_name
        return False, None, None, None

    async def process_query(
        self, 
        prompt: str, 
        session_id: str | None = None, 
        provider_name: str = "gemini",
        confirmed: bool = False,
        confirmation_token: str | None = None
    ) -> FridayResponse:
        start_time = time.time()
        sess_id = session_id or str(uuid.uuid4())
        
        if self._event_bus:
            self._event_bus.publish_background(FridayEvent(topic="ConversationReceived", data={
                "session_id": sess_id, "prompt": prompt
            }))
        
        logger.info(f"Incoming request: session={sess_id}, provider={provider_name}")

        # 1. Intent Classifier
        intent = await self.intent_classifier.classify(prompt)
        logger.info(f"Selected intent: {intent.value}")

        # 1a. Delegate AUTONOMOUS_GOAL to MissionRuntime
        if intent == IntentTypeEnum.AUTONOMOUS_GOAL and self._mission_runtime:
            return await self._handle_autonomous_goal(prompt, sess_id, provider_name)

        # 2. Planner & Tool Execution
        tool_used = None
        tool_output = ""

        plan = await self.planner.plan(prompt, intent)
        if plan:
            tool_used = plan.tool_name

            if self._runtime_bridge and plan.steps:
                # Check confirmation before Workflow Runtime path
                if not confirmed:
                    conf_check = await self.tool_executor.check_confirmation(plan)
                    if conf_check and conf_check.confirmation_required:
                        latency_ms = (time.time() - start_time) * 1000
                        return FridayResponse(
                            success=False, intent=intent.value,
                            response=conf_check.output, tool_used=tool_used,
                            session_id=sess_id, execution_time_ms=latency_ms,
                            telemetry=FridayTelemetry(model=provider_name, error="ConfirmationRequired"),
                            confirmation_required=True,
                            confirmation_token=conf_check.confirmation_token
                        )

                runtime_input = execution_plan_to_input(plan)
                workflow = await self._runtime_bridge.submit_and_wait(runtime_input)
                tool_outputs = extract_tool_output(workflow)
                if tool_outputs:
                    tool_output = format_tool_output_for_prompt(tool_outputs)
                else:
                    tool_output = "Workflow completed but no tool output captured."
            else:
                exec_result = await self.tool_executor.execute(plan, confirmed, confirmation_token)

                if exec_result.confirmation_required:
                    latency_ms = (time.time() - start_time) * 1000
                    return FridayResponse(
                        success=False, intent=intent.value,
                        response=exec_result.output, tool_used=tool_used,
                        session_id=sess_id, execution_time_ms=latency_ms,
                        telemetry=FridayTelemetry(model=provider_name, error="ConfirmationRequired"),
                        confirmation_required=True,
                        confirmation_token=exec_result.confirmation_token
                    )

                if exec_result.success:
                    tool_output = exec_result.output
                else:
                    tool_output = f"Error executing tool: {exec_result.error}"

        if tool_used:
            logger.info(f"Tool usage: '{tool_used}' triggered. Output: {tool_output[:40]}...")

        # 3. Context & History loading
        sys_context = SystemContext()
        session = self.memory.get_or_create_session(sess_id)
        
        # Save executed tool info into the ChatSession
        session.tool_used = tool_used
        session.tool_output = tool_output

        history_str = self.memory.get_history_string(sess_id)
        available_tools_list = list(self.tool_registry.list_tools().keys())

        vision_context_str = ""
        if session.context and isinstance(session.context, dict):
            last_vision = session.context.get("last_vision")
            if last_vision and last_vision.get("has_text"):
                vision_context_str = f"\n[Previous Screen Context]:\n{last_vision.get('ocr_text', '')}"
                if last_vision.get("element_count", 0) > 0:
                    vision_context_str += f"\n[UI Elements Detected: {last_vision['element_count']}]"

        # 4. Formulate Prompt using Prompt Builder
        system_instruction = (
            "You are FRIDAY, the central AI operating system core. Be helpful and direct."
        )
        if tool_used:
            system_instruction += f"\n[Executed Tool: {tool_used}. Output results: {tool_output}]"

        if vision_context_str:
            system_instruction += vision_context_str

        session_meta = {
            "session_id": sess_id,
            "created_at": session.created_at,
            "platform": sys_context.platform,
            "status": sys_context.status
        }

        full_prompt = self.prompt_manager.format_prompt(
            system_instruction=system_instruction,
            user_message=prompt,
            history=history_str,
            available_tools=available_tools_list,
            session_metadata=session_meta,
            retrieved_context=tool_output if tool_used == "knowledge.search" else None
        )

        # 5. Route to provider via LLMRouter
        try:
            logger.info(f"Chosen model provider: {provider_name}")
            provider = self.llm_router.get_provider(provider_name)
            llm_response = await provider.generate(full_prompt)
        except ValueError as e:
            logger.error(f"Configuration/Initialization Error: {str(e)}")
            latency_ms = (time.time() - start_time) * 1000
            return FridayResponse(
                success=False,
                intent=intent.value,
                response=f"Configuration Error: {str(e)}",
                tool_used=tool_used,
                session_id=sess_id,
                execution_time_ms=latency_ms,
                telemetry=FridayTelemetry(model=provider_name, error=f"MissingAPIKey: {str(e)}")
            )
        except (socket.timeout, socket.error) as e:
            logger.error(f"Timeout/Network Error: {str(e)}")
            latency_ms = (time.time() - start_time) * 1000
            return FridayResponse(
                success=False,
                intent=intent.value,
                response="Provider Timeout: The connection timed out.",
                tool_used=tool_used,
                session_id=sess_id,
                execution_time_ms=latency_ms,
                telemetry=FridayTelemetry(model=provider_name, error=f"Timeout: {str(e)}")
            )
        except Exception as e:
            err_msg = str(e)
            logger.error(f"LLM API Error: {type(e).__name__}: {err_msg}")
            latency_ms = (time.time() - start_time) * 1000
            
            err_type = "ProviderUnavailable"
            if "exhausted" in err_msg.lower() or "limit" in err_msg.lower():
                err_type = "RateLimit"

            return FridayResponse(
                success=False,
                intent=intent.value,
                response=f"AI Engine Error: {err_msg}",
                tool_used=tool_used,
                session_id=sess_id,
                execution_time_ms=latency_ms,
                telemetry=FridayTelemetry(model=provider_name, error=f"{err_type}: {err_msg}")
            )

        # 6. Update Memory
        self.memory.add_message(sess_id, "user", prompt)
        self.memory.add_message(sess_id, "assistant", llm_response)
        
        self.memory.update_context(sess_id, f"Intent: {intent.value}")
        logger.info(f"Memory updates: logged chat message and context for session {sess_id}.")

        if self._event_bus:
            self._event_bus.publish_background(FridayEvent(topic="ConversationCompleted", data={
                "session_id": sess_id, "turn_count": len(self.memory.get_session(sess_id).messages) if self.memory.get_session(sess_id) else 0
            }))

        # 7. Response Formatter with Telemetry
        latency_ms = (time.time() - start_time) * 1000
        telemetry = await self._calculate_telemetry(provider_name, full_prompt, llm_response)
        
        logger.info(f"Latency: {latency_ms:.2f}ms. Total Tokens: {telemetry.total_tokens}")

        return FridayResponse(
            success=True,
            intent=intent.value,
            response=llm_response,
            tool_used=tool_used,
            session_id=sess_id,
            execution_time_ms=latency_ms,
            telemetry=telemetry
        )

    async def process_stream(
        self,
        prompt: str,
        session_id: str | None = None,
        provider_name: str = "gemini",
        confirmed: bool = False,
        confirmation_token: str | None = None
    ) -> AsyncGenerator[str, None]:
        sess_id = session_id or str(uuid.uuid4())
        if self._event_bus:
            self._event_bus.publish_background(FridayEvent(topic="ConversationReceived", data={
                "session_id": sess_id, "prompt": prompt
            }))
        logger.info(f"Incoming stream request: session={sess_id}, provider={provider_name}")

        intent = await self.intent_classifier.classify(prompt)

        if intent == IntentTypeEnum.AUTONOMOUS_GOAL and self._mission_runtime:
            response = await self._handle_autonomous_goal(prompt, sess_id, provider_name)
            yield response.response
            return

        tool_used = None
        tool_output = ""

        plan = await self.planner.plan(prompt, intent)
        if plan:
            tool_used = plan.tool_name

            if self._runtime_bridge and plan.steps:
                runtime_input = execution_plan_to_input(plan)
                workflow = await self._runtime_bridge.submit_and_wait(runtime_input)
                tool_outputs = extract_tool_output(workflow)
                if tool_outputs:
                    tool_output = format_tool_output_for_prompt(tool_outputs)
                else:
                    tool_output = "Workflow completed but no tool output captured."
            else:
                exec_result = await self.tool_executor.execute(plan, confirmed, confirmation_token)
                if exec_result.success:
                    tool_output = exec_result.output
                else:
                    tool_output = f"Error executing tool: {exec_result.error}"

        sys_context = SystemContext()
        session = self.memory.get_or_create_session(sess_id)
        
        session.tool_used = tool_used
        session.tool_output = tool_output

        history_str = self.memory.get_history_string(sess_id)
        available_tools_list = list(self.tool_registry.list_tools().keys())

        stream_vision_str = ""
        if session.context and isinstance(session.context, dict):
            last_vision = session.context.get("last_vision")
            if last_vision and last_vision.get("has_text"):
                stream_vision_str = f"\n[Previous Screen Context]:\n{last_vision.get('ocr_text', '')}"
                if last_vision.get("element_count", 0) > 0:
                    stream_vision_str += f"\n[UI Elements Detected: {last_vision['element_count']}]"
        
        system_instruction = "You are FRIDAY, the central AI operating system core. Stream text."
        if tool_used:
            system_instruction += f"\n[Executed Tool: {tool_used}. Output results: {tool_output}]"
        if stream_vision_str:
            system_instruction += stream_vision_str

        session_meta = {
            "session_id": sess_id,
            "created_at": session.created_at,
            "platform": sys_context.platform,
            "status": sys_context.status
        }

        full_prompt = self.prompt_manager.format_prompt(
            system_instruction=system_instruction,
            user_message=prompt,
            history=history_str,
            available_tools=available_tools_list,
            session_metadata=session_meta,
            retrieved_context=tool_output if tool_used == "knowledge.search" else None
        )

        # Update memory pre-streaming
        self.memory.add_message(sess_id, "user", prompt)

        full_response_accum = []
        try:
            provider = self.llm_router.get_provider(provider_name)
            async for chunk in provider.generate_stream(full_prompt):
                full_response_accum.append(chunk)
                yield chunk
        except Exception as e:
            logger.error(f"Streaming prompt processing failed: {str(e)}")
            yield f"\n[STREAM ERROR: {str(e)}]"
            return

        final_resp = "".join(full_response_accum)
        self.memory.add_message(sess_id, "assistant", final_resp)
        self.memory.update_context(sess_id, f"Intent: {intent.value} (streamed)")
        if self._event_bus:
            self._event_bus.publish_background(FridayEvent(topic="ConversationCompleted", data={
                "session_id": sess_id, "turn_count": len(self.memory.get_session(sess_id).messages) if self.memory.get_session(sess_id) else 0
            }))
        logger.info(f"Memory updates: logged streamed assistant response for session {sess_id}.")

    async def _handle_autonomous_goal(
        self,
        prompt: str,
        session_id: str,
        provider_name: str = "gemini",
    ) -> FridayResponse:
        start_time = time.time()
        mission_id = await self._mission_runtime.submit_background(
            user_request=prompt,
            intent="AUTONOMOUS_GOAL",
            metadata={"session_id": session_id},
        )
        latency_ms = (time.time() - start_time) * 1000

        self.memory.add_message(session_id, "user", prompt)
        self.memory.add_message(
            session_id,
            "assistant",
            f"Starting autonomous mission: {mission_id}",
        )
        self.memory.update_context(session_id, f"Intent: AUTONOMOUS_GOAL (mission: {mission_id})")

        if self._event_bus:
            self._event_bus.publish_background(FridayEvent(topic="ConversationCompleted", data={
                "session_id": session_id, "mission_id": mission_id,
            }))

        return FridayResponse(
            success=True,
            intent="AUTONOMOUS_GOAL",
            response=f"Starting autonomous mission for: {prompt}\nYou can track progress and control execution via the mission dashboard.",
            session_id=session_id,
            execution_time_ms=latency_ms,
            telemetry=FridayTelemetry(model=provider_name),
            mission_id=mission_id,
        )
