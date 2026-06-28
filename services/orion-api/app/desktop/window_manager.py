import shutil
import subprocess
from typing import List, Dict, Any

class WindowManager:
    """
    Controls desktop GUI window focus, minimization, and list states.
    Uses 'xdotool' on Linux/X11 displays when available.
    """
    def __init__(self) -> None:
        """Initialize the WindowManager."""
        pass

    def _has_xdotool(self) -> bool:
        return shutil.which("xdotool") is not None

    async def list_windows(self) -> Dict[str, Any]:
        """
        Retrieves details of active desktop windows.

        Returns:
            Dict[str, Any]: Structured window detail dictionary.
        """
        if not self._has_xdotool():
            return {
                "success": False,
                "error": "Not implemented: xdotool is missing or display unavailable.",
                "windows": []
            }
        
        try:
            # Query visible window IDs matching any name regex
            proc = subprocess.run(
                ["xdotool", "search", "--onlyvisible", "--name", ".*"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True
            )
            if proc.returncode == 0:
                windows = []
                window_ids = [w.strip() for w in proc.stdout.splitlines() if w.strip()]
                for wid in window_ids[:10]:  # Limit to top 10 visible windows to keep it fast
                    name_proc = subprocess.run(
                        ["xdotool", "getwindowname", wid],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        text=True
                    )
                    name = name_proc.stdout.strip() if name_proc.returncode == 0 else "Unnamed Window"
                    windows.append({
                        "id": wid,
                        "name": name,
                        "focused": False
                    })
                return {
                    "success": True,
                    "error": None,
                    "windows": windows
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "windows": []
            }

        return {
            "success": False,
            "error": "X11 window query failed.",
            "windows": []
        }

    async def focus_window(self, window_id: str) -> Dict[str, Any]:
        """
        Brings a window to the foreground.

        Args:
            window_id (str): Identifier of the target window.

        Returns:
            Dict[str, Any]: Structured success indicator.
        """
        if not self._has_xdotool():
            return {"success": False, "error": "Not implemented: xdotool is missing."}
        try:
            proc = subprocess.run(
                ["xdotool", "windowactivate", window_id],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return {
                "success": proc.returncode == 0,
                "error": None if proc.returncode == 0 else "Window activate command failed."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def minimize_window(self, window_id: str) -> Dict[str, Any]:
        """
        Minimizes the window.

        Args:
            window_id (str): Window ID.

        Returns:
            Dict[str, Any]: Structured success indicator.
        """
        if not self._has_xdotool():
            return {"success": False, "error": "Not implemented: xdotool is missing."}
        try:
            proc = subprocess.run(
                ["xdotool", "windowminimize", window_id],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return {
                "success": proc.returncode == 0,
                "error": None if proc.returncode == 0 else "Window minimize command failed."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def maximize_window(self, window_id: str) -> Dict[str, Any]:
        """
        Maximizes the window.

        Args:
            window_id (str): Window ID.

        Returns:
            Dict[str, Any]: Structured success indicator.
        """
        return {
            "success": False,
            "error": "Maximize window operation not implemented."
        }
