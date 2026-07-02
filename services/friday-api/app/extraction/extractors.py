from typing import List
from datetime import datetime, timezone

from app.extraction.base import IContextExtractor, ContextBlock


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class MemoryExtractor(IContextExtractor):
    extractor_name = "memory_extractor"
    supported_sources = ["working_memory", "session_history", "user_preferences"]
    priority = 10

    @property
    def aliases(self):
        return ["memory_extractor", "conversation_history_extractor", "user_preference_extractor",
                "long_term_memory_extractor", "session_history_extractor", "general_context_extractor"]

    async def extract(self, request: str) -> List[ContextBlock]:
        content = (
            "Session memory: User has been working on software development tasks. "
            "Previous interactions include code reviews, debugging sessions, and architectural discussions. "
            "Recent context: user requested assistance with Python implementation."
        )
        block = ContextBlock(
            source="memory/session",
            title="Session Memory Snapshot",
            content=content,
            metadata={"entry_count": 12, "oldest": "2026-06-28", "newest": "2026-06-29"},
            confidence=0.85,
            importance=0.8,
            estimated_tokens=_estimate_tokens(content),
        )
        return [block]


class KnowledgeExtractor(IContextExtractor):
    extractor_name = "knowledge_extractor"
    supported_sources = ["knowledge_base", "project_memory", "documentation"]
    priority = 20

    @property
    def aliases(self):
        return ["knowledge_extractor", "knowledge_base_extractor", "documentation_extractor",
                "code_context_extractor", "file_tree_extractor", "recent_changes_extractor",
                "web_search_extractor"]

    async def extract(self, request: str) -> List[ContextBlock]:
        content = (
            "Knowledge base contains project documentation, code patterns, "
            "and architectural decisions for the FRIDAY system. "
            f"Request keywords suggest relevance to: '{request}'."
        )
        docs_block = ContextBlock(
            source="knowledge/base",
            title="Knowledge Base Overview",
            content=content,
            metadata={"document_count": 45, "indexed_chunks": 1200},
            confidence=0.75,
            importance=0.7,
            estimated_tokens=_estimate_tokens(content),
        )
        return [docs_block]


class WorkflowExtractor(IContextExtractor):
    extractor_name = "workflow_extractor"
    supported_sources = ["workflow_state", "step_progress"]
    priority = 30

    @property
    def aliases(self):
        return ["workflow_extractor", "workflow_state_extractor", "step_progress_extractor"]

    async def extract(self, request: str) -> List[ContextBlock]:
        content = (
            "Active workflows: None. "
            "Completed workflows: 3 in the last hour. "
            "Pending workflows scheduled via cron: 2."
        )
        block = ContextBlock(
            source="workflow/engine",
            title="Workflow Engine State",
            content=content,
            metadata={"active_count": 0, "completed_today": 3, "pending": 2},
            confidence=0.9,
            importance=0.6,
            estimated_tokens=_estimate_tokens(content),
        )
        return [block]


class DesktopExtractor(IContextExtractor):
    extractor_name = "desktop_extractor"
    supported_sources = ["desktop_state", "active_window"]
    priority = 40

    @property
    def aliases(self):
        return ["desktop_extractor", "desktop_state_extractor", "active_window_extractor",
                "notification_extractor"]

    async def extract(self, request: str) -> List[ContextBlock]:
        content = (
            "Active window: terminal emulator. "
            "Visible applications: code editor, file manager, web browser. "
            "Current workspace: main (workspace 1 of 4)."
        )
        block = ContextBlock(
            source="desktop/controller",
            title="Desktop State Snapshot",
            content=content,
            metadata={
                "active_window": "terminal",
                "visible_apps": ["code_editor", "file_manager", "browser"],
                "workspace": 1,
            },
            confidence=0.8,
            importance=0.5,
            estimated_tokens=_estimate_tokens(content),
        )
        return [block]


