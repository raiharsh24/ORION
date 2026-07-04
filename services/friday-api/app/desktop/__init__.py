"""
Desktop automation package.
Contains application controller, launchers, window and process trackers,
screenshots, clipboard operations, notifications, permission tracks,
input controller, action planner, overlay, and mission playback.
"""
from app.desktop.controller import DesktopController
from app.desktop.launcher import DesktopLauncher
from app.desktop.process_manager import ProcessManager
from app.desktop.window_manager import WindowManager
from app.desktop.screenshot import ScreenshotHandler
from app.desktop.clipboard import DesktopClipboard
from app.desktop.notifications import DesktopNotifier
from app.desktop.permissions import DesktopPermissionTracker
from app.desktop.input_controller import InputController
from app.desktop.action_planner import DesktopActionPlanner
from app.desktop.overlay import DesktopOverlayService
from app.desktop.playback import MissionRecorder, MissionPlayback

__all__ = [
    "DesktopController",
    "DesktopLauncher",
    "ProcessManager",
    "WindowManager",
    "ScreenshotHandler",
    "DesktopClipboard",
    "DesktopNotifier",
    "DesktopPermissionTracker",
    "InputController",
    "DesktopActionPlanner",
    "DesktopOverlayService",
    "MissionRecorder",
    "MissionPlayback",
]
