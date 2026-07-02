import time
import pytest
from typing import List, Optional, Any

from app.intent.types import IntentType
from app.intent.analyzer import RuleBasedIntentAnalyzer, IntentResult
from app.intent.events import IntentAnalyzed
from app.events.bus import EventBus
from app.kernel import FridayKernel, FridayKernelConfig


# ----------------------------------------------------------------
# Unit Tests: RuleBasedIntentAnalyzer
# ----------------------------------------------------------------

class TestIntentTypeEnum:
    def test_enum_values(self):
        assert IntentType.CONVERSATION.value == "conversation"
        assert IntentType.CODING.value == "coding"
        assert IntentType.TERMINAL.value == "terminal"
        assert IntentType.DESKTOP.value == "desktop"
        assert IntentType.BROWSER.value == "browser"
        assert IntentType.WORKFLOW.value == "workflow"
        assert IntentType.PLANNING.value == "planning"
        assert IntentType.MEMORY.value == "memory"
        assert IntentType.SEARCH.value == "search"
        assert IntentType.VISION.value == "vision"
        assert IntentType.UNKNOWN.value == "unknown"

    def test_enum_membership(self):
        assert len(IntentType) == 11
        for member in IntentType:
            assert isinstance(member.value, str)


class TestRuleBasedIntentAnalyzerUnit:
    """Pure unit tests — no EventBus, no kernel."""

    def make_analyzer(self):
        return RuleBasedIntentAnalyzer()

    # --- Conversation ---
    @pytest.mark.parametrize("query", [
        "hello",
        "hi there",
        "hey how are you",
        "good morning",
        "thanks for your help",
        "thank you very much",
        "goodbye",
        "see you later",
        "who are you",
        "what can you do",
        "sorry about that",
        "yes please",
        "ok sounds good",
    ])
    def test_conversation_intent(self, query):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze(query)
        assert result.intent == IntentType.CONVERSATION, f"Expected CONVERSATION for '{query}', got {result.intent}"
        assert 0.0 < result.confidence <= 1.0
        assert result.reasoning

    # --- Coding ---
    @pytest.mark.parametrize("query", [
        "write a function to sort an array",
        "fix this bug in the login code",
        "how do I refactor this class",
        "create a new API endpoint",
        "merge my pull request on GitHub",
        "debug this stack trace",
        "write unit tests for the validator",
        "import pandas and load the csv",
        "deploy the docker container to kubernetes",
        "install pip package requests",
        "the build is failing with a syntax error",
        "implement a binary search in python",
    ])
    def test_coding_intent(self, query):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze(query)
        assert result.intent == IntentType.CODING, f"Expected CODING for '{query}', got {result.intent}"
        assert 0.0 < result.confidence <= 1.0

    # --- Terminal ---
    @pytest.mark.parametrize("query", [
        "run ls in the current directory",
        "grep for error in the log file",
        "ssh into the production server",
        "kill process 1234",
        "list all running processes with ps aux",
        "change permissions with chmod 755",
        "create a new directory with mkdir",
        "use curl to test the endpoint",
        "edit the config file with vim",
        "find all python files in the project",
        "run a bash script",
    ])
    def test_terminal_intent(self, query):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze(query)
        assert result.intent == IntentType.TERMINAL, f"Expected TERMINAL for '{query}', got {result.intent}"
        assert 0.0 < result.confidence <= 1.0

    # --- Desktop ---
    @pytest.mark.parametrize("query", [
        "open the browser",
        "open the settings app",
        "open a terminal window",
        "take a screenshot of the screen",
        "switch to the code editor window",
        "minimize the terminal window",
        "click on the save button",
        "show me the file manager",
        "adjust the volume",
        "connect to wifi",
        "restart the computer",
    ])
    def test_desktop_intent(self, query):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze(query)
        assert result.intent == IntentType.DESKTOP, f"Expected DESKTOP for '{query}', got {result.intent}"
        assert 0.0 < result.confidence <= 1.0

    # --- Browser ---
    @pytest.mark.parametrize("query", [
        "search for the latest news",
        "navigate to the documentation page",
        "open the website example.com in the browser",
        "navigate to github.com",
        "open the website example.com",
        "browse to the documentation page",
        "download a file from the internet",
        "search the web for restaurants nearby",
        "open a new tab in chrome",
    ])
    def test_browser_intent(self, query):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze(query)
        assert result.intent == IntentType.BROWSER, f"Expected BROWSER for '{query}', got {result.intent}"
        assert 0.0 < result.confidence <= 1.0

    # --- Workflow ---
    @pytest.mark.parametrize("query", [
        "create a workflow to deploy the app",
        "automate the build pipeline",
        "set up a cron job to run daily backups",
        "when a PR is merged, trigger a deployment",
        "schedule a task every hour",
        "build a CI pipeline with GitHub actions",
    ])
    def test_workflow_intent(self, query):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze(query)
        assert result.intent == IntentType.WORKFLOW, f"Expected WORKFLOW for '{query}', got {result.intent}"
        assert 0.0 < result.confidence <= 1.0

    # --- Planning ---
    @pytest.mark.parametrize("query", [
        "plan the roadmap for Q3",
        "set project goals and milestones",
        "prioritize the backlog for this sprint",
        "create a timeline for the release",
        "define the OKRs for this quarter",
        "brainstorm ideas for the new feature",
        "what are the objectives for this project",
    ])
    def test_planning_intent(self, query):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze(query)
        assert result.intent == IntentType.PLANNING, f"Expected PLANNING for '{query}', got {result.intent}"
        assert 0.0 < result.confidence <= 1.0

    # --- Memory ---
    @pytest.mark.parametrize("query", [
        "remember that my favorite color is blue",
        "what did I say earlier about the design",
        "save this note for later",
        "as I mentioned before, we need more tests",
        "don't forget to update the API key",
        "recall the previous conversation context",
        "you said yesterday we should refactor",
        "keep this in mind for next time",
    ])
    def test_memory_intent(self, query):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze(query)
        assert result.intent == IntentType.MEMORY, f"Expected MEMORY for '{query}', got {result.intent}"
        assert 0.0 < result.confidence <= 1.0

    # --- Search ---
    @pytest.mark.parametrize("query", [
        "search for the documentation on FastAPI",
        "find information about machine learning",
        "how to write a Python decorator",
        "what is the capital of France",
        "tell me about the history of computing",
        "show me examples of REST APIs",
        "recommend a good book on algorithms",
        "look up the definition of recursion",
    ])
    def test_search_intent(self, query):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze(query)
        assert result.intent == IntentType.SEARCH, f"Expected SEARCH for '{query}', got {result.intent}"
        assert 0.0 < result.confidence <= 1.0

    # --- Vision ---
    @pytest.mark.parametrize("query", [
        "what do you see in this image",
        "describe the picture attached",
        "analyze this screenshot for errors",
        "can you see what is on my screen",
        "detect faces in this photo",
        "extract text from this image using OCR",
        "look at this photo and tell me what it is",
        "identify objects in the picture",
    ])
    def test_vision_intent(self, query):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze(query)
        assert result.intent == IntentType.VISION, f"Expected VISION for '{query}', got {result.intent}"
        assert 0.0 < result.confidence <= 1.0

    # --- Unknown ---
    @pytest.mark.parametrize("query", [
        "",
        "   ",
        "xyzzx",
        "abracadabra",
        "fnord 42",
    ])
    def test_unknown_intent(self, query):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze(query)
        assert result.intent == IntentType.UNKNOWN
        assert result.confidence >= 0.0

    # --- Edge cases ---
    def test_case_insensitivity(self):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze("HELLO HOW ARE YOU")
        assert result.intent == IntentType.CONVERSATION

    def test_empty_string_high_confidence_unknown(self):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze("")
        assert result.intent == IntentType.UNKNOWN
        assert result.confidence == 1.0

    def test_whitespace_only_unknown(self):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze("   \t\n  ")
        assert result.intent == IntentType.UNKNOWN

    def test_confidence_bounds(self):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze("hello how are you")
        assert 0.0 <= result.confidence <= 1.0

    def test_reasoning_not_empty(self):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze("write a python function to sort a list")
        assert result.reasoning
        assert "coding" in result.reasoning

    def test_performance_under_5ms(self):
        analyzer = self.make_analyzer()
        queries = [
            "hello world",
            "fix this bug in production",
            "run ls -la in the terminal",
            "open the file manager",
            "search google for python tutorial",
            "create a workflow for deployment",
            "plan the sprint backlog",
            "remember my password",
            "what do you see on my screen",
            "",
        ]
        for query in queries:
            start = time.perf_counter()
            for _ in range(100):
                analyzer._sync_analyze(query)
            elapsed_ms = (time.perf_counter() - start) * 10
            assert elapsed_ms < 5.0, f"Average time {elapsed_ms:.3f}ms for '{query}' exceeds 5ms"

    def test_multiple_intent_scores(self):
        """Request matching multiple intents should pick the highest-scored one."""
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze("search for how to write a Python function")
        assert result.intent in (IntentType.SEARCH, IntentType.CODING)
        assert result.confidence > 0.0

    def test_analyze_returns_result_object(self):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze("hello")
        assert isinstance(result, IntentResult)
        assert isinstance(result.intent, IntentType)
        assert isinstance(result.confidence, float)
        assert isinstance(result.reasoning, str)

    def test_lifecycle_start_shutdown(self):
        analyzer = self.make_analyzer()
        import anyio
        anyio.run(analyzer.start)
        assert analyzer._running is True
        anyio.run(analyzer.shutdown)
        assert analyzer._running is False

    def test_health_check(self):
        analyzer = self.make_analyzer()
        h = analyzer.health()
        assert h["status"] == "HEALTHY"
        assert h["details"]["intent_count"] == 10  # UNKNOWN is fallback, has no patterns
        assert h["details"]["pattern_count"] > 0

    def test_no_event_bus_does_not_crash(self):
        analyzer = self.make_analyzer()
        import anyio
        result = anyio.run(analyzer.analyze, "hello")
        assert result.intent == IntentType.CONVERSATION

    def test_sql_keyword_in_coding(self):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze("write a SQL query to join two tables")
        assert result.intent == IntentType.CODING

    def test_git_commands_are_coding(self):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze("commit my changes and push to origin")
        assert result.intent == IntentType.CODING

    def test_docker_compose_is_coding(self):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze("build a docker image and deploy it")
        assert result.intent == IntentType.CODING

    def test_short_greeting(self):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze("hi")
        assert result.intent == IntentType.CONVERSATION

    def test_thanks(self):
        analyzer = self.make_analyzer()
        result = analyzer._sync_analyze("thanks a lot")
        assert result.intent == IntentType.CONVERSATION


