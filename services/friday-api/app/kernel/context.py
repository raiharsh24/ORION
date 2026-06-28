from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.kernel.state import KernelState
from app.kernel.config import FridayKernelConfig

class UserContext(BaseModel):
    username: str = "Harsh"
    roles: List[str] = Field(default_factory=lambda: ["admin"])
    permissions: List[str] = Field(default_factory=lambda: ["file_access", "process_control", "desktop_control"])

class MissionContext(BaseModel):
    active_mission_id: Optional[str] = None
    active_workflow_id: Optional[str] = None
    step_index: int = 0
    progress: float = 0.0

class WorkspaceContext(BaseModel):
    active_workspace_path: str = "/home/warlock/ORION"
    current_project_name: Optional[str] = None
    git_branch: Optional[str] = None

class SystemMetadata(BaseModel):
    version: str = "0.2.0"
    os_platform: str = "linux"
    debug_mode: bool = True

class FridayKernelContext(BaseModel):
    """
    Global coordinator context capturing system state, current user, active workspaces, 
    running missions, loaded services, and system configs.
    """
    user: UserContext = Field(default_factory=UserContext)
    mission: MissionContext = Field(default_factory=MissionContext)
    workspace: WorkspaceContext = Field(default_factory=WorkspaceContext)
    loaded_services: List[str] = Field(default_factory=list)
    state: KernelState = KernelState.STOPPED
    config: FridayKernelConfig = Field(default_factory=FridayKernelConfig)
    metadata: SystemMetadata = Field(default_factory=SystemMetadata)
