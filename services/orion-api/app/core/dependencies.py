import os
from app.memory import ConversationMemory
from app.orion import ToolRegistry
from app.tools import (
    BrowserTool, FilesystemTool, TerminalTool,
    ClipboardTool, OpenAppTool, KnowledgeSearchTool,
    OpenApplicationTool, CloseApplicationTool, ScreenshotTool,
    ClipboardCopyTool, ClipboardReadTool, NotificationsTool
)
from app.orion.workspace import WorkspaceManager
from app.orion.vectordb import VectorDB
from app.memory.embeddings import EmbeddingsManager
from app.orion.indexer import DocumentIndexer
from app.orion.retrieval import RetrievalEngine
from app.capabilities import CapabilityRegistry
from app.desktop.controller import DesktopController

# Share singletons globally to maintain state
memory_store = ConversationMemory()
tool_registry = ToolRegistry()
capability_registry = CapabilityRegistry()

desktop_controller = DesktopController()
capability_registry.register(desktop_controller)

# Configure workspace path discovery
workspace_root = "/home/warlock/ORION"
workspace_manager = WorkspaceManager(workspace_root)

# Resolve persistent vector database directory path
api_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
persist_dir = os.path.join(api_dir, ".orion_kb")
vector_db = VectorDB(persist_dir)

embeddings_manager = EmbeddingsManager()
document_indexer = DocumentIndexer(vector_db, embeddings_manager)
retrieval_engine = RetrievalEngine(vector_db, embeddings_manager)

# Register Action Engine tools
tool_registry.register("browser", BrowserTool())
tool_registry.register("filesystem", FilesystemTool())
tool_registry.register("terminal", TerminalTool())
tool_registry.register("clipboard", ClipboardTool())
tool_registry.register("open_app", OpenAppTool())
tool_registry.register("knowledge.search", KnowledgeSearchTool(retrieval_engine))

# Register Desktop subsystem tools
tool_registry.register("desktop.open_application", OpenApplicationTool(desktop_controller))
tool_registry.register("desktop.close_application", CloseApplicationTool(desktop_controller))
tool_registry.register("desktop.screenshot", ScreenshotTool(desktop_controller))
tool_registry.register("desktop.clipboard.copy", ClipboardCopyTool(desktop_controller))
tool_registry.register("desktop.clipboard.read", ClipboardReadTool(desktop_controller))
tool_registry.register("desktop.notifications", NotificationsTool(desktop_controller))