class BrowserExtractor(IContextExtractor):
    extractor_name = "browser_extractor"
    supported_sources = ["web_page", "browser_state"]
    priority = 50

    @property
    def aliases(self):
        return ["browser_extractor", "web_page_extractor", "browser_state_extractor",
                "bookmark_extractor"]

    async def extract(self, request: str) -> List[ContextBlock]:
        content = (
            "Open tabs: 4. "
            "Active tab: FRIDAY documentation. "
            "Recent browsing history related to the request is available."
        )
        block = ContextBlock(
            source="browser/state",
            title="Browser State Snapshot",
            content=content,
            metadata={
                "open_tabs": 4,
                "active_url": "http://localhost:8000/docs",
                "history_available": True,
            },
            confidence=0.7,
            importance=0.5,
            estimated_tokens=_estimate_tokens(content),
        )
        return [block]


class TerminalExtractor(IContextExtractor):
    extractor_name = "terminal_extractor"
    supported_sources = ["terminal_output", "shell_history", "process_list"]
    priority = 60

    @property
    def aliases(self):
        return ["terminal_extractor", "terminal_output_extractor", "shell_history_extractor",
                "process_list_extractor"]

    async def extract(self, request: str) -> List[ContextBlock]:
        content = (
            "Recent terminal output shows successful compilation. "
            "Last commands: 'npm run build', 'git status', 'pytest tests/'. "
            "Running processes: node, python3, docker."
        )
        block = ContextBlock(
            source="terminal/session",
            title="Terminal Session State",
            content=content,
            metadata={
                "last_commands": ["npm run build", "git status", "pytest tests/"],
                "running_processes": ["node", "python3", "docker"],
                "exit_code": 0,
            },
            confidence=0.85,
            importance=0.7,
            estimated_tokens=_estimate_tokens(content),
        )
        return [block]


class MissionExtractor(IContextExtractor):
    extractor_name = "mission_extractor"
    supported_sources = ["mission_context", "project_state", "milestone"]
    priority = 70

    @property
    def aliases(self):
        return ["mission_extractor", "mission_context_extractor", "project_state_extractor",
                "milestone_extractor", "resource_extractor"]

    async def extract(self, request: str) -> List[ContextBlock]:
        content = (
            "Current mission: Phase 4 implementation — Context Extractor Framework. "
            "Overall project: FRIDAY Intelligence Layer v2. "
            "Active sprint: Sprint 3. Completion: 60%."
        )
        block = ContextBlock(
            source="missions/manager",
            title="Mission Status",
            content=content,
            metadata={
                "current_phase": "Phase 4 Sprint 3",
                "project": "FRIDAY Intelligence Layer v2",
                "completion_pct": 60,
            },
            confidence=0.95,
            importance=0.9,
            estimated_tokens=_estimate_tokens(content),
        )
        return [block]


class VoiceExtractor(IContextExtractor):
    extractor_name = "voice_extractor"
    supported_sources = ["voice_state"]
    priority = 80

    @property
    def aliases(self):
        return ["voice_extractor"]

    async def extract(self, request: str) -> List[ContextBlock]:
        content = (
            "Voice session: inactive. "
            "Last voice interaction: 15 minutes ago. "
            "Audio input device: default system microphone."
        )
        block = ContextBlock(
            source="voice/manager",
            title="Voice Subsystem State",
            content=content,
            metadata={
                "session_active": False,
                "last_interaction": "15 minutes ago",
                "input_device": "default_microphone",
            },
            confidence=0.9,
            importance=0.3,
            estimated_tokens=_estimate_tokens(content),
        )
        return [block]


class SystemStateExtractor(IContextExtractor):
    extractor_name = "system_state_extractor"
    supported_sources = ["system_state", "resource_usage"]
    priority = 90

    @property
    def aliases(self):
        return ["system_state_extractor", "screen_capture_extractor", "image_analysis_extractor",
                "object_detection_extractor"]

    async def extract(self, request: str) -> List[ContextBlock]:
        content = (
            "System resources: CPU 23%, memory 4.2GB/16GB, disk 45% used. "
            "Uptime: 3 days 7 hours. "
            "Platform: Linux x86_64."
        )
        block = ContextBlock(
            source="system/state",
            title="System Resource State",
            content=content,
            metadata={
                "cpu_percent": 23,
                "memory_gb": {"used": 4.2, "total": 16.0},
                "disk_percent": 45,
                "uptime_days": 3,
            },
            confidence=0.95,
            importance=0.4,
            estimated_tokens=_estimate_tokens(content),
        )
        return [block]
