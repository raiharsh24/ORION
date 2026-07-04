from enum import Enum
from loguru import logger

class IntentType(str, Enum):
    CHAT = "CHAT"
    SEARCH_MEMORY = "SEARCH_MEMORY"
    OPEN_APP = "OPEN_APP"
    FILE_OPERATION = "FILE_OPERATION"
    SYSTEM_COMMAND = "SYSTEM_COMMAND"
    WEB_SEARCH = "WEB_SEARCH"
    PLUGIN = "PLUGIN"
    VISION_ACTION = "VISION_ACTION"
    AUTONOMOUS_GOAL = "AUTONOMOUS_GOAL"
    UNKNOWN = "UNKNOWN"

class IntentClassifier:
    """
    Classifies the user prompt intent into one of the designated IntentTypes.
    """
    async def classify(self, prompt: str) -> IntentType:
        logger.debug(f"Classifying user intent for prompt: '{prompt}'")
        prompt_lower = prompt.lower().strip()
        
        if not prompt_lower:
            return IntentType.UNKNOWN
            
        if any(w in prompt_lower for w in ["search", "find", "query memory", "lookup"]):
            return IntentType.SEARCH_MEMORY
        elif any(w in prompt_lower for w in ["open", "launch", "start app"]):
            return IntentType.OPEN_APP
        elif any(w in prompt_lower for w in ["file", "directory", "read file", "write file", "filesystem"]):
            return IntentType.FILE_OPERATION
        elif any(w in prompt_lower for w in ["run command", "terminal", "exec", "sh ", "bash"]):
            return IntentType.SYSTEM_COMMAND
        elif any(w in prompt_lower for w in ["web", "google", "search browser", "navigate"]):
            return IntentType.WEB_SEARCH
        elif any(w in prompt_lower for w in ["what is on my screen", "read this error", "summarize this dashboard", "what button", "describe this image", "what changed", "screenshot", "ocr", "screen context", "vision"]):
            return IntentType.VISION_ACTION
        elif any(w in prompt_lower for w in ["plugin", "register module", "extension"]):
            return IntentType.PLUGIN
        elif any(w in prompt_lower for w in [
            "organize", "clean up", "cleanup", "sort", "categorize",
            "automate", "monitor", "watch", "track",
            "analyze all", "process all", "go through",
            "set up", "configure", "deploy",
            "research", "investigate", "explore",
            "migrate", "backup", "sync",
            "generate report", "summarize folder",
            "multi-step", "long running",
            "organize my", "sort my", "clean my",
        ]):
            return IntentType.AUTONOMOUS_GOAL
        else:
            return IntentType.CHAT
