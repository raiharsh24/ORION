from typing import Dict, Any, List, Optional

from app.agent_framework.base import AgentCapability, AgentModel
from app.agent_framework.state import AgentState


class PlannerAgent:
    ROLE = "planner"
    CAPABILITIES = [
        AgentCapability(name="task_decomposition", description="Break goals into steps"),
        AgentCapability(name="dependency_analysis", description="Analyze task dependencies"),
        AgentCapability(name="resource_allocation", description="Allocate agents to tasks"),
        AgentCapability(name="priority_assignment", description="Assign priorities to tasks"),
    ]
    TOOLS = ["planner", "knowledge.search", "memory"]

    @staticmethod
    def create(agent_id: str = "planner-agent") -> AgentModel:
        return AgentModel(
            agent_id=agent_id,
            name="Planner Agent",
            role=PlannerAgent.ROLE,
            capabilities=PlannerAgent.CAPABILITIES,
            tools=PlannerAgent.TOOLS,
            permissions=["plan:create", "plan:modify", "knowledge:read", "memory:read"],
            priority=10,
            memory_scope="session",
        )


class ResearchAgent:
    ROLE = "research"
    CAPABILITIES = [
        AgentCapability(name="web_search", description="Search the web for information"),
        AgentCapability(name="knowledge_retrieval", description="Retrieve from knowledge base"),
        AgentCapability(name="information_synthesis", description="Synthesize research findings"),
        AgentCapability(name="source_verification", description="Verify source credibility"),
    ]
    TOOLS = ["knowledge.search", "browser", "memory"]

    @staticmethod
    def create(agent_id: str = "research-agent") -> AgentModel:
        return AgentModel(
            agent_id=agent_id,
            name="Research Agent",
            role=ResearchAgent.ROLE,
            capabilities=ResearchAgent.CAPABILITIES,
            tools=ResearchAgent.TOOLS,
            permissions=["knowledge:read", "knowledge:write", "browser:access", "memory:read"],
            priority=7,
            memory_scope="project",
        )


class MemoryAgent:
    ROLE = "memory"
    CAPABILITIES = [
        AgentCapability(name="memory_storage", description="Store information in memory"),
        AgentCapability(name="memory_retrieval", description="Retrieve information from memory"),
        AgentCapability(name="context_maintenance", description="Maintain conversation context"),
        AgentCapability(name="summarization", description="Summarize stored information"),
    ]
    TOOLS = ["memory", "knowledge.search"]

    @staticmethod
    def create(agent_id: str = "memory-agent") -> AgentModel:
        return AgentModel(
            agent_id=agent_id,
            name="Memory Agent",
            role=MemoryAgent.ROLE,
            capabilities=MemoryAgent.CAPABILITIES,
            tools=MemoryAgent.TOOLS,
            permissions=["memory:read", "memory:write", "memory:delete"],
            priority=8,
            memory_scope="persistent",
        )


class CodeAgent:
    ROLE = "code"
    CAPABILITIES = [
        AgentCapability(name="code_generation", description="Generate source code"),
        AgentCapability(name="code_review", description="Review and analyze code"),
        AgentCapability(name="code_execution", description="Execute code in sandbox"),
        AgentCapability(name="dependency_management", description="Manage code dependencies"),
    ]
    TOOLS = ["terminal", "filesystem", "knowledge.search"]

    @staticmethod
    def create(agent_id: str = "code-agent") -> AgentModel:
        return AgentModel(
            agent_id=agent_id,
            name="Code Agent",
            role=CodeAgent.ROLE,
            capabilities=CodeAgent.CAPABILITIES,
            tools=CodeAgent.TOOLS,
            permissions=["filesystem:read", "filesystem:write", "terminal:execute"],
            priority=6,
            memory_scope="session",
        )


class BrowserAgent:
    ROLE = "browser"
    CAPABILITIES = [
        AgentCapability(name="web_navigation", description="Navigate web pages"),
        AgentCapability(name="content_extraction", description="Extract web content"),
        AgentCapability(name="form_interaction", description="Fill and submit forms"),
        AgentCapability(name="screenshot_capture", description="Capture page screenshots"),
    ]
    TOOLS = ["browser", "desktop.screenshot", "clipboard"]

    @staticmethod
    def create(agent_id: str = "browser-agent") -> AgentModel:
        return AgentModel(
            agent_id=agent_id,
            name="Browser Agent",
            role=BrowserAgent.ROLE,
            capabilities=BrowserAgent.CAPABILITIES,
            tools=BrowserAgent.TOOLS,
            permissions=["browser:access", "browser:navigate", "desktop:access"],
            priority=5,
            memory_scope="session",
        )


class ToolAgent:
    ROLE = "tool"
    CAPABILITIES = [
        AgentCapability(name="tool_execution", description="Execute available tools"),
        AgentCapability(name="tool_discovery", description="Discover and inspect tools"),
        AgentCapability(name="workflow_execution", description="Execute workflow steps"),
        AgentCapability(name="result_processing", description="Process and format tool results"),
    ]
    TOOLS = ["filesystem", "terminal", "clipboard", "desktop"]

    @staticmethod
    def create(agent_id: str = "tool-agent") -> AgentModel:
        return AgentModel(
            agent_id=agent_id,
            name="Tool Agent",
            role=ToolAgent.ROLE,
            capabilities=ToolAgent.CAPABILITIES,
            tools=ToolAgent.TOOLS,
            permissions=["tool:execute", "tool:discover", "filesystem:read", "filesystem:write"],
            priority=9,
            memory_scope="session",
        )


class MissionAgent:
    ROLE = "mission"
    CAPABILITIES = [
        AgentCapability(name="mission_planning", description="Plan mission execution"),
        AgentCapability(name="mission_monitoring", description="Monitor mission progress"),
        AgentCapability(name="mission_recovery", description="Recover from mission failures"),
        AgentCapability(name="agent_orchestration", description="Coordinate multiple agents"),
    ]
    TOOLS = ["mission", "workflow", "scheduler"]

    @staticmethod
    def create(agent_id: str = "mission-agent") -> AgentModel:
        return AgentModel(
            agent_id=agent_id,
            name="Mission Agent",
            role=MissionAgent.ROLE,
            capabilities=MissionAgent.CAPABILITIES,
            tools=MissionAgent.TOOLS,
            permissions=["mission:create", "mission:monitor", "mission:cancel", "agent:assign"],
            priority=10,
            memory_scope="project",
        )


BUILTIN_AGENTS = {
    "planner-agent": PlannerAgent,
    "research-agent": ResearchAgent,
    "memory-agent": MemoryAgent,
    "code-agent": CodeAgent,
    "browser-agent": BrowserAgent,
    "tool-agent": ToolAgent,
    "mission-agent": MissionAgent,
}


def create_all_builtin_agents() -> List[AgentModel]:
    return [factory.create() for factory in BUILTIN_AGENTS.values()]
