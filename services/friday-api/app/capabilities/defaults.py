from app.capabilities.base import (
    CapabilityDefinition, CapabilityDependency, CapabilityPermission,
    CapabilityCategory, CapabilityStatus,
)


def web_search() -> CapabilityDefinition:
    return CapabilityDefinition(
        id="web_search",
        name="Web Search",
        description="Search the web for information, pages, and resources",
        category=CapabilityCategory.WEB_SEARCH,
        version="1.0.0",
        aliases=["search", "internet_search", "web"],
        tool_ids=["web_search", "browser_navigate"],
        tags=["search", "web", "internet"],
        permission_level="user",
    )


def file_analysis() -> CapabilityDefinition:
    return CapabilityDefinition(
        id="file_analysis",
        name="File Analysis",
        description="Read, analyze, and extract information from files",
        category=CapabilityCategory.FILE_ANALYSIS,
        version="1.0.0",
        aliases=["file_read", "file_analyze", "read_file"],
        tool_ids=["read_file", "list_directory", "search_files"],
        tags=["file", "analysis", "filesystem"],
        permission_level="user",
    )


def desktop_automation() -> CapabilityDefinition:
    return CapabilityDefinition(
        id="desktop_automation",
        name="Desktop Automation",
        description="Control desktop UI elements, mouse, and keyboard",
        category=CapabilityCategory.DESKTOP_AUTOMATION,
        version="1.0.0",
        aliases=["desktop", "gui", "ui_control"],
        tool_ids=["desktop_click", "desktop_type", "desktop_screenshot"],
        tags=["desktop", "automation", "ui"],
        permission_level="user",
    )


def knowledge_retrieval() -> CapabilityDefinition:
    return CapabilityDefinition(
        id="knowledge_retrieval",
        name="Knowledge Retrieval",
        description="Query and retrieve information from the knowledge base",
        category=CapabilityCategory.KNOWLEDGE_RETRIEVAL,
        version="1.0.0",
        aliases=["knowledge", "kb", "knowledge_base"],
        tool_ids=["query_knowledge", "retrieve_documents"],
        dependencies=[
            CapabilityDependency(capability_id="memory_access", optional=True),
        ],
        tags=["knowledge", "retrieval", "rag"],
        permission_level="user",
    )


def memory_access() -> CapabilityDefinition:
    return CapabilityDefinition(
        id="memory_access",
        name="Memory Access",
        description="Store and retrieve information from long-term memory",
        category=CapabilityCategory.MEMORY_ACCESS,
        version="1.0.0",
        aliases=["memory", "memories", "long_term_memory"],
        tool_ids=["memory_store", "memory_retrieve", "memory_search"],
        tags=["memory", "storage", "recall"],
        permission_level="user",
    )


def vision() -> CapabilityDefinition:
    return CapabilityDefinition(
        id="vision",
        name="Vision",
        description="Analyze images, screenshots, and visual content",
        category=CapabilityCategory.VISION,
        version="1.0.0",
        aliases=["image", "screenshot", "visual", "ocr"],
        tool_ids=["analyze_image", "ocr_image"],
        dependencies=[
            CapabilityDependency(capability_id="file_analysis", optional=True),
        ],
        tags=["vision", "image", "ocr"],
        permission_level="user",
    )


def voice() -> CapabilityDefinition:
    return CapabilityDefinition(
        id="voice",
        name="Voice",
        description="Process speech input and generate audio output",
        category=CapabilityCategory.VOICE,
        version="1.0.0",
        aliases=["speech", "audio", "speak", "listen"],
        tool_ids=["speech_to_text", "text_to_speech"],
        tags=["voice", "speech", "audio"],
        permission_level="user",
    )


def terminal() -> CapabilityDefinition:
    return CapabilityDefinition(
        id="terminal",
        name="Terminal",
        description="Execute shell commands and scripts in the terminal",
        category=CapabilityCategory.TERMINAL,
        version="1.0.0",
        aliases=["shell", "command", "terminal_execute", "bash"],
        tool_ids=["execute_command", "run_script"],
        tags=["terminal", "shell", "command"],
        permission_level="elevated",
    )


def workflow_control() -> CapabilityDefinition:
    return CapabilityDefinition(
        id="workflow_control",
        name="Workflow Control",
        description="Create, manage, and orchestrate multi-step workflows",
        category=CapabilityCategory.WORKFLOW_CONTROL,
        version="1.0.0",
        aliases=["workflow", "pipeline", "orchestrate"],
        tool_ids=[],
        recommended_tool_ids=["tool_a", "tool_b"],
        tags=["workflow", "orchestration"],
        permission_level="user",
    )


def browser() -> CapabilityDefinition:
    return CapabilityDefinition(
        id="browser",
        name="Browser",
        description="Navigate and interact with web pages through a browser",
        category=CapabilityCategory.BROWSER,
        version="1.0.0",
        aliases=["web_browser", "internet", "webpage"],
        tool_ids=["browser_navigate", "browser_click", "browser_extract"],
        dependencies=[
            CapabilityDependency(capability_id="web_search", optional=True),
        ],
        tags=["browser", "web", "navigation"],
        permission_level="user",
    )


def code_execution() -> CapabilityDefinition:
    return CapabilityDefinition(
        id="code_execution",
        name="Code Execution",
        description="Write, run, and debug code in various languages",
        category=CapabilityCategory.CODE_EXECUTION,
        version="1.0.0",
        aliases=["code", "programming", "run_code", "execute"],
        tool_ids=["python_execute", "run_script"],
        dependencies=[
            CapabilityDependency(capability_id="terminal", optional=True),
        ],
        tags=["code", "execution", "programming"],
        permission_level="elevated",
    )


def DEFAULT_CAPABILITIES() -> list:
    return [
        web_search(),
        file_analysis(),
        desktop_automation(),
        knowledge_retrieval(),
        memory_access(),
        vision(),
        voice(),
        terminal(),
        workflow_control(),
        browser(),
        code_execution(),
    ]
