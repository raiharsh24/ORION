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
        elif any(w in prompt_lower for w in ["plugin", "register module", "extension"]):
            return IntentType.PLUGIN
        else:
            return IntentType.CHAT
