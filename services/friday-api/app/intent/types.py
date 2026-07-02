from enum import Enum


class IntentType(str, Enum):
    CONVERSATION = "conversation"
    CODING = "coding"
    TERMINAL = "terminal"
    DESKTOP = "desktop"
    BROWSER = "browser"
    WORKFLOW = "workflow"
    PLANNING = "planning"
    MEMORY = "memory"
    SEARCH = "search"
    VISION = "vision"
    UNKNOWN = "unknown"
