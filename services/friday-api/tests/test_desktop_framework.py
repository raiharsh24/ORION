import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.desktop.launcher import DesktopLauncher
from app.desktop.process_manager import ProcessManager
from app.desktop.window_manager import WindowManager
from app.desktop.clipboard import DesktopClipboard
from app.desktop.notifications import DesktopNotifier
from app.desktop.screenshot import ScreenshotHandler
from app.desktop.permissions import DesktopPermissionTracker
from app.desktop.controller import DesktopController

from app.tools.desktop_tools import (
    OpenApplicationTool, CloseApplicationTool, ScreenshotTool,
    ClipboardCopyTool, ClipboardReadTool, NotificationsTool
)

@pytest.mark.anyio
async def test_desktop_launcher():
    launcher = DesktopLauncher()
    # Test launch missing executable
    res = await launcher.launch("nonexistent_executable_12345")
    assert res["success"] is False
    assert "not found" in res["error"].lower()

    # Mock subprocess.Popen
    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.pid = 99999
        mock_popen.return_value = mock_proc
        
        # Launch with mock executable in PATH
        with patch("shutil.which", return_value="/bin/true"):
            res = await launcher.launch("true", ["--args"])
            assert res["success"] is True
            assert res["pid"] == 99999
            mock_popen.assert_called_once()

    # Test terminate
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        res = await launcher.terminate("test_app")
        assert res["success"] is True

        mock_run.return_value.returncode = 1
        res = await launcher.terminate("test_app")
        assert res["success"] is False


@pytest.mark.anyio
async def test_process_manager():
    pm = ProcessManager()
    
    # Check listing processes
    procs = await pm.list_processes()
    assert isinstance(procs, list)
    if procs:
        p = procs[0]
        assert "pid" in p
        assert "name" in p
        assert "status" in p

    # Test is_running
    with patch.object(pm, "list_processes", return_value=[{"pid": 123, "name": "PythonTest", "status": "running"}]):
        assert await pm.is_running("pythontest") is True
        assert await pm.is_running("nonexistent") is False

    # Test terminate_process
    with patch("os.kill") as mock_kill:
        assert await pm.terminate_process(123) is True
        mock_kill.assert_called_once()


@pytest.mark.anyio
async def test_clipboard():
    clip = DesktopClipboard()
    
    # Test setting and getting text (headless mode fallback)
    with patch.object(clip, "_has_display", return_value=False):
        assert await clip.set_text("Hello Clipboard") is True
        text = await clip.get_text()
        assert text == "Hello Clipboard"

    # Test set/get with DISPLAY / mock subprocess
    with patch.object(clip, "_has_display", return_value=True):
        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.communicate.return_value = (b"X11 Clipboard Content", None)
            mock_proc.returncode = 0
            mock_popen.return_value = mock_proc
            
            text = await clip.get_text()
            assert text == "X11 Clipboard Content"


