from typing import Dict, Any
from loguru import logger

from app.agents.base import BaseAgent
from app.agents.models import AgentTask


class WorkflowWorkerAgent(BaseAgent):
    def __init__(
        self,
        agent_id: str = "workflow-worker",
        name: str = "Workflow Worker",
        shared_context: Any = None
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            name=name,
            capabilities=[
                "tool", "llm", "knowledge", "condition",
                "delay", "mission", "agent_task", "notification"
            ],
            permissions=["workflow"],
            description="Generic worker agent that handles workflow step execution"
        )
        self._shared_context = shared_context

    async def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        step_type = task.payload.get("step_type", "")
        inputs = task.payload.get("inputs", {})

        logger.info(f"WorkflowWorker executing step '{task.task_id}' type='{step_type}'")

        if step_type == "tool":
            return await self._execute_tool(inputs)
        elif step_type == "llm":
            return await self._execute_llm(inputs)
        elif step_type == "knowledge":
            return await self._execute_knowledge(inputs)
        elif step_type == "condition":
            return self._execute_condition(inputs)
        elif step_type == "delay":
            return await self._execute_delay(inputs)
        elif step_type == "mission":
            return await self._execute_mission(inputs)
        elif step_type == "notification":
            return await self._execute_notification(inputs)
        elif step_type == "agent_task":
            return await self._execute_agent_task(inputs)
        else:
            raise ValueError(f"Unknown step type: {step_type}")

    async def _execute_tool(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        tool_name = inputs.get("tool_name", "")
        args = inputs.get("args", {})
        ctx = self._context
        if ctx and hasattr(ctx, "execute_tool"):
            result = await ctx.execute_tool(tool_name, **args)
            return {"result": result, "tool": tool_name}
        raise RuntimeError(f"SharedContext unavailable for tool '{tool_name}'")

    async def _execute_llm(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        prompt = inputs.get("prompt", "")
        provider = inputs.get("provider")
        ctx = self._context
        if ctx and hasattr(ctx, "generate_llm"):
            response = await ctx.generate_llm(prompt, provider=provider)
            return {"response": response}
        raise RuntimeError("SharedContext unavailable for LLM generation")

    async def _execute_knowledge(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        query = inputs.get("query", "")
        top_k = inputs.get("top_k", 5)
        ctx = self._context
        if ctx and hasattr(ctx, "query_knowledge"):
            results = await ctx.query_knowledge(query, top_k=top_k)
            return {"results": results, "count": len(results)}
        raise RuntimeError("SharedContext unavailable for knowledge query")

    def _execute_condition(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        import operator
        left = inputs.get("left")
        op = inputs.get("operator", "eq")
        right = inputs.get("right")
        ops = {
            "eq": operator.eq, "ne": operator.ne,
            "gt": operator.gt, "ge": operator.ge,
            "lt": operator.lt, "le": operator.le,
            "in": lambda a, b: a in b,
            "contains": lambda a, b: b in a if isinstance(a, str) else False,
        }
        fn = ops.get(op, operator.eq)
        result = fn(left, right)
        return {"condition_result": result, "left": left, "operator": op, "right": right}

    async def _execute_delay(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        import asyncio
        seconds = float(inputs.get("seconds", 1))
        await asyncio.sleep(seconds)
        return {"delayed_seconds": seconds}

    async def _execute_mission(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        ctx = self._context
        if ctx and ctx.kernel:
            mission_engine = ctx.kernel.get_service("mission_engine")
            if mission_engine and hasattr(mission_engine, "create_mission"):
                from app.missions.mission_manager import CreateMissionRequest
                request = CreateMissionRequest(
                    name=inputs.get("name", "Workflow Mission"),
                    description=inputs.get("description", ""),
                    priority=inputs.get("priority", "NORMAL"),
                    type=inputs.get("type", "USER_DEFINED"),
                    metadata=inputs.get("metadata", {})
                )
                mission = await mission_engine.create_mission(request)
                await mission_engine.queue_mission(mission.id)
                await mission_engine.start_mission(mission.id)
                return {"mission_id": mission.id, "status": mission.status}
        raise RuntimeError("MissionEngine unavailable")

    async def _execute_notification(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        ctx = self._context
        if ctx and ctx.event_bus:
            from app.events.events import OrionEvent
            topic = inputs.get("topic", "WorkflowNotification")
            message = inputs.get("message", "")
            await ctx.publish_event(topic, {
                "message": message,
                "source": "workflow-worker"
            })
            return {"notified": True, "topic": topic}
        raise RuntimeError("EventBus unavailable for notification")

    async def _execute_agent_task(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        sub_type = inputs.get("sub_type", "")
        sub_inputs = inputs.get("inputs", {})
        return await self.execute_task(AgentTask(
            task_id=inputs.get("task_id", "sub-task"),
            type=sub_type,
            payload={"step_type": sub_type, "inputs": sub_inputs}
        ))
