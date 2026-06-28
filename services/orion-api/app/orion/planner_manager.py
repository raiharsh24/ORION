import time
import asyncio
from typing import Dict, Any, List, Optional
from loguru import logger

from app.orion.planner_schema import ExecutionPlan
from app.orion.planner_components import (
    IntentAnalyzer, GoalExtractor, CapabilityResolver,
    TaskClassifier, PlanValidator, ClarificationManager
)
from app.orion.planner_events import (
    PlanCreated, PlanValidated, PlanRejected,
    ClarificationRequested, IntentDetected, CapabilityResolved,
    PlannerError
)
from app.events.events import OrionEvent
from app.orion.intent import IntentType

class PlannerManager:
    """
    Coordinates Intent Analysis, Goal Extraction, Memory checking,
    Capability checking, Task classification, Plan Validation, and EventBus dispatching.
    """
    def __init__(self, event_bus: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self.intent_analyzer = IntentAnalyzer()
        self.goal_extractor = GoalExtractor()
        self.capability_resolver = CapabilityResolver()
        self.task_classifier = TaskClassifier()
        self.plan_validator = PlanValidator()
        self.clarification_manager = ClarificationManager()
        self._pending_tasks: set = set()
        
        # Metrics
        self.planning_latency_sum = 0.0
        self.planning_count = 0
        self.validation_failures = 0
        self.clarification_count = 0
        self.errors_count = 0

    def _safe_publish(self, event: OrionEvent) -> None:
        if not self._event_bus:
            return
        import asyncio
        import inspect
        try:
            if inspect.iscoroutinefunction(self._event_bus.publish):
                try:
                    loop = asyncio.get_running_loop()
                    task = loop.create_task(self._event_bus.publish(event))
                    self._pending_tasks.add(task)
                    task.add_done_callback(self._pending_tasks.discard)
                except RuntimeError:
                    asyncio.run(self._event_bus.publish(event))
            else:
                self._event_bus.publish(event)
        except Exception as e:
            logger.error(f"Failed to publish event to EventBus: {str(e)}")

    async def shutdown(self) -> None:
        for task in list(self._pending_tasks):
            task.cancel()
        if self._pending_tasks:
            await asyncio.wait(self._pending_tasks, timeout=2.0)
        self._pending_tasks.clear()

    async def create_plan(self, prompt: str, legacy_intent: Optional[IntentType] = None) -> ExecutionPlan:
        """
        Runs the step-by-step planning pipeline.
        """
        start_time = time.time()
        self.planning_count += 1
        
        try:
            # 1. Intent Analysis
            intent = self.intent_analyzer.analyze(prompt, legacy_intent)
            self._safe_publish(IntentDetected(query=prompt, intent=intent))
            
            # 2. Goal Extraction
            goal = self.goal_extractor.extract(prompt, intent)
            
            # 3. Memory Requirement Analysis
            memory_required = intent in ["Memory Lookup", "Memory Update", "Project Management"]
            
            # 4. Capability Resolution
            capabilities = self.capability_resolver.resolve_required_capabilities(intent)
            self._safe_publish(CapabilityResolved(intent=intent, capabilities=capabilities))
            
            # 5. Clarification Logic
            clarification_question = self.clarification_manager.check_clarification(prompt, intent)
            
            # 6. Task Classification
            steps = []
            if not clarification_question:
                steps = self.task_classifier.classify_steps(prompt, intent)
                
            # 7. Plan Assembly
            plan = ExecutionPlan(
                intent=intent,
                goal=goal,
                memoryRequired=memory_required,
                toolRequired=len(steps) > 0 and intent != "Conversation",
                clarificationRequired=clarification_question is not None,
                capabilities=capabilities,
                steps=steps,
                priority="high" if intent in ["Terminal Action", "System Control"] else "medium",
                confidence=0.95 if not clarification_question else 1.0
            )
            
            # Backward Compatibility settings for legacy ToolPlan handlers
            if steps and intent != "Conversation":
                import re
                if legacy_intent == IntentType.FILE_OPERATION or intent == "Filesystem Action":
                    plan.tool_name = "filesystem"
                    plan.args = steps[0].get("args", {})
                elif legacy_intent == IntentType.SYSTEM_COMMAND or intent == "Terminal Action":
                    plan.tool_name = "terminal"
                    plan.args = steps[0].get("args", {})
                elif legacy_intent == IntentType.OPEN_APP:
                    plan.tool_name = "open_app"
                    words = prompt.split()
                    app_name = "default"
                    for i, w in enumerate(words):
                        if w.lower() in ["open", "launch", "start"] and i + 1 < len(words):
                            app_name = words[i+1].strip(".,;:?!'\"`()")
                            break
                    target = None
                    quotes = re.findall(r'["\'`]([^"\'`]+)["\'`]', prompt)
                    if quotes:
                        target = quotes[0]
                    else:
                        url_match = re.search(r'(https?://\S+)', prompt)
                        if url_match:
                            target = url_match.group(1)
                    plan.args = {"app_name": app_name, "target": target}
                elif legacy_intent == IntentType.WEB_SEARCH:
                    plan.tool_name = "browser"
                    url = "https://google.com"
                    url_match = re.search(r'(https?://\S+)', prompt)
                    if url_match:
                        url = url_match.group(1)
                    else:
                        words = prompt.split()
                        for w in words:
                            if "." in w and not w.startswith(".") and not w.endswith("."):
                                cleaned = w.strip(".,;:?!'\"`()")
                                if cleaned:
                                    url = f"https://{cleaned}"
                                    break
                    plan.args = {"url": url}
                elif legacy_intent == IntentType.SEARCH_MEMORY or intent == "Memory Lookup":
                    plan.tool_name = "knowledge.search"
                    plan.args = {"query": prompt}
                elif "clipboard" in prompt.lower():
                    plan.tool_name = "clipboard"
                    op = "copy" if "copy" in prompt.lower() else "paste"
                    text = None
                    quotes = re.findall(r'["\'`]([^"\'`]+)["\'`]', prompt)
                    if quotes:
                        text = quotes[0]
                    plan.args = {"op": op, "text": text}
                else:
                    plan.tool_name = "browser"
                    plan.args = {"url": "https://google.com"}
                plan.reasoning = f"Planned action: {goal}"
            
            self._safe_publish(PlanCreated(plan_data=plan.model_dump()))
            
            # 8. Validation
            is_valid = self.plan_validator.validate(plan)
            
            if clarification_question:
                self.clarification_count += 1
                self._safe_publish(ClarificationRequested(question=clarification_question, intent=intent))
            elif not is_valid:
                self.validation_failures += 1
                self._safe_publish(PlanRejected(reason="Validation failed: confidence too low", plan_data=plan.model_dump()))
            else:
                self._safe_publish(PlanValidated(plan_data=plan.model_dump()))
                
            latency = (time.time() - start_time) * 1000.0
            self.planning_latency_sum += latency
            
            return plan

        except Exception as e:
            self.errors_count += 1
            logger.error(f"PlannerManager error: {str(e)}")
            self._safe_publish(PlannerError(message=str(e)))
            raise e
            
    # Callback callbacks for EventBus subscriptions
    def on_conversation_received(self, event: OrionEvent) -> None:
        logger.info(f"PlannerManager intercepted ConversationReceived prompt: {event.data.get('prompt')}")

    def on_memory_retrieved(self, event: OrionEvent) -> None:
        logger.info("PlannerManager intercepted MemoryRetrieved event.")

    def on_tool_completed(self, event: OrionEvent) -> None:
        logger.info("PlannerManager intercepted ToolCompleted event.")

    def on_mission_completed(self, event: OrionEvent) -> None:
        logger.info("PlannerManager intercepted MissionCompleted event.")

    def on_workflow_completed(self, event: OrionEvent) -> None:
        logger.info("PlannerManager intercepted WorkflowCompleted event.")
