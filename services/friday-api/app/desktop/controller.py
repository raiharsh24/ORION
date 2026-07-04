from typing import List, Dict, Any, Optional, Tuple
from app.desktop.launcher import DesktopLauncher
from app.desktop.process_manager import ProcessManager
from app.desktop.window_manager import WindowManager
from app.desktop.clipboard import DesktopClipboard
from app.desktop.notifications import DesktopNotifier
from app.desktop.screenshot import ScreenshotHandler
from app.desktop.permissions import DesktopPermissionTracker
from app.desktop.input_controller import InputController
from app.capabilities.capability import BaseCapability

class DesktopController(BaseCapability):
    """
    Central controller for desktop operations.
    Acts as the façade.
    """
    def __init__(self) -> None:
        """Initialize the DesktopController and its specialized sub-modules."""
        self.launcher = DesktopLauncher()
        self.process_manager = ProcessManager()
        self.window_manager = WindowManager()
        self.clipboard = DesktopClipboard()
        self.notifier = DesktopNotifier()
        self.screenshot_handler = ScreenshotHandler()
        self.permission_manager = DesktopPermissionTracker()
        self.input_controller = InputController()

    @property
    def name(self) -> str:
        """Returns the unique name of the capability."""
        return "desktop_controller"

    @property
    def schema(self) -> Dict[str, Any]:
        """Returns the expected argument validation schema."""
        return {}

    async def initialize(self) -> None:
        """Set up connection parameters and resources."""
        pass

    async def validate(self, **kwargs) -> bool:
        """Validates argument values against structural schemas."""
        return True

    async def execute(self, **kwargs) -> Any:
        """Runs the primary action command."""
        pass

    async def rollback(self) -> bool:
        """Undoes action commands to restore previous states."""
        return True

    async def shutdown(self) -> None:
        """Closes connections and cleans up active resources."""
        pass

    async def open_application(self, app_name: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Launches a desktop application.

        Args:
            app_name (str): Name or path of the application.
            args (Optional[List[str]]): Startup arguments.

        Returns:
            Dict[str, Any]: Structured result mapping success status, PID, and messages.
        """
        if not await self.permission_manager.has_permission("desktop_control"):
            return {
                "success": False,
                "pid": None,
                "error": "Permission Denied: desktop_control permission is required.",
                "message": "Permission Denied."
            }
        return await self.launcher.launch(app_name, args)

    async def close_application(self, app_name: str) -> Dict[str, Any]:
        """
        Terminates running applications matching a process name.

        Args:
            app_name (str): Application process name.

        Returns:
            Dict[str, Any]: Structured success dictionary.
        """
        if not await self.permission_manager.has_permission("desktop_control"):
            return {
                "success": False,
                "error": "Permission Denied: desktop_control permission is required.",
                "message": "Permission Denied."
            }
        return await self.launcher.terminate(app_name)

    async def list_running_processes(self) -> List[Dict[str, Any]]:
        """
        Retrieves a list of all currently running system processes.

        Returns:
            List[Dict[str, Any]]: List of process metadata dictionaries.
        """
        if not await self.permission_manager.has_permission("process_control"):
            return []
        return await self.process_manager.list_processes()

    async def take_screenshot(self, save_path: Optional[str] = None) -> bytes:
        """
        Captures the current desktop screen.

        Args:
            save_path (Optional[str]): Target file path to write image.

        Returns:
            bytes: Raw image byte buffer.
        """
        if not await self.permission_manager.has_permission("desktop_control"):
            return b""
        return await self.screenshot_handler.capture_screen(save_path)

    async def show_notification(self, message: str, title: Optional[str] = None) -> bool:
        """
        Sends a desktop notification.

        Args:
            message (str): Body text of the notification.
            title (Optional[str]): Header title.

        Returns:
            bool: True if trigger succeeded.
        """
        if not await self.permission_manager.has_permission("desktop_control"):
            return False
        return await self.notifier.notify(message, title)

    async def copy_to_clipboard(self, text: str) -> bool:
        """
        Writes text to system clipboard.

        Args:
            text (str): String content to copy.

        Returns:
            bool: True if write succeeded.
        """
        if not await self.permission_manager.has_permission("desktop_control"):
            return False
        return await self.clipboard.set_text(text)

    async def read_clipboard(self) -> str:
        """
        Retrieves text from system clipboard.

        Returns:
            str: Clipboard string content.
        """
        if not await self.permission_manager.has_permission("desktop_control"):
            return ""
        return await self.clipboard.get_text()

    async def mouse_move(self, x: int, y: int) -> bool:
        if not await self.permission_manager.has_permission("desktop_control"):
            return False
        return await self.input_controller.mouse_move(x, y)

    async def mouse_click(self, button: str = "left") -> bool:
        if not await self.permission_manager.has_permission("desktop_control"):
            return False
        return await self.input_controller.mouse_click(button)

    async def mouse_double_click(self, button: str = "left") -> bool:
        if not await self.permission_manager.has_permission("desktop_control"):
            return False
        return await self.input_controller.mouse_double_click(button)

    async def mouse_right_click(self) -> bool:
        if not await self.permission_manager.has_permission("desktop_control"):
            return False
        return await self.input_controller.mouse_right_click()

    async def mouse_drag_drop(self, start_x: int, start_y: int, end_x: int, end_y: int) -> bool:
        if not await self.permission_manager.has_permission("desktop_control"):
            return False
        return await self.input_controller.mouse_drag_drop(start_x, start_y, end_x, end_y)

    async def mouse_position(self) -> Optional[Tuple[int, int]]:
        if not await self.permission_manager.has_permission("desktop_control"):
            return None
        return await self.input_controller.mouse_position()

    async def keyboard_type(self, text: str) -> bool:
        if not await self.permission_manager.has_permission("desktop_control"):
            return False
        return await self.input_controller.keyboard_type(text)

    async def keyboard_shortcut(self, combo: str) -> bool:
        if not await self.permission_manager.has_permission("desktop_control"):
            return False
        return await self.input_controller.keyboard_shortcut(combo)

    async def key_press(self, key: str) -> bool:
        if not await self.permission_manager.has_permission("desktop_control"):
            return False
        return await self.input_controller.key_press(key)

    async def window_focus(self, window_name: str) -> Dict[str, Any]:
        if not await self.permission_manager.has_permission("desktop_control"):
            return {"success": False, "error": "Permission Denied"}
        windows_info = await self.window_manager.list_windows()
        if not windows_info.get("success"):
            return {"success": False, "error": "Could not list windows"}
        for w in windows_info.get("windows", []):
            if window_name.lower() in w.get("name", "").lower():
                return await self.window_manager.focus_window(w["id"])
        return {"success": False, "error": f"Window '{window_name}' not found"}

    async def window_resize(self, window_id: str, width: int, height: int) -> Dict[str, Any]:
        if not await self.permission_manager.has_permission("desktop_control"):
            return {"success": False, "error": "Permission Denied"}
        return await self.window_manager.resize_window(window_id, width, height)

    async def file_explorer_open(self, folder_path: str) -> Dict[str, Any]:
        if not await self.permission_manager.has_permission("file_access"):
            return {"success": False, "error": "Permission Denied"}
        import os
        import sys
        import subprocess
        if not os.path.isdir(folder_path):
            return {"success": False, "error": f"Directory not found: {folder_path}"}
        try:
            if sys.platform == "win32":
                os.startfile(folder_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder_path])
            else:
                subprocess.Popen(["xdg-open", folder_path])
            return {"success": True, "message": f"Opened {folder_path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_system_summary(self) -> Dict[str, Any]:
        """
        Retrieves a summary of the current desktop and OS environment.

        Returns:
            Dict[str, Any]: Summary dictionary.
        """
        active_windows = 0
        try:
            windows_info = await self.window_manager.list_windows()
            if windows_info.get("success"):
                active_windows = len(windows_info.get("windows", []))
        except Exception:
            pass

        processes_tracked = 0
        try:
            procs = await self.process_manager.list_processes()
            processes_tracked = len(procs)
        except Exception:
            pass

        return {
            "status": "nominal",
            "active_windows": active_windows,
            "processes_tracked": processes_tracked
        }
