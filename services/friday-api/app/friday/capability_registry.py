from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from loguru import logger

class CapabilityMetadata(BaseModel):
    """
    Metadata describing a system capability registered in FRIDAY.
    """
    id: str
    name: str
    description: str
    version: str = "1.0.0"
    category: str = "system"  # "system", "developer", "knowledge", "plugin"
    permissions: str = "Public"  # "Public", "Trusted", "Privileged", "Dangerous", "Restricted"
    supported_operations: List[str] = Field(default_factory=list)
    required_confirmation: str = "Never"  # "Never", "Always", "DangerousOnly", "UserApproval", "PolicyDriven"
    timeout: float = 30.0  # seconds
    health: str = "HEALTHY"
    dependencies: List[str] = Field(default_factory=list)

class CapabilityRegistry:
    """
    Registry managing capability discovery, dynamic plugins registration, and schema querying.
    """
    def __init__(self) -> None:
        self._capabilities: Dict[str, CapabilityMetadata] = {}
        self._initialize_builtins()

    def _initialize_builtins(self) -> None:
        # Pre-populate built-ins
        builtins = [
            CapabilityMetadata(
                id="filesystem", name="Filesystem Operations",
                description="Read, write, list, and delete files on host workspace.",
                category="system", permissions="Dangerous",
                supported_operations=["read", "write", "delete", "list"],
                required_confirmation="DangerousOnly"
            ),
            CapabilityMetadata(
                id="terminal", name="Terminal Execution",
                description="Run shell commands directly on host host OS.",
                category="system", permissions="Dangerous",
                supported_operations=["execute"],
                required_confirmation="Always"
            ),
            CapabilityMetadata(
                id="memory", name="Memory System",
                description="Save, update and search working/session/user memory layers.",
                category="system", permissions="Trusted",
                supported_operations=["retrieve", "save", "summarize"]
            ),
            CapabilityMetadata(
                id="browser", name="Web Browser Automation",
                description="Open, close and automate chromium browser pages.",
                category="system", permissions="Trusted",
                supported_operations=["navigate", "click", "input", "screenshot"]
            ),
            CapabilityMetadata(
                id="knowledge", name="Knowledge Engine Search",
                description="Execute semantic search query matching in repository index.",
                category="knowledge", permissions="Public",
                supported_operations=["search", "index", "delete"]
            ),
            CapabilityMetadata(
                id="workflow", name="Workflow Orchestrator",
                description="Execute structured automation blueprints.",
                category="developer", permissions="Trusted",
                supported_operations=["run", "track"]
            ),
            CapabilityMetadata(
                id="mission", name="Mission Controller",
                description="Track long-running multi-agent goals.",
                category="developer", permissions="Trusted",
                supported_operations=["start", "cancel"]
            ),
            CapabilityMetadata(
                id="git", name="Git Version Control",
                description="Commit, checkout and log status inside repo.",
                category="developer", permissions="Trusted",
                supported_operations=["status", "commit", "log"]
            ),
            CapabilityMetadata(
                id="docker", name="Docker Sandbox Container Manager",
                description="Manage isolates container runtime nodes.",
                category="system", permissions="Privileged",
                supported_operations=["run", "stop", "list"]
            ),
            CapabilityMetadata(
                id="python", name="Python Execution Runtime",
                description="Evaluate sandboxed python script commands.",
                category="developer", permissions="Trusted",
                supported_operations=["eval", "run"]
            ),
            CapabilityMetadata(
                id="vision", name="Vision & Screen Understanding",
                description="Capture screenshots, analyze images, extract text via OCR, and build screen context for UI understanding.",
                category="system", permissions="Trusted",
                supported_operations=["screenshot", "analyze", "ocr", "screen_context", "clipboard_image"],
                timeout=60.0
            )
        ]
        for cap in builtins:
            self.register_capability(cap)

    def register_capability(self, metadata: CapabilityMetadata) -> None:
        logger.info(f"CapabilityRegistry registering: '{metadata.id}' v{metadata.version}")
        self._capabilities[metadata.id] = metadata

    def unregister_capability(self, capability_id: str) -> None:
        if capability_id in self._capabilities:
            logger.info(f"CapabilityRegistry unregistering: '{capability_id}'")
            del self._capabilities[capability_id]

    def get_capability(self, capability_id: str) -> Optional[CapabilityMetadata]:
        return self._capabilities.get(capability_id)

    def list_capabilities(self) -> Dict[str, CapabilityMetadata]:
        return self._capabilities.copy()