# ----------------------------------------------------------------
# Integration Tests: EventBus publication
# ----------------------------------------------------------------

class TestIntentAnalyzerEventBusIntegration:
    @pytest.mark.anyio
    async def test_publishes_intent_analyzed_event(self):
        bus = EventBus()
        analyzer = RuleBasedIntentAnalyzer(event_bus=bus)
        await analyzer.start()

        received_events = []
        bus.subscribe("IntentAnalyzed", lambda e: received_events.append(e))

        result = await analyzer.analyze("hello how are you")
        assert result.intent == IntentType.CONVERSATION

        assert len(received_events) == 1
        event = received_events[0]
        assert isinstance(event, IntentAnalyzed)
        assert event.topic == "IntentAnalyzed"
        assert event.data["request"] == "hello how are you"
        assert event.data["intent"] == "conversation"
        assert event.data["confidence"] > 0.0
        assert event.data["reasoning"]

        await analyzer.shutdown()

    @pytest.mark.anyio
    async def test_event_data_fields_are_correct(self):
        bus = EventBus()
        analyzer = RuleBasedIntentAnalyzer(event_bus=bus)
        await analyzer.start()

        received = []
        bus.subscribe("IntentAnalyzed", lambda e: received.append(e))

        await analyzer.analyze("fix this bug in the login code")
        assert len(received) == 1
        event = received[0]
        assert event.data["intent"] == "coding"
        assert isinstance(event.data["confidence"], float)
        assert isinstance(event.data["reasoning"], str)

        await analyzer.shutdown()

    @pytest.mark.anyio
    async def test_no_event_published_when_not_running(self):
        bus = EventBus()
        analyzer = RuleBasedIntentAnalyzer(event_bus=bus)
        # Not started — should still work but not publish

        received = []
        bus.subscribe("IntentAnalyzed", lambda e: received.append(e))

        await analyzer.analyze("hello")
        assert len(received) == 0

    @pytest.mark.anyio
    async def test_no_event_bus_no_crash(self):
        analyzer = RuleBasedIntentAnalyzer(event_bus=None)
        result = await analyzer.analyze("hello")
        assert result.intent == IntentType.CONVERSATION


