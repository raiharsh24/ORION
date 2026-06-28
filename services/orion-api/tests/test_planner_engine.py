import pytest
import anyio
from typing import Dict, Any

from app.orion.planner_schema import ExecutionPlan
from app.orion.planner_components import (
    IntentAnalyzer, GoalExtractor, CapabilityResolver,
    TaskClassifier, PlanValidator, ClarificationManager
)
from app.orion.planner_events import (
    PlanCreated, PlanValidated, ClarificationRequested, IntentDetected
)
from app.orion.planner_manager import PlannerManager
from app.orion.planner_engine import PlannerEngine
from app.orion.intent import IntentType
from app.events.bus import EventBus
from app.events.events import OrionEvent
from app.kernel import OrionKernel, OrionKernelConfig

# ----------------------------------------------------
# 1. Unit Tests for Pipeline Components
# ----------------------------------------------------
def test_intent_analyzer():
    analyzer = IntentAnalyzer()
    assert analyzer.analyze("hello there orion") == "Conversation"
    assert analyzer.analyze("read file 'foo.txt'") == "Filesystem Action"
    assert analyzer.analyze("run terminal command 'ls'") == "Terminal Action"
    assert analyzer.analyze("what do you remember about me") == "Memory Lookup"
    assert analyzer.analyze("save preference coding_style=spaces") == "Memory Update"
    assert analyzer.analyze("random gibberish query") == "Unknown"

def test_goal_extractor():
    extractor = GoalExtractor()
    assert extractor.extract("read file 'foo.txt'", "Filesystem Action") == "Execute file system operations for: 'read file 'foo.txt''"
    assert extractor.extract("hello", "Conversation") == "Engage in social conversation"

def test_capability_resolver():
    resolver = CapabilityResolver()
    # If unbooted, falls back to direct mappings
    assert "Desktop" in resolver.resolve_required_capabilities("Filesystem Action")
    assert "Memory" in resolver.resolve_required_capabilities("Memory Lookup")

def test_task_classifier():
    classifier = TaskClassifier()
    steps = classifier.classify_steps("write file 'test.txt' with 'content'", "Filesystem Action")
    assert len(steps) == 1
    assert steps[0]["action"] == "filesystem_op"
    assert steps[0]["args"]["op"] == "write"

def test_plan_validator():
    validator = PlanValidator()
    # Valid plan
    plan1 = ExecutionPlan(
        intent="Filesystem Action", goal="read file", memoryRequired=False,
        toolRequired=True, clarificationRequired=False, confidence=0.9
    )
    assert validator.validate(plan1) is True

    # Invalid Unknown intent plan
    plan2 = ExecutionPlan(
        intent="Unknown", goal="blah", memoryRequired=False,
        toolRequired=False, clarificationRequired=False, confidence=0.3
    )
    assert validator.validate(plan2) is False

def test_clarification_manager():
    manager = ClarificationManager()
    
    # Missing file path in filesystem operation
    q1 = "write file with content hello"
    assert manager.check_clarification(q1, "Filesystem Action") is not None
    
    # Complete path filesystem operation -> no clarification
    q2 = "write file 'foo.txt' with content hello"
    assert manager.check_clarification(q2, "Filesystem Action") is None

# ----------------------------------------------------
# 2. Integration & EventBus Publish Tests
# ----------------------------------------------------
@pytest.mark.anyio
async def test_planner_manager_events_dispatch():
    event_bus = EventBus()
    manager = PlannerManager(event_bus=event_bus)
    
    events_logged = []
    event_bus.subscribe("IntentDetected", lambda e: events_logged.append(e))
    event_bus.subscribe("PlanCreated", lambda e: events_logged.append(e))
    event_bus.subscribe("PlanValidated", lambda e: events_logged.append(e))
    
    plan = await manager.create_plan("read file 'foo.txt'")
    await anyio.sleep(0.1)
    
    # Assert events published
    topics = [e.topic for e in events_logged]
    assert "IntentDetected" in topics
    assert "PlanCreated" in topics
    assert "PlanValidated" in topics
    
    assert plan.intent == "Filesystem Action"
    assert plan.toolRequired is True
    # Backwards compatible tool mappings
    assert plan.tool_name == "filesystem"
    assert plan.args["op"] == "read"

# ----------------------------------------------------
# 3. Subsystem Lifecycle & Health Tests
# ----------------------------------------------------
@pytest.mark.anyio
async def test_planner_engine_lifecycle_and_health():
    OrionKernel.reset_instance()
    kernel = OrionKernel.get_instance(OrionKernelConfig())
    await kernel.boot()
    
    planner_service = kernel.get_service("planner")
    assert planner_service is not None
    assert isinstance(planner_service, PlannerEngine)
    
    # Check health status aggregation
    h = planner_service.health()
    assert h["status"] == "HEALTHY"
    assert "planning_count" in h["details"]
    
    # Legacy plan compatibility call
    plan = await planner_service.plan("run command 'python3 main.py'", IntentType.SYSTEM_COMMAND)
    assert plan is not None
    assert plan.intent == "Terminal Action"
    assert plan.tool_name == "terminal"
    assert plan.args["cmd"] == "python3 main.py"
    
    h2 = planner_service.health()
    assert h2["details"]["planning_count"] == 1
    
    await kernel.shutdown()
