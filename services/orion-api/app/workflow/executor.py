"""
Workflow Node Executor — routes each node to the appropriate ORION subsystem.

Each handler:
  1. Resolves input variables via variables.resolve_variables()
  2. Calls the target subsystem
  3. Returns an outputs dict that gets merged back into the workflow runtime

Node type dispatch:
  DESKTOP_ACTION  → DesktopAutomationService / DesktopController
  MISSION         → MissionManager
  LLM_PROMPT      → LLMRouter
  KNOWLEDGE_QUERY → RetrievalEngine
  PLANNER_STEP    → Planner
  CONDITION       → conditions.evaluate_condition()
  DELAY           → asyncio.sleep
  NOTIFICATION    → EventBus.publish()
"""
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from loguru import logger

from app.workflow.workflow import Workflow, WorkflowNode, WorkflowNodeType
from app.workflow.variables import resolve_variables
from app.workflow.conditions import evaluate_condition


class WorkflowNodeExecutor:
    """
    Dispatches individual workflow nodes to their target subsystems.
    Uses dependency-injected service references passed from WorkflowEngine.
    """

    def __init__(
        self,
        mission_engine: Optional[Any] = None,
        desktop_automation: Optional[Any] = None,
        desktop_controller: Optional[Any] = None,
        knowledge_engine: Optional[Any] = None,
        planner: Optional[Any] = None,
        llm_router: Optional[Any] = None,
        event_bus: Optional[Any] = None,
    ) -> None:
        self._mission_engine      = mission_engine
        self._desktop_automation  = desktop_automation
        self._desktop_controller  = desktop_controller
        self._knowledge_engine    = knowledge_engine
        self._planner             = planner
        self._llm_router          = llm_router
        self._event_bus           = event_bus

    # -----------------------------------------------------------------------
    # Public entry point
    # -----------------------------------------------------------------------

    async def execute_node(
        self,
        node: WorkflowNode,
        workflow: Workflow
    ) -> Dict[str, Any]:
        """
        Executes a single workflow node and returns its output dict.

        Args:
            node:     The WorkflowNode to execute.
            workflow: The owning Workflow (for variable resolution context).

        Returns:
            Dict of outputs to be merged into workflow.variables via merge_outputs().

        Raises:
            RuntimeError on unrecoverable execution errors.
        """
        # Resolve all input template references
        resolved_inputs: Dict[str, Any] = resolve_variables(
            node.inputs, workflow.variables, workflow.nodes
        )

        node_type = node.type.upper().replace(" ", "_")
        logger.info(
            f"[Executor] Executing node '{node.id}' "
            f"type={node.type} workflow='{workflow.name}'"
        )

        try:
            if node_type == WorkflowNodeType.DESKTOP_ACTION.name or node.type == WorkflowNodeType.DESKTOP_ACTION.value:
                return await self._run_desktop_action(node, resolved_inputs, workflow)

            elif node_type == WorkflowNodeType.MISSION.name or node.type == WorkflowNodeType.MISSION.value:
                return await self._run_mission(node, resolved_inputs, workflow)

            elif node_type == WorkflowNodeType.LLM_PROMPT.name or node.type == WorkflowNodeType.LLM_PROMPT.value:
                return await self._run_llm_prompt(node, resolved_inputs, workflow)

            elif node_type == WorkflowNodeType.KNOWLEDGE_QUERY.name or node.type == WorkflowNodeType.KNOWLEDGE_QUERY.value:
                return await self._run_knowledge_query(node, resolved_inputs, workflow)

            elif node_type == WorkflowNodeType.PLANNER_STEP.name or node.type == WorkflowNodeType.PLANNER_STEP.value:
                return await self._run_planner_step(node, resolved_inputs, workflow)

            elif node_type == WorkflowNodeType.CONDITION.name or node.type == WorkflowNodeType.CONDITION.value:
                return await self._run_condition(node, resolved_inputs, workflow)

            elif node_type == WorkflowNodeType.DELAY.name or node.type == WorkflowNodeType.DELAY.value:
                return await self._run_delay(node, resolved_inputs, workflow)

            elif node_type == WorkflowNodeType.NOTIFICATION.name or node.type == WorkflowNodeType.NOTIFICATION.value:
                return await self._run_notification(node, resolved_inputs, workflow)

            else:
                logger.warning(
                    f"[Executor] Unknown node type '{node.type}' for node '{node.id}'. "
                    "Treating as no-op."
                )
                return {"result": "noop", "node_type": node.type}

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[Executor] Node '{node.id}' failed: {e}")
            raise RuntimeError(f"Node '{node.id}' execution failed: {e}") from e

    # -----------------------------------------------------------------------
    # Handlers
    # -----------------------------------------------------------------------

    async def _run_desktop_action(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any],
        workflow: Workflow
    ) -> Dict[str, Any]:
        """Routes to DesktopAutomationService or DesktopController."""
        action = inputs.get("action", "")
        kwargs = {k: v for k, v in inputs.items() if k != "action"}

        if self._desktop_automation:
            # Enqueue as a pseudo-mission action
            mission_id = inputs.get("mission_id") or f"wf_{workflow.id}_{node.id}"
            self._desktop_automation.add_mission(mission_id)
            logger.info(f"[Executor] Desktop action '{action}' queued as mission '{mission_id}'")
            return {"mission_id": mission_id, "action": action, "queued": True}

        if self._desktop_controller:
            method = getattr(self._desktop_controller, action, None)
            if callable(method):
                result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: method(**kwargs)
                )
                return {"result": result, "action": action}

        logger.warning(f"[Executor] No desktop service available for action '{action}'")
        return {"result": None, "action": action, "error": "no_desktop_service"}

    async def _run_mission(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any],
        workflow: Workflow
    ) -> Dict[str, Any]:
        """Creates and starts a mission via MissionManager."""
        if not self._mission_engine:
            raise RuntimeError("MissionEngine not available for MISSION node")

        from app.missions.mission_manager import CreateMissionRequest
        request = CreateMissionRequest(
            name=inputs.get("name", node.name),
            description=inputs.get("description", f"Workflow '{workflow.name}' — node '{node.id}'"),
            priority=inputs.get("priority", "NORMAL"),
            type=inputs.get("type", "USER_DEFINED"),
            metadata=inputs.get("metadata", {})
        )
        mission_response = await self._mission_engine.create_mission(request)
        mission_id = mission_response.id
        await self._mission_engine.queue_mission(mission_id)
        await self._mission_engine.start_mission(mission_id)
        logger.info(f"[Executor] Mission '{mission_id}' created and started for node '{node.id}'")
        return {
            "mission_id": mission_id,
            "mission_name": mission_response.name,
            "mission_status": mission_response.status
        }

    async def _run_llm_prompt(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any],
        workflow: Workflow
    ) -> Dict[str, Any]:
        """Sends a prompt to the LLMRouter and returns the text response."""
        if not self._llm_router:
            raise RuntimeError("LLMRouter not available for LLM_PROMPT node")

        prompt = inputs.get("prompt", "")
        model  = inputs.get("model")
        logger.info(f"[Executor] LLM prompt for node '{node.id}': {prompt[:80]}...")

        response_text = await self._llm_router.generate(
            prompt=prompt,
            provider=inputs.get("provider"),
            model=model
        )
        return {"response": response_text, "prompt": prompt}

    async def _run_knowledge_query(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any],
        workflow: Workflow
    ) -> Dict[str, Any]:
        """Queries the RetrievalEngine knowledge base."""
        if not self._knowledge_engine:
            raise RuntimeError("KnowledgeEngine not available for KNOWLEDGE_QUERY node")

        query  = inputs.get("query", "")
        top_k  = inputs.get("top_k", 5)
        logger.info(f"[Executor] Knowledge query for node '{node.id}': '{query}'")

        results = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._knowledge_engine.retrieve(query, top_k=top_k)
        )
        return {"results": results, "query": query, "count": len(results) if results else 0}

    async def _run_planner_step(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any],
        workflow: Workflow
    ) -> Dict[str, Any]:
        """Invokes the Planner to generate a mission plan."""
        if not self._planner:
            raise RuntimeError("Planner not available for PLANNER_STEP node")

        goal    = inputs.get("goal", "")
        context = inputs.get("context", {})
        logger.info(f"[Executor] Planner step for node '{node.id}' goal='{goal}'")

        plan = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._planner.plan(goal=goal, context=context)
        )
        return {"plan": plan, "goal": goal}

    async def _run_condition(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any],
        workflow: Workflow
    ) -> Dict[str, Any]:
        """Evaluates a condition and returns the boolean result."""
        condition_config = node.condition
        if not condition_config:
            # Fallback: read from inputs
            ctype  = inputs.get("condition_type", "boolean")
            params = inputs.get("params", {"value": True})
        else:
            ctype  = condition_config.type
            params = condition_config.params

        result = evaluate_condition(ctype, params, workflow.variables, workflow.nodes)
        logger.info(
            f"[Executor] Condition node '{node.id}' type='{ctype}' result={result}"
        )
        return {"condition_result": result, "condition_type": ctype}

    async def _run_delay(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any],
        workflow: Workflow
    ) -> Dict[str, Any]:
        """Waits for a configured delay in seconds."""
        seconds = float(inputs.get("seconds", node.delay_seconds or 1.0))
        logger.info(f"[Executor] Delay node '{node.id}' — waiting {seconds}s")
        await asyncio.sleep(seconds)
        return {"delayed_seconds": seconds}

    async def _run_notification(
        self,
        node: WorkflowNode,
        inputs: Dict[str, Any],
        workflow: Workflow
    ) -> Dict[str, Any]:
        """Publishes a notification event to the EventBus."""
        message = inputs.get("message", node.name)
        topic   = inputs.get("topic", "WorkflowNotification")
        payload = {
            "message":      message,
            "workflow_id":  workflow.id,
            "workflow_name": workflow.name,
            "node_id":      node.id,
            "node_name":    node.name,
            "timestamp":    datetime.now(timezone.utc).isoformat()
        }
        if self._event_bus:
            from app.events.events import OrionEvent
            await self._event_bus.publish(OrionEvent(topic, payload))
            logger.info(f"[Executor] Notification '{topic}' published for node '{node.id}'")
        return {"notified": True, "topic": topic, "message": message}
