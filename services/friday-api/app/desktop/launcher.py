import os
import shutil
import sys
import subprocess
from typing import List, Optional, Dict, Any

class DesktopLauncher:
    """
    Launches and closes OS applications by executable name or path in a detached process group.
    """
    def __init__(self) -> None:
        """Initialize the DesktopLauncher."""
        pass

    async def launch(self, app_name: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Launches a desktop application.

        Args:
            app_name (str): Name or path of the application.
            args (Optional[List[str]]): Startup arguments.

        Returns:
            Dict[str, Any]: Structured result mapping success status, PID, and messages.
        """
        try:
            executable = shutil.which(app_name)
            if not executable:
                if os.path.exists(app_name):
                    executable = app_name
                else:
                    return {
                        "success": False,
                        "pid": None,
                        "error": f"Executable '{app_name}' not found in system PATH or filesystem.",
                        "message": "Launch failed: Executable not found."
                    }

            cmd = [executable]
            if args:
                cmd.extend(args)

            if sys.platform == "win32":
                # DETACHED_PROCESS creation flag for Windows
                DETACHED_PROCESS = 0x00000008
                proc = subprocess.Popen(
                    cmd,
                    creationflags=DETACHED_PROCESS,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                # Spawn detached group on Unix systems
                proc = subprocess.Popen(
                    cmd,
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )

            return {
                "success": True,
                "pid": proc.pid,
                "error": None,
                "message": f"Successfully launched '{app_name}' (PID: {proc.pid})."
            }
        except Exception as e:
            return {
                "success": False,
                "pid": None,
                "error": str(e),
                "message": f"Failed to launch '{app_name}': {str(e)}"
            }

    async def terminate(self, app_name: str) -> Dict[str, Any]:
        """
        Terminates running applications matching a process name.

        Args:
            app_name (str): Application process name.

        Returns:
            Dict[str, Any]: Structured success dictionary.
        """
        try:
            if sys.platform == "win32":
                proc = subprocess.run(
                    ["taskkill", "/F", "/IM", app_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                success = proc.returncode == 0
            else:
                # Kill processes using pkill on Linux/Mac
                proc = subprocess.run(
                    ["pkill", "-f", app_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                success = proc.returncode == 0

            if success:
                return {
                    "success": True,
                    "error": None,
                    "message": f"Successfully terminated processes matching '{app_name}'."
                }
            else:
                return {
                    "success": False,
                    "error": "No matching processes found or command failed.",
                    "message": f"Failed to terminate processes matching '{app_name}'."
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to terminate '{app_name}': {str(e)}"
            }