@pytest.mark.anyio
async def test_notifier():
    notifier = DesktopNotifier()
    with patch("shutil.which", return_value="/usr/bin/notify-send"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            res = await notifier.notify("Body message", "Title text")
            assert res is True
            mock_run.assert_called_once()


@pytest.mark.anyio
async def test_screenshot():
    handler = ScreenshotHandler()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = os.path.join(tmpdir, "screenshot.png")
        # Ensure it falls back and writes the transparent PNG dummy
        with patch("shutil.which", return_value=None):
            bytes_out = await handler.capture_screen(save_path)
            assert len(bytes_out) > 0
            assert os.path.exists(save_path)
            # Verify it contains dummy PNG
            with open(save_path, "rb") as f:
                content = f.read()
                assert b"PNG" in content


@pytest.mark.anyio
async def test_permissions():
    tracker = DesktopPermissionTracker()
    assert await tracker.has_permission("desktop_control") is True
    
    missing = await tracker.verify_permissions()
    assert len(missing) == 0

    await tracker.revoke_permission("desktop_control")
    assert await tracker.has_permission("desktop_control") is False
    missing = await tracker.verify_permissions()
    assert "desktop_control" in missing

    await tracker.grant_permission("desktop_control")
    assert await tracker.has_permission("desktop_control") is True


@pytest.mark.anyio
async def test_window_manager():
    wm = WindowManager()
    
    with patch.object(wm, "_has_xdotool", return_value=False):
        res = await wm.list_windows()
        assert res["success"] is False
        assert "not implemented" in res["error"].lower()
        
        res = await wm.focus_window("123")
        assert res["success"] is False
        
        res = await wm.minimize_window("123")
        assert res["success"] is False
        
        res = await wm.maximize_window("123")
        assert res["success"] is False

    with patch.object(wm, "_has_xdotool", return_value=True):
        with patch("subprocess.run") as mock_run:
            # list_windows mock
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "12345\n67890\n"
            
            res = await wm.list_windows()
            assert res["success"] is True
            assert len(res["windows"]) > 0


@pytest.mark.anyio
async def test_controller_and_tools():
    controller = DesktopController()
    
    # Revoke permission and test blocking
    await controller.permission_manager.revoke_permission("desktop_control")
    res = await controller.open_application("test")
    assert res["success"] is False
    assert "Permission Denied" in res["message"]

    res = await controller.close_application("test")
    assert res["success"] is False
    assert "Permission Denied" in res["message"]

    res_bytes = await controller.take_screenshot()
    assert res_bytes == b""

    res_notify = await controller.show_notification("hello")
    assert res_notify is False

    res_copy = await controller.copy_to_clipboard("test")
    assert res_copy is False

    res_read = await controller.read_clipboard()
    assert res_read == ""

    # Grant permissions back
    await controller.permission_manager.grant_permission("desktop_control")
    
    # Test mock success execution routes through controller
    with patch.object(controller.launcher, "launch", return_value={"success": True, "pid": 123}) as mock_launch:
        res = await controller.open_application("app", ["-arg"])
        assert res["success"] is True
        mock_launch.assert_called_with("app", ["-arg"])

    with patch.object(controller.launcher, "terminate", return_value={"success": True}) as mock_term:
        res = await controller.close_application("app")
        assert res["success"] is True
        mock_term.assert_called_with("app")

    # Test tools execution
    # 1. OpenApplicationTool
    tool_open = OpenApplicationTool(controller)
    assert tool_open.name == "desktop.open_application"
    with patch.object(controller.launcher, "launch", return_value={"success": True, "pid": 123}):
        tool_res = await tool_open.execute(app_name="dummy")
        assert tool_res["success"] is True

    # Test open failure cases
    tool_res = await tool_open.execute()
    assert tool_res["success"] is False

    # 2. CloseApplicationTool
    tool_close = CloseApplicationTool(controller)
    assert tool_close.name == "desktop.close_application"
    with patch.object(controller.launcher, "terminate", return_value={"success": True}):
        tool_res = await tool_close.execute(app_name="dummy")
        assert tool_res["success"] is True

    tool_res = await tool_close.execute()
    assert tool_res["success"] is False

    # 3. ScreenshotTool
    tool_screenshot = ScreenshotTool(controller)
    assert tool_screenshot.name == "desktop.screenshot"
    with patch.object(controller.screenshot_handler, "capture_screen", return_value=b"png-data"):
        tool_res = await tool_screenshot.execute()
        assert tool_res["success"] is True
        assert tool_res["size_bytes"] == len(b"png-data")

    with patch.object(controller.screenshot_handler, "capture_screen", return_value=b""):
        tool_res = await tool_screenshot.execute()
        assert tool_res["success"] is False

    # 4. ClipboardCopyTool
    tool_copy = ClipboardCopyTool(controller)
    assert tool_copy.name == "desktop.clipboard.copy"
    tool_res = await tool_copy.execute(text="copy-test")
    assert tool_res["success"] is True

    tool_res = await tool_copy.execute()
    assert tool_res["success"] is False

    # 5. ClipboardReadTool
    tool_read = ClipboardReadTool(controller)
    assert tool_read.name == "desktop.clipboard.read"
    with patch.object(controller.clipboard, "get_text", return_value="read-test"):
        tool_res = await tool_read.execute()
        assert tool_res["success"] is True
        assert tool_res["text"] == "read-test"

    # 6. NotificationsTool
    tool_notify = NotificationsTool(controller)
    assert tool_notify.name == "desktop.notifications"
    with patch.object(controller.notifier, "notify", return_value=True):
        tool_res = await tool_notify.execute(message="Hello msg")
        assert tool_res["success"] is True

    tool_res = await tool_notify.execute()
    assert tool_res["success"] is False
    
    # System summary
    summary = await controller.get_system_summary()
    assert summary["status"] == "nominal"
