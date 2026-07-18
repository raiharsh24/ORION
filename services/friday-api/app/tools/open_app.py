from typing import List
import subprocess
import shutil
import sys
from app.tools.base import ToolParameter, ToolExample
from app.tools.base_tool import BaseTool

class OpenAppTool(BaseTool):
    """
    Opens desktop applications or system targets (such as local documents or web URLs).
    Runs processes in detached mode to avoid blocking FRIDAY.
    """
    @property
    def name(self) -> str:
        return "open_app"

    @property
    def description(self) -> str:
        return "Open a desktop application, file, or URL with the default handler."

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(name="app_name", type="string", description="Application name or path to launch", required=True),
            ToolParameter(name="target", type="string", description="Optional file or URL to open with the application", required=False),
        ]

    @property
    def examples(self) -> List[ToolExample]:
        return [
            ToolExample(prompt="Open Firefox", args={"app_name": "firefox"}, description="Launch the Firefox browser"),
            ToolExample(prompt="Open README", args={"app_name": "default", "target": "README.md"}, description="Open README.md with the default text editor"),
        ]

    def requires_confirmation(self, **kwargs) -> bool:
        return False

    async def execute(self, **kwargs) -> str:
        app_name = kwargs.get("app_name")
        target = kwargs.get("target")

        if not app_name:
            return "Error: Missing required parameter 'app_name'."

        try:
            cmd = []
            if app_name.lower() == "default" and target:
                if sys.platform.startswith("linux"):
                    cmd = ["xdg-open", target]
                elif sys.platform == "darwin":
                    cmd = ["open", target]
                elif sys.platform == "win32":
                    cmd = ["start", target]
            else:
                executable = shutil.which(app_name)
                if not executable:
                    executable = app_name
                cmd = [executable]
                if target:
                    cmd.append(target)

            # Start detached background process
            if sys.platform == "win32":
                DETACHED_PROCESS = 0x00000008
                subprocess.Popen(
                    cmd,
                    creationflags=DETACHED_PROCESS,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                subprocess.Popen(
                    cmd,
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

            return f"Successfully launched '{app_name}'" + (f" with target '{target}'" if target else "") + " in a detached background process."
        except Exception as e:
            return f"Error: Failed to open application '{app_name}': {str(e)}"
