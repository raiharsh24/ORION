from typing import Any, Optional
from loguru import logger

from app.autonomous_dev.models import AutonomousTask
from app.friday.workspace import WorkspaceManager
from app.friday.indexer import DocumentIndexer

class AutonomousExecutor:
    """
    Executes a single autonomous task.
    For this vertical slice, it's a simple, non-generic executor
    that calls specific services based on task description.
    """
    def __init__(self,
                 workspace_manager: Optional[WorkspaceManager] = None,
                 document_indexer: Optional[DocumentIndexer] = None):
        self._workspace_manager = workspace_manager
        self._document_indexer = document_indexer
        if not workspace_manager or not document_indexer:
            raise ValueError("AutonomousExecutor requires WorkspaceManager and DocumentIndexer.")
        logger.info("AutonomousExecutor initialized.")

    async def execute_task(self, task: AutonomousTask) -> Any:
        """
        Executes a task. This is the 'E' in the O-T-P-E-V-R-P loop.
        """
        if "inspect and analyze" in task.description.lower():
            return await self._execute_workspace_inspection()
        else:
            logger.warning(f"No execution logic for task: '{task.description}'")
            raise NotImplementedError(f"Execution for task '{task.description}' is not implemented.")

    async def _execute_workspace_inspection(self) -> dict:
        """
        Performs the workspace inspection by calling existing services.
        """
        logger.info("Executing workspace inspection...")
        if not self._workspace_manager or not self._document_indexer:
            return {"error": "Executor not fully initialized."}

        # 1. Discover projects in the workspace
        projects = self._workspace_manager.discover_projects()
        if not projects:
            return {"summary": "No projects found in the workspace."}

        project_summaries = []
        total_files_indexed = 0

        # For this slice, we focus on the first project found.
        # A full implementation would inspect all or a specified project.
        main_project = projects[0]
        project_path = main_project.get("path")
        project_name = main_project.get("name")

        # 2. Index the project directory
        if project_path:
            logger.info(f"Indexing directory: {project_path}")
            indexed_count = await self._document_indexer.index_directory(project_path, project_name)
            total_files_indexed += indexed_count

        summary = {
            "project_name": project_name,
            "path": project_path,
            "is_git": main_project.get("is_git"),
            "branch": main_project.get("branch"),
            "files_count": main_project.get("files_count"),
            "languages": main_project.get("languages"),
            "files_indexed_now": total_files_indexed
        }

        logger.info(f"Workspace inspection completed. Result: {summary}")
        return summary
