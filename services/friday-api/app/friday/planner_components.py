import re
import time
from typing import Dict, Any, List, Set, Optional
from loguru import logger
from app.friday.intent import IntentType

class IntentAnalyzer:
    """
    Analyzes user queries to determine the structural intent category.
    """
    def __init__(self) -> None:
        self.patterns = {
            "Conversation": r"\b(hello|hi|hey|greetings|howdy|how are you|who are you|whats up)\b",
            "Terminal Action": r"\b(run|execute|cmd|terminal|sh|bash|command)\b",
            "Filesystem Action": r"\b(read|write|create|delete|remove|rm|erase|list|show files|file|folder|dir|ls)\b",
            "Memory Lookup": r"\b(what do you remember|search memory|do you know my|lookup preference|list memories)\b",
            "Memory Update": r"\b(remember|save preference|preference|my preferred|favorite|style is|store that)\b",
            "Project Management": r"\b(project|milestone|todo|decisions|roadmap|gantt|kanban)\b",
            "Workflow Creation": r"\b(create workflow|new workflow|run workflow|define workflow|workflow)\b",
            "Mission Creation": r"\b(create mission|new mission|run mission|mission)\b",
            "Tool Invocation": r"\b(tool|invoke|run tool|execute tool|call tool)\b",
            "System Control": r"\b(shutdown|reboot|restart|poweroff|exit|kernel status)\b"
        }

    def analyze(self, query: str, legacy_intent: Optional[IntentType] = None) -> str:
        query_lower = query.lower().strip()
        
        # Check explicit overrides from legacy intent enum
        if legacy_intent == IntentType.FILE_OPERATION:
            return "Filesystem Action"
        if legacy_intent == IntentType.SYSTEM_COMMAND:
            return "Terminal Action"
        if legacy_intent == IntentType.WEB_SEARCH:
            return "Tool Invocation"
        if legacy_intent == IntentType.SEARCH_MEMORY:
            return "Memory Lookup"
            
        # Regex scans
        for category, regex in self.patterns.items():
            if re.search(regex, query_lower):
                return category
                
        return "Unknown"

class GoalExtractor:
    """
    Extracts the core target objective/goal from user query prompts.
    """
    def extract(self, query: str, intent: str) -> str:
        query_strip = query.strip()
        if intent == "Conversation":
            return "Engage in social conversation"
        if intent == "Filesystem Action":
            return f"Execute file system operations for: '{query_strip}'"
        if intent == "Terminal Action":
            return f"Run terminal command: '{query_strip}'"
        return f"Process action query: '{query_strip}'"

class CapabilityResolver:
    """
    Resolves required capabilities from FridayKernel capability registry.
    """
    def resolve_required_capabilities(self, intent: str) -> List[str]:
        # Mapping intent categories to registered capabilities
        mapping = {
            "Filesystem Action": ["Desktop"],
            "Terminal Action": ["Desktop"],
            "Memory Update": ["Memory"],
            "Memory Lookup": ["Memory"],
            "Project Management": ["Memory", "Missions"],
            "Workflow Creation": ["Workflows"],
            "Mission Creation": ["Missions"],
            "Tool Invocation": ["Tools"]
        }
        required = mapping.get(intent, [])
        
        # Verify resolution status in active kernel registry if loaded
        resolved = []
        try:
            from app.kernel.kernel import FridayKernel
            kernel = FridayKernel.get_instance()
            registry = getattr(kernel, "_capability_registry", None)
            if registry and len(registry.discover_capabilities()) > 0:
                for cap in required:
                    if any(c.get("name") == cap for c in registry.discover_capabilities()):
                        resolved.append(cap)
            else:
                resolved = required
        except Exception:
            resolved = required
            
        return resolved

class TaskClassifier:
    """
    Generates step-by-step execution listings from intent and queries.
    """
    def classify_steps(self, query: str, intent: str) -> List[Dict[str, Any]]:
        steps = []
        query_lower = query.lower()
        
        if intent == "Filesystem Action":
            op = "read"
            if any(w in query_lower for w in ["delete", "remove", "rm", "erase"]):
                op = "delete"
            elif any(w in query_lower for w in ["write", "create", "save", "overwrite"]):
                op = "write"
            elif any(w in query_lower for w in ["list", "ls", "dir", "show files"]):
                op = "list"
            
            path = None
            quotes = re.findall(r'["\'`]([^"\'`]+)["\'`]', query)
            if quotes:
                path = quotes[0]
            else:
                words = query.split()
                for w in words:
                    if "." in w or "/" in w:
                        cleaned = w.strip(".,;:?!'\"`()")
                        if cleaned:
                            path = cleaned
                            break
            if not path:
                path = "file.txt"
                
            content = None
            if op == "write":
                if len(quotes) > 1:
                    content = quotes[1]
                else:
                    match = re.search(r'(?:content|text|with)\s+["\'`]?(.+?)["\'`]?$', query, re.IGNORECASE)
                    if match:
                        content = match.group(1)
                    else:
                        content = "nominal"
                        
            steps.append({
                "step": 1,
                "action": "filesystem_op",
                "args": {"op": op, "path": path, "content": content}
            })
        elif intent == "Terminal Action":
            cmd = query
            for prefix in ["run command", "run", "execute", "terminal", "exec", "sh", "bash"]:
                if query_lower.startswith(prefix):
                    candidate = query[len(prefix):].strip()
                    if candidate:
                        cmd = candidate
                        break
            cmd = cmd.strip("\"'` ")
            steps.append({
                "step": 1,
                "action": "terminal_exec",
                "args": {"cmd": cmd}
            })
        else:
            steps.append({
                "step": 1,
                "action": "process_prompt",
                "args": {"prompt": query}
            })
            
        return steps

class PlanValidator:
    """
    Validates structural correctness and flags planning rejections.
    """
    def validate(self, plan: Any) -> bool:
        if not plan.intent or plan.intent == "Unknown":
            plan.confidence = 0.3
            return False
        if plan.confidence < 0.4:
            return False
        return True

class ClarificationManager:
    """
    Determines if request parameters are missing or ambiguous.
    """
    def check_clarification(self, query: str, intent: str) -> Optional[str]:
        query_lower = query.lower()
        if intent == "Filesystem Action":
            # Check if file path is missing
            has_path = re.search(r'["\'`]([^"\'`]+)["\'`]', query) or "." in query or "/" in query
            if not has_path and not any(w in query_lower for w in ["list", "ls", "dir"]):
                return "Which file path should I execute this operation on?"
        if intent == "Terminal Action":
            # Check if command is completely empty
            if len(query.strip()) < 3:
                return "Please specify the exact command line arguments to run."
        return None
