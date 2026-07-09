"""
Validation script for FRIDAY AI Operating System subsystems.
Tests import and construction of all 18 subsystems.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unittest.mock import MagicMock

results = []

def check(label: str, status: str, detail: str = ""):
    results.append((label, status, detail))
    sym = "PASS" if status == "PASS" else "FAIL"
    print(f"  [{sym}] {label}" + (f" -- {detail}" if detail else ""))

def try_import(label: str, import_stmt: str, cls_name: str, init_kwargs: dict = None):
    try:
        exec(import_stmt, globals())
        cls = eval(cls_name)
        kwargs = init_kwargs or {}
        instance = cls(**kwargs)
        check(label, "PASS", f"instance={type(instance).__name__}")
    except Exception as e:
        check(label, "FAIL", str(e))

print("=" * 72)
print("FRIDAY AI Operating System - Subsystem Validation")
print("=" * 72)

# 1. Desktop UI — check desktop module import
print("\n--- 1. Desktop UI ---")
try:
    from app.desktop import DesktopController
    check("DesktopController import", "PASS")
except Exception as e:
    check("DesktopController import", "FAIL", str(e))

# 2. Gateway — check services or main app import
print("\n--- 2. Gateway / FastAPI app ---")
try:
    from app.main import app
    check("FastAPI app import (Gateway)", "PASS", f"title={app.title}")
except Exception as e:
    check("FastAPI app import (Gateway)", "FAIL", str(e))

# 3. FastAPI — router from app.api.routes
print("\n--- 3. FastAPI Router ---")
try:
    from app.api.routes import router
    check("Router import", "PASS", f"routes={len(router.routes)}")
except Exception as e:
    check("Router import", "FAIL", str(e))

# 4. FridayOrchestrator
print("\n--- 4. FridayOrchestrator ---")
try:
    from app.friday.orchestrator import FridayOrchestrator
    from app.memory import ConversationMemory
    from app.friday.tool_registry import ToolRegistry
    from app.friday.prompt_manager import PromptManager
    from app.friday.intent import IntentClassifier
    from app.llm.router import LLMRouter
    from app.memory import EmbeddingsManager

    orch = FridayOrchestrator(
        llm_router=MagicMock(spec=LLMRouter),
        intent_classifier=MagicMock(spec=IntentClassifier),
        memory=MagicMock(spec=ConversationMemory),
        prompt_manager=MagicMock(spec=PromptManager),
        tool_registry=MagicMock(spec=ToolRegistry),
        embeddings=MagicMock(spec=EmbeddingsManager),
    )
    check("FridayOrchestrator", "PASS")
except Exception as e:
    check("FridayOrchestrator", "FAIL", str(e))

# 5. UnifiedExecutionEngine
print("\n--- 5. UnifiedExecutionEngine ---")
try:
    from app.execution.engine import UnifiedExecutionEngine
    from app.execution.config import ExecutionConfig

    uee = UnifiedExecutionEngine(
        llm_router=MagicMock(),
        intent_classifier=MagicMock(),
        memory=MagicMock(),
        prompt_manager=MagicMock(),
        tool_registry=MagicMock(),
        embeddings=MagicMock(),
        config=ExecutionConfig(),
    )
    check("UnifiedExecutionEngine", "PASS")
except Exception as e:
    check("UnifiedExecutionEngine", "FAIL", str(e))

# 6. Planner (PlannerEngine)
print("\n--- 6. Planner ---")
try:
    from app.friday.planner import Planner
    planner = Planner()
    check("Planner (PlannerEngine)", "PASS")
except Exception as e:
    check("Planner (PlannerEngine)", "FAIL", str(e))

# 7. Memory — ConversationMemory (MemoryEngine)
print("\n--- 7. Memory (ConversationMemory) ---")
try:
    from app.memory import ConversationMemory
    cm = ConversationMemory()
    check("ConversationMemory", "PASS")
    # Check session methods
    session_methods = ["get_or_create_session", "add_message", "get_session", "list_sessions", "prune_sessions"]
    found = [m for m in session_methods if hasattr(cm, m)]
    if len(found) >= 3:
        check("ConversationMemory session methods", "PASS", f"methods={found}")
    else:
        check("ConversationMemory session methods", "FAIL", f"expected session methods, got dir={[x for x in dir(cm) if not x.startswith('_')][:15]}")
except Exception as e:
    check("ConversationMemory", "FAIL", str(e))
    check("ConversationMemory session methods", "FAIL", str(e))

# 8. CognitiveCore
print("\n--- 8. CognitiveCore ---")
try:
    from app.cognitive_core.core import CognitiveCore
    cc = CognitiveCore()
    check("CognitiveCore", "PASS")
except Exception as e:
    check("CognitiveCore", "FAIL", str(e))

# 9. ToolRegistry
print("\n--- 9. ToolRegistry ---")
try:
    from app.friday.tool_registry import ToolRegistry
    tr = ToolRegistry()
    check("ToolRegistry", "PASS")
except Exception as e:
    check("ToolRegistry", "FAIL", str(e))

# 10. ToolSelectionEngine
print("\n--- 10. ToolSelectionEngine ---")
try:
    from app.tool_selection.selector import ToolSelectionEngine
    from app.tools.registry import ToolRegistry as UniversalToolRegistry
    tse = ToolSelectionEngine(tool_registry=MagicMock(spec=UniversalToolRegistry))
    check("ToolSelectionEngine", "PASS")
except Exception as e:
    check("ToolSelectionEngine", "FAIL", str(e))

# 11. ToolExecutionEngine
print("\n--- 11. ToolExecutionEngine ---")
try:
    from app.tool_execution.executor import ToolExecutionEngine
    tee = ToolExecutionEngine(legacy_tool_registry=MagicMock())
    check("ToolExecutionEngine", "PASS")
except Exception as e:
    check("ToolExecutionEngine", "FAIL", str(e))

# 12. PluginRuntime
print("\n--- 12. PluginRuntime ---")
try:
    from app.plugin_runtime.runtime import PluginRuntime
    pr = PluginRuntime(sdk_registry=MagicMock())
    check("PluginRuntime", "PASS")
except Exception as e:
    check("PluginRuntime", "FAIL", str(e))

# 13. BrowserTool
print("\n--- 13. BrowserTool ---")
try:
    from app.tools.browser import BrowserTool
    bt = BrowserTool()
    check("BrowserTool", "PASS", f"name={bt.name}")
except Exception as e:
    check("BrowserTool", "FAIL", str(e))

# 14. MissionManager
print("\n--- 14. MissionManager ---")
try:
    from app.missions.mission_manager import MissionManager
    mm = MissionManager()
    check("MissionManager", "PASS")
except Exception as e:
    check("MissionManager", "FAIL", str(e))

# 15. StreamingResponse usage in routes
print("\n--- 15. StreamingResponse in routes ---")
try:
    from app.api.routes import router
    from fastapi.responses import StreamingResponse
    # Check if StreamingResponse is used in the routes module
    import inspect
    route_source = inspect.getsource(sys.modules.get("app.api.routes"))
    if "StreamingResponse" in route_source:
        check("StreamingResponse used in routes", "PASS")
    else:
        check("StreamingResponse used in routes", "FAIL", "StreamingResponse not found in routes.py source")
except Exception as e:
    check("StreamingResponse used in routes", "FAIL", str(e))

# 16. Session Memory (ConversationMemory session methods already checked above)
print("\n--- 16. Session Memory methods ---")
try:
    from app.memory import ConversationMemory
    session_cm = ConversationMemory()
    # Check for session-related methods
    has_session_methods = all(hasattr(session_cm, m) for m in [
        "get_or_create_session", "add_message", "get_session", "list_sessions"
    ])
    if has_session_methods:
        check("SessionMemory (ConversationMemory)", "PASS")
    else:
        missing = [m for m in ["get_or_create_session", "add_message", "get_session", "list_sessions"] if not hasattr(session_cm, m)]
        check("SessionMemory (ConversationMemory)", "FAIL", f"missing methods: {missing}")
except Exception as e:
    check("SessionMemory (ConversationMemory)", "FAIL", str(e))

# 17. ExecutionMetrics
print("\n--- 17. ExecutionMetrics ---")
try:
    from app.execution.metrics import ExecutionMetrics
    em = ExecutionMetrics()
    check("ExecutionMetrics", "PASS", f"snapshot={em.snapshot()}")
except Exception as e:
    check("ExecutionMetrics", "FAIL", str(e))

# 18. MiddlewareChain
print("\n--- 18. MiddlewareChain ---")
try:
    from app.execution.middleware import MiddlewareChain, ExecutionMiddleware
    mc = MiddlewareChain()
    check("MiddlewareChain", "PASS")
except Exception as e:
    check("MiddlewareChain", "FAIL", str(e))

print("\n" + "=" * 72)
print("SUMMARY")
print("=" * 72)
passed = sum(1 for _, s, _ in results if s == "PASS")
failed = sum(1 for _, s, _ in results if s == "FAIL")
print(f"Total: {len(results)} | Passed: {passed} | Failed: {failed}")
if failed > 0:
    print("\nFAILURES:")
    for label, status, detail in results:
        if status == "FAIL":
            print(f"  - {label}: {detail}")
sys.exit(0 if failed == 0 else 1)