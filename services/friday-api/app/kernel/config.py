from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class PathsConfig(BaseModel):
    workspace_root: str = "/home/warlock/ORION"
    persist_dir: str = ".friday_kb"
    temp_dir: str = "tmp"

class ModelsConfig(BaseModel):
    default_llm: str = "gemini-1.5-pro"
    embedding_model: str = "text-embedding-004"

class APIKeysConfig(BaseModel):
    gemini_api_key: Optional[str] = None

class WorkspaceConfig(BaseModel):
    tracked_projects: List[str] = Field(default_factory=list)
    watch_for_changes: bool = True

class LoggingConfig(BaseModel):
    level: str = "DEBUG"
    file_path: Optional[str] = None

class PluginsConfig(BaseModel):
    enabled_plugins: List[str] = Field(default_factory=list)
    plugin_dir: str = "plugins"

class DesktopConfig(BaseModel):
    allow_process_control: bool = True
    allow_desktop_control: bool = True

class MemoryConfig(BaseModel):
    max_history_sessions: int = 100
    store_type: str = "in_memory"

class KnowledgeConfig(BaseModel):
    chunk_size: int = 1000
    chunk_overlap: int = 200
    vector_db_type: str = "chromadb"

class MCPServerEntry(BaseModel):
    server_name: str
    transport: str = "stdio"
    command: str = ""
    args: List[str] = Field(default_factory=list)
    url: str = ""
    api_key: Optional[str] = None
    timeout_seconds: float = 30.0
    auto_reconnect: bool = True

class MCPConfig(BaseModel):
    servers: List[MCPServerEntry] = Field(default_factory=list)

class FridayKernelConfig(BaseModel):
    """
    Global configuration model schema for the central FRIDAY system kernel.
    Defines structural configurations for nested components and subsystems.
    """
    paths: PathsConfig = Field(default_factory=PathsConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    api_keys: APIKeysConfig = Field(default_factory=APIKeysConfig)
    workspace: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)
    desktop: DesktopConfig = Field(default_factory=DesktopConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)

    @classmethod
    def load_defaults(cls) -> 'FridayKernelConfig':
        """
        Loads default configuration mapping configuration schemas.
        """
        return cls()
