import time
import uuid
import socket
from loguru import logger
from typing import List, Dict, Any, AsyncGenerator, Optional

from app.orion.intent import IntentClassifier, IntentType
from app.memory.conversation import ConversationMemory
from app.memory.embeddings import EmbeddingsManager
from app.orion.prompt_manager import PromptManager
from app.orion.context import SystemContext
from app.orion.tool_registry import ToolRegistry
from app.llm.router import LLMRouter
from app.orion.response import OrionResponse, OrionTelemetry
from app.orion.planner import Planner
from app.orion.executor import ToolExecutor
from app.orion.plan_adapter import execution_plan_to_input, extract_tool_output, format_tool_output_for_prompt

class OrionOrchestrator:
    """
    Coordinates ORION Core intelligence logic and pipeline pathways:
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
        logger.info("OrionOrchestrator coordinates initialized with Action Engine modules.")

    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    async def _calculate_telemetry(self, provider_name: str, prompt: str, response: str) -> OrionTelemetry:
        try:
            provider = self.llm_router.get_provider(provider_name)
            if hasattr(provider, '_get_model'):
                model = provider._get_model()
                p_count = model.count_tokens(prompt).total_tokens
                c_count = model.count_tokens(response).total_tokens
                return OrionTelemetry(
                    model=provider_name,
                    prompt_tokens=p_count,
                    completion_tokens=c_count,
                    total_tokens=p_count + c_count
                )
        except Exception:
            pass
        
        p_est = self._estimate_tokens(prompt)
        c_est = self._estimate_tokens(response)
        return OrionTelemetry(
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
        intent = await self.intent_classifier.classify(prompt)
        plan = await self.planner.plan(prompt, intent)
        if plan:
            exec_result = await self.tool_executor.execute(plan, confirmed, confirmation_token)
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
    ) -> OrionResponse:
        start_time = time.time()
        sess_id = session_id or str(uuid.uuid4())
        
        logger.info(f"Incoming request: session={sess_id}, provider={provider_name}")

        # 1. Intent Classifier
        intent = await self.intent_classifier.classify(prompt)
        logger.info(f"Selected intent: {intent.value}")

        # 2. Planner & Tool Execution
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

                if exec_result.confirmation_required:
                    latency_ms = (time.time() - start_time) * 1000
                    return OrionResponse(
                        success=False,
                        intent=intent.value,
                        response=exec_result.output,
                        tool_used=tool_used,
                        session_id=sess_id,
                        execution_time_ms=latency_ms,
                        telemetry=OrionTelemetry(model=provider_name, error="ConfirmationRequired"),
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

        # 4. Formulate Prompt using Prompt Builder
        system_instruction = (
            "You are ORION, the central AI operating system core. Be helpful and direct."
        )
        if tool_used:
            system_instruction += f"\n[Executed Tool: {tool_used}. Output results: {tool_output}]"

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
            return OrionResponse(
                success=False,
                intent=intent.value,
                response=f"Configuration Error: {str(e)}",
                tool_used=tool_used,
                session_id=sess_id,
                execution_time_ms=latency_ms,
                telemetry=OrionTelemetry(model=provider_name, error=f"MissingAPIKey: {str(e)}")
            )
        except (socket.timeout, socket.error) as e:
            logger.error(f"Timeout/Network Error: {str(e)}")
            latency_ms = (time.time() - start_time) * 1000
            return OrionResponse(
                success=False,
                intent=intent.value,
                response="Provider Timeout: The connection timed out.",
                tool_used=tool_used,
                session_id=sess_id,
                execution_time_ms=latency_ms,
                telemetry=OrionTelemetry(model=provider_name, error=f"Timeout: {str(e)}")
            )
        except Exception as e:
            err_msg = str(e)
            logger.error(f"LLM API Error: {type(e).__name__}: {err_msg}")
            latency_ms = (time.time() - start_time) * 1000
            
            err_type = "ProviderUnavailable"
            if "exhausted" in err_msg.lower() or "limit" in err_msg.lower():
                err_type = "RateLimit"

            return OrionResponse(
                success=False,
                intent=intent.value,
                response=f"AI Engine Error: {err_msg}",
                tool_used=tool_used,
                session_id=sess_id,
                execution_time_ms=latency_ms,
                telemetry=OrionTelemetry(model=provider_name, error=f"{err_type}: {err_msg}")
            )

        # 6. Update Memory
        self.memory.add_message(sess_id, "user", prompt)
        self.memory.add_message(sess_id, "assistant", llm_response)
        
        self.memory.update_context(sess_id, f"Intent: {intent.value}")
        logger.info(f"Memory updates: logged chat message and context for session {sess_id}.")

        # 7. Response Formatter with Telemetry
        latency_ms = (time.time() - start_time) * 1000
        telemetry = await self._calculate_telemetry(provider_name, full_prompt, llm_response)
        
        logger.info(f"Latency: {latency_ms:.2f}ms. Total Tokens: {telemetry.total_tokens}")

        return OrionResponse(
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
        logger.info(f"Incoming stream request: session={sess_id}, provider={provider_name}")

        intent = await self.intent_classifier.classify(prompt)
        
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
        
        system_instruction = "You are ORION, the central AI operating system core. Stream text."
        if tool_used:
            system_instruction += f"\n[Executed Tool: {tool_used}. Output results: {tool_output}]"

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
        logger.info(f"Memory updates: logged streamed assistant response for session {sess_id}.")