# ----------------------------------------------------------------
# Regression Tests: Kernel registration and lifecycle
# ----------------------------------------------------------------

class TestIntentAnalyzerKernelIntegration:
    @pytest.mark.anyio
    async def test_kernel_boot_includes_intent_analyzer(self):
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            svc = kernel.get_service("intent_analyzer")
            assert svc is not None
            assert isinstance(svc, RuleBasedIntentAnalyzer)

            h = kernel.health()
            assert h.intent_analyzer.status.value == "HEALTHY"
            assert h.intent_analyzer.name == "intent_analyzer"
        finally:
            await kernel.shutdown()

    @pytest.mark.anyio
    async def test_intent_analyzer_lifecycle_via_kernel(self):
        """Verify start() and shutdown() are called by the LifecycleManager."""
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            analyzer = kernel.get_service("intent_analyzer")
            assert analyzer._running is True

            analyzer_from_registry = kernel.module_registry.get_module("intent_analyzer")
            assert analyzer_from_registry is analyzer
        finally:
            await kernel.shutdown()

        assert analyzer._running is False

    @pytest.mark.anyio
    async def test_analyze_through_kernel(self):
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()

        try:
            analyzer = kernel.get_service("intent_analyzer")
            event_bus = kernel.get_service("event_bus")

            received = []
            event_bus.subscribe("IntentAnalyzed", lambda e: received.append(e))

            result = await analyzer.analyze("write a unit test for the API")
            assert result.intent == IntentType.CODING
            assert result.confidence > 0.0
            assert len(received) == 1
            assert received[0].data["intent"] == "coding"
        finally:
            await kernel.shutdown()

    @pytest.mark.anyio
    async def test_kernel_boot_shutdown_restart_preserves_analyzer(self):
        FridayKernel.reset_instance()
        config = FridayKernelConfig()
        kernel = FridayKernel.get_instance(config)
        await kernel.boot()
        svc1 = kernel.get_service("intent_analyzer")
        await kernel.shutdown()

        await kernel.boot()
        svc2 = kernel.get_service("intent_analyzer")
        assert svc2 is not None
        assert isinstance(svc2, RuleBasedIntentAnalyzer)
        assert svc2 is not svc1  # New instance after full boot
        await kernel.shutdown()
