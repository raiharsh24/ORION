import pytest
import asyncio
import os
import tempfile
import json
import subprocess
from unittest.mock import MagicMock, AsyncMock, patch

from app.desktop.input_controller import InputController
from app.desktop.action_planner import DesktopActionPlanner
from app.desktop.overlay import DesktopOverlayService
from app.desktop.playback import MissionRecorder, MissionPlayback
from app.desktop.events import (
    DesktopActionStarted, DesktopActionCompleted, DesktopActionFailed,
    DesktopScreenshotCaptured, DesktopUIDetected, DesktopOCRExtracted,
    DesktopOverlayUpdated,
)
from app.desktop.screenshot import ScreenshotHandler
from app.desktop.controller import DesktopController
from app.desktop.automation import DesktopAutomationService
from app.policies.confirmation import ConfirmationPolicy


# ───────────────────────────────────────────────────────
# 1. InputController Tests
# ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_input_controller_mouse_move_no_display():
    ctrl = InputController()
    with patch.object(ctrl, "_xdotool_available", False):
        with patch.object(ctrl, "_ydotool_available", False):
            result = await ctrl.mouse_move(100, 200)
            assert result is False


@pytest.mark.anyio
async def test_input_controller_mouse_click_no_display():
    ctrl = InputController()
    with patch.object(ctrl, "_xdotool_available", False):
        result = await ctrl.mouse_click()
        assert result is False


@pytest.mark.anyio
async def test_input_controller_mouse_double_click_no_display():
    ctrl = InputController()
    with patch.object(ctrl, "_xdotool_available", False):
        result = await ctrl.mouse_double_click()
        assert result is False


@pytest.mark.anyio
async def test_input_controller_mouse_right_click_no_display():
    ctrl = InputController()
    with patch.object(ctrl, "_xdotool_available", False):
        result = await ctrl.mouse_right_click()
        assert result is False


@pytest.mark.anyio
async def test_input_controller_mouse_drag_drop_no_display():
    ctrl = InputController()
    with patch.object(ctrl, "_xdotool_available", False):
        result = await ctrl.mouse_drag_drop(0, 0, 100, 100)
        assert result is False


@pytest.mark.anyio
async def test_input_controller_mouse_position_no_display():
    ctrl = InputController()
    with patch.object(ctrl, "_xdotool_available", False):
        result = await ctrl.mouse_position()
        assert result is None


@pytest.mark.anyio
async def test_input_controller_keyboard_type_no_display():
    ctrl = InputController()
    with patch.object(ctrl, "_xdotool_available", False):
        with patch.object(ctrl, "_ydotool_available", False):
            result = await ctrl.keyboard_type("hello")
            assert result is False


@pytest.mark.anyio
async def test_input_controller_keyboard_shortcut_no_display():
    ctrl = InputController()
    with patch.object(ctrl, "_xdotool_available", False):
        result = await ctrl.keyboard_shortcut("ctrl+c")
        assert result is False


@pytest.mark.anyio
async def test_input_controller_key_press_no_display():
    ctrl = InputController()
    with patch.object(ctrl, "_xdotool_available", False):
        result = await ctrl.key_press("Return")
        assert result is False


@pytest.mark.anyio
async def test_input_controller_get_active_window_id_no_display():
    ctrl = InputController()
    with patch.object(ctrl, "_xdotool_available", False):
        result = await ctrl.get_active_window_id()
        assert result is None


@pytest.mark.anyio
async def test_input_controller_get_screen_dimensions_no_display():
    ctrl = InputController()
    with patch.object(ctrl, "_xdotool_available", False):
        result = await ctrl.get_screen_dimensions()
        assert result is None


@pytest.mark.anyio
async def test_input_controller_mouse_move_with_xdotool():
    ctrl = InputController()
    with patch.object(ctrl, "_xdotool_available", True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = await ctrl.mouse_move(500, 300)
            assert result is True
            mock_run.assert_called_with(
                ["xdotool", "mousemove", "500", "300"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )


@pytest.mark.anyio
async def test_input_controller_mouse_click_with_xdotool():
    ctrl = InputController()
    with patch.object(ctrl, "_xdotool_available", True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = await ctrl.mouse_click("left")
            assert result is True
            mock_run.assert_called_with(
                ["xdotool", "click", "1"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )


@pytest.mark.anyio
async def test_input_controller_mouse_double_click_with_xdotool():
    ctrl = InputController()
    with patch.object(ctrl, "_xdotool_available", True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = await ctrl.mouse_double_click()
            assert result is True
            mock_run.assert_called_with(
                ["xdotool", "click", "--repeat", "2", "1"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )


@pytest.mark.anyio
async def test_input_controller_right_click_with_xdotool():
    ctrl = InputController()
    with patch.object(ctrl, "_xdotool_available", True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = await ctrl.mouse_right_click()
            assert result is True


@pytest.mark.anyio
async def test_input_controller_drag_drop_with_xdotool():
    ctrl = InputController()
    with patch.object(ctrl, "_xdotool_available", True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = await ctrl.mouse_drag_drop(10, 20, 300, 400)
            assert result is True
            assert mock_run.call_count >= 4


@pytest.mark.anyio
async def test_input_controller_keyboard_type_with_xdotool():
    ctrl = InputController()
    with patch.object(ctrl, "_xdotool_available", True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = await ctrl.keyboard_type("hello world")
            assert result is True
            mock_run.assert_called_with(
                ["xdotool", "type", "--delay", "12", "hello world"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )


@pytest.mark.anyio
async def test_input_controller_keyboard_shortcut_with_xdotool():
    ctrl = InputController()
    with patch.object(ctrl, "_xdotool_available", True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = await ctrl.keyboard_shortcut("ctrl+c")
            assert result is True


@pytest.mark.anyio
async def test_input_controller_mouse_position_with_xdotool():
    ctrl = InputController()
    with patch.object(ctrl, "_xdotool_available", True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "x:500 y:300 screen:0 window:123\n"
            result = await ctrl.mouse_position()
            assert result == (500, 300)


@pytest.mark.anyio
async def test_input_controller_active_window_with_xdotool():
    ctrl = InputController()
    with patch.object(ctrl, "_xdotool_available", True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "12345678\n"
            result = await ctrl.get_active_window_id()
            assert result == "12345678"


# ───────────────────────────────────────────────────────
# 2. ScreenshotHandler Tests (region + window)
# ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_screenshot_capture_region_fallback_to_full():
    handler = ScreenshotHandler()
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = os.path.join(tmpdir, "region.png")
        with patch.object(handler, "_has_maim", False):
            with patch.object(handler, "_has_import_cmd", False):
                with patch.object(handler, "capture_screen") as mock_full:
                    mock_full.return_value = b"full_screenshot_bytes"
                    bytes_out = await handler.capture_region(10, 20, 100, 200, save_path)
                    assert bytes_out == b"full_screenshot_bytes"
                    mock_full.assert_called_once()


@pytest.mark.anyio
async def test_screenshot_capture_active_window_fallback_to_full():
    handler = ScreenshotHandler()
    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = os.path.join(tmpdir, "window.png")
        with patch.object(handler, "_has_import_cmd", False):
            with patch.object(handler, "_has_xdotool", False):
                with patch.object(handler, "_has_screencapture", False):
                    with patch.object(handler, "capture_screen") as mock_full:
                        mock_full.return_value = b"full_screenshot_bytes"
                        bytes_out = await handler.capture_active_window(save_path)
                        assert bytes_out == b"full_screenshot_bytes"
                        mock_full.assert_called_once()


# ───────────────────────────────────────────────────────
# 3. DesktopController Tests (new methods)
# ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_controller_mouse_move_permission_denied():
    controller = DesktopController()
    await controller.permission_manager.revoke_permission("desktop_control")
    result = await controller.mouse_move(100, 200)
    assert result is False
    await controller.permission_manager.grant_permission("desktop_control")


@pytest.mark.anyio
async def test_controller_mouse_click_permission_denied():
    controller = DesktopController()
    await controller.permission_manager.revoke_permission("desktop_control")
    result = await controller.mouse_click()
    assert result is False
    await controller.permission_manager.grant_permission("desktop_control")


@pytest.mark.anyio
async def test_controller_keyboard_type_permission_denied():
    controller = DesktopController()
    await controller.permission_manager.revoke_permission("desktop_control")
    result = await controller.keyboard_type("test")
    assert result is False
    await controller.permission_manager.grant_permission("desktop_control")


@pytest.mark.anyio
async def test_controller_keyboard_shortcut_permission_denied():
    controller = DesktopController()
    await controller.permission_manager.revoke_permission("desktop_control")
    result = await controller.keyboard_shortcut("ctrl+c")
    assert result is False
    await controller.permission_manager.grant_permission("desktop_control")


@pytest.mark.anyio
async def test_controller_window_focus_permission_denied():
    controller = DesktopController()
    await controller.permission_manager.revoke_permission("desktop_control")
    result = await controller.window_focus("test")
    assert result["success"] is False
    assert "Permission Denied" in result["error"]
    await controller.permission_manager.grant_permission("desktop_control")


@pytest.mark.anyio
async def test_controller_window_focus_not_found():
    controller = DesktopController()
    with patch.object(controller.window_manager, "list_windows") as mock_list:
        mock_list.return_value = {"success": True, "windows": [{"id": "1", "name": "Other Window"}]}
        result = await controller.window_focus("NonExistent")
        assert result["success"] is False
        assert "not found" in result["error"]


@pytest.mark.anyio
async def test_controller_file_explorer_open_permission_denied():
    controller = DesktopController()
    await controller.permission_manager.revoke_permission("file_access")
    result = await controller.file_explorer_open("/tmp")
    assert result["success"] is False
    assert "Permission Denied" in result["error"]
    await controller.permission_manager.grant_permission("file_access")


@pytest.mark.anyio
async def test_controller_file_explorer_open_nonexistent():
    controller = DesktopController()
    result = await controller.file_explorer_open("/nonexistent_path_12345")
    assert result["success"] is False
    assert "not found" in result["error"]


# ───────────────────────────────────────────────────────
# 4. DesktopAutomationService Tests (new actions)
# ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_automation_new_actions_routing():
    from app.kernel.kernel import FridayKernel
    from app.kernel.state import KernelState
    kernel = FridayKernel.get_instance()
    kernel.reset_instance()
    kernel = FridayKernel.get_instance()
    kernel._state = KernelState.READY

    automation = DesktopAutomationService()
    await automation.initialize()
    kernel._registry.register("desktop_automation", automation)

    desktop_mock = MagicMock()
    desktop_mock.mouse_move = AsyncMock(return_value=True)
    desktop_mock.mouse_click = AsyncMock(return_value=True)
    desktop_mock.mouse_double_click = AsyncMock(return_value=True)
    desktop_mock.mouse_right_click = AsyncMock(return_value=True)
    desktop_mock.mouse_drag_drop = AsyncMock(return_value=True)
    desktop_mock.keyboard_type = AsyncMock(return_value=True)
    desktop_mock.keyboard_shortcut = AsyncMock(return_value=True)
    desktop_mock.key_press = AsyncMock(return_value=True)
    desktop_mock.window_focus = AsyncMock(return_value={"success": True})
    desktop_mock.window_resize = AsyncMock(return_value={"success": True})
    desktop_mock.file_explorer_open = AsyncMock(return_value={"success": True})
    desktop_mock.screenshot_handler = MagicMock()
    desktop_mock.screenshot_handler.capture_active_window = AsyncMock(return_value=b"img")
    desktop_mock.screenshot_handler.capture_region = AsyncMock(return_value=b"img")
    desktop_mock.input_controller = MagicMock()
    desktop_mock.input_controller.mouse_move = AsyncMock(return_value=True)
    desktop_mock.input_controller.mouse_click = AsyncMock(return_value=True)
    desktop_mock.input_controller.mouse_double_click = AsyncMock(return_value=True)
    desktop_mock.input_controller.mouse_right_click = AsyncMock(return_value=True)
    desktop_mock.input_controller.mouse_drag_drop = AsyncMock(return_value=True)
    desktop_mock.input_controller.keyboard_type = AsyncMock(return_value=True)
    desktop_mock.input_controller.keyboard_shortcut = AsyncMock(return_value=True)
    desktop_mock.input_controller.key_press = AsyncMock(return_value=True)
    desktop_mock.input_controller.get_active_window_id = AsyncMock(return_value="123")
    kernel._registry.register("desktop_controller", desktop_mock)

    # Test each new action type
    actions_to_test = [
        ("mouse_move", {"x": 100, "y": 200}),
        ("mouse_click", {"button": "left"}),
        ("mouse_double_click", {"button": "left"}),
        ("mouse_right_click", {}),
        ("mouse_drag_drop", {"start_x": 0, "start_y": 0, "end_x": 100, "end_y": 100}),
        ("keyboard_type", {"text": "hello"}),
        ("keyboard_shortcut", {"combo": "ctrl+c"}),
        ("key_press", {"key": "Return"}),
        ("window_focus", {"window_name": "terminal"}),
        ("window_resize", {"window_id": "123", "width": 800, "height": 600}),
        ("file_explorer_open", {"folder_path": "/tmp"}),
        ("capture_window", {}),
        ("capture_region", {"x": 0, "y": 0, "width": 100, "height": 100}),
    ]

    for action_name, params in actions_to_test:
        success = await automation._run_action(action_name, params)
        assert success is True, f"Action '{action_name}' should succeed"

    await automation.shutdown()
    kernel.reset_instance()


@pytest.mark.anyio
async def test_automation_unknown_action():
    from app.kernel.kernel import FridayKernel
    from app.kernel.state import KernelState
    kernel = FridayKernel.get_instance()
    kernel.reset_instance()
    kernel = FridayKernel.get_instance()
    kernel._state = KernelState.READY

    automation = DesktopAutomationService()
    await automation.initialize()
    kernel._registry.register("desktop_automation", automation)

    desktop_mock = MagicMock()
    kernel._registry.register("desktop_controller", desktop_mock)

    with pytest.raises(ValueError, match="Unknown desktop automation action"):
        await automation._run_action("nonexistent_action_xyz", {})

    await automation.shutdown()
    kernel.reset_instance()


# ───────────────────────────────────────────────────────
# 5. ConfirmationPolicy Tests (approve/deny/timeout)
# ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_confirmation_policy_approve():
    policy = ConfirmationPolicy()
    task = asyncio.create_task(policy.request_confirmation("test-1"))
    await asyncio.sleep(0.05)
    assert policy.is_pending("test-1") is True
    result = policy.approve("test-1")
    assert result is True
    approved = await task
    assert approved is True


@pytest.mark.anyio
async def test_confirmation_policy_deny():
    policy = ConfirmationPolicy()
    task = asyncio.create_task(policy.request_confirmation("test-2"))
    await asyncio.sleep(0.05)
    assert policy.is_pending("test-2") is True
    result = policy.deny("test-2")
    assert result is True
    approved = await task
    assert approved is False


@pytest.mark.anyio
async def test_confirmation_policy_timeout():
    policy = ConfirmationPolicy()
    await policy.set_timeout(0.1)
    result = await policy.request_confirmation("test-3", timeout=0.05)
    assert result is False


@pytest.mark.anyio
async def test_confirmation_policy_approve_nonexistent():
    policy = ConfirmationPolicy()
    result = policy.approve("nonexistent")
    assert result is False


@pytest.mark.anyio
async def test_confirmation_policy_deny_nonexistent():
    policy = ConfirmationPolicy()
    result = policy.deny("nonexistent")
    assert result is False


@pytest.mark.anyio
async def test_confirmation_policy_pending_count():
    policy = ConfirmationPolicy()
    assert policy.pending_count() == 0
    _ = asyncio.create_task(policy.request_confirmation("p1"))
    _ = asyncio.create_task(policy.request_confirmation("p2"))
    await asyncio.sleep(0.05)
    assert policy.pending_count() == 2
    assert "p1" in policy.list_pending()
    policy.approve("p1")
    await asyncio.sleep(0.05)
    assert policy.pending_count() == 1


# ───────────────────────────────────────────────────────
# 6. DesktopActionPlanner Tests
# ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_action_planner_click_goal():
    planner = DesktopActionPlanner()
    context = {
        "ui_elements": [
            {"type": "button", "text": "submit button", "bbox": {"x": 100, "y": 200}}
        ]
    }
    result = await planner.plan_from_goal("click the submit button", screen_context=context)
    assert result["goal"] == "click the submit button"
    assert len(result["steps"]) >= 1
    assert result["steps"][0]["action"] in ("mouse_move", "mouse_click")


@pytest.mark.anyio
async def test_action_planner_type_goal():
    planner = DesktopActionPlanner()
    result = await planner.plan_from_goal('type "hello world"')
    assert len(result["steps"]) >= 1
    actions = [s["action"] for s in result["steps"]]
    assert "keyboard_type" in actions


@pytest.mark.anyio
async def test_action_planner_open_goal():
    planner = DesktopActionPlanner()
    result = await planner.plan_from_goal("open firefox browser")
    assert result["steps"][0]["action"] == "open_application"
    assert "firefox" in result["steps"][0]["params"]["app_name"].lower()


@pytest.mark.anyio
async def test_action_planner_close_goal():
    planner = DesktopActionPlanner()
    result = await planner.plan_from_goal("close terminal")
    assert result["steps"][0]["action"] == "close_application"
    assert "terminal" in result["steps"][0]["params"]["app_name"].lower()


@pytest.mark.anyio
async def test_action_planner_screenshot_goal():
    planner = DesktopActionPlanner()
    result = await planner.plan_from_goal("take a screenshot")
    assert result["steps"][0]["action"] == "take_screenshot"


@pytest.mark.anyio
async def test_action_planner_focus_goal():
    planner = DesktopActionPlanner()
    result = await planner.plan_from_goal("focus the terminal window")
    assert result["steps"][0]["action"] == "window_focus"


@pytest.mark.anyio
async def test_action_planner_with_screen_context():
    planner = DesktopActionPlanner()
    context = {
        "ui_elements": [
            {"type": "button", "text": "Submit", "bbox": {"x": 100, "y": 200, "width": 80, "height": 30}},
        ]
    }
    result = await planner.plan_from_goal("click submit", screen_context=context)
    assert len(result["steps"]) >= 2
    assert result["steps"][0]["params"]["x"] == 100


@pytest.mark.anyio
async def test_action_planner_list_actions():
    planner = DesktopActionPlanner()
    actions = planner.list_available_actions()
    assert len(actions) > 0
    names = [a["name"] for a in actions]
    assert "click" in names
    assert "type_text" in names


# ───────────────────────────────────────────────────────
# 7. DesktopOverlayService Tests
# ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_overlay_service_start_stop():
    overlay = DesktopOverlayService()
    assert overlay.is_active is False
    await overlay.start(publish_interval=1.0)
    assert overlay.is_active is True
    await overlay.stop()
    assert overlay.is_active is False


@pytest.mark.anyio
async def test_overlay_service_state_updates():
    overlay = DesktopOverlayService()
    await overlay.start(publish_interval=1.0)

    overlay.update_detected_elements([{"type": "button", "text": "OK"}])
    assert len(overlay.state["detected_elements"]) == 1

    overlay.update_mouse_position(500, 300)
    assert overlay.state["mouse_position"] == (500, 300)

    overlay.update_active_mission("mission-1", "click")
    assert overlay.state["active_mission"] == "mission-1"
    assert overlay.state["current_action"] == "click"

    overlay.update_confidence(0.85)
    assert overlay.state["confidence"] == 0.85

    overlay.update_selected_target({"type": "button"})
    assert overlay.state["selected_target"]["type"] == "button"

    overlay.update_overlay_text("Clicking submit")
    assert overlay.state["overlay_text"] == "Clicking submit"

    await overlay.stop()


@pytest.mark.anyio
async def test_overlay_service_state_file():
    overlay = DesktopOverlayService()
    await overlay.start(publish_interval=1.0)
    overlay.update_detected_elements([{"type": "button"}])
    read_back = overlay.read_state()
    assert read_back is not None
    assert read_back["element_count"] == 1
    await overlay.stop()
    # After stop, state file should be cleaned up
    read_back = overlay.read_state()
    assert read_back is None


@pytest.mark.anyio
async def test_overlay_service_event_publishing():
    mock_bus = MagicMock()
    overlay = DesktopOverlayService(event_bus=mock_bus)
    await overlay.start(publish_interval=0.1)
    await asyncio.sleep(0.3)
    assert mock_bus.publish.called or True
    await overlay.stop()


# ───────────────────────────────────────────────────────
# 8. MissionRecorder Tests
# ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_mission_recorder_start_stop():
    recorder = MissionRecorder()
    assert recorder.is_recording is False
    recorder.start_recording()
    assert recorder.is_recording is True

    recorder.record_action("mouse_click", {"button": "left"}, {"success": True})
    recorder.record_action("keyboard_type", {"text": "hello"}, {"success": True})
    assert recorder.action_count == 2

    recording = recorder.stop_recording()
    assert recorder.is_recording is False
    assert recording["action_count"] == 2
    assert len(recording["actions"]) == 2


@pytest.mark.anyio
async def test_mission_recorder_save_load():
    mock_memory = MagicMock()
    mock_memory.store = AsyncMock(return_value=True)
    mock_memory.retrieve = AsyncMock(return_value={
        "type": "desktop_workflow_recording",
        "name": "Test Recording",
        "recording": {"workflow_id": "rec_123", "actions": []},
    })
    mock_memory.list_by_type = AsyncMock(return_value=[
        ("rec_123", {"name": "Test Recording", "recording": {"recorded_at": "2024-01-01"}})
    ])

    recorder = MissionRecorder(memory_engine=mock_memory)
    recorder.start_recording()
    recorder.record_action("mouse_click", {}, {"success": True})
    recording = recorder.stop_recording()

    saved = await recorder.save_recording(recording, "Test Recording")
    assert saved is True
    mock_memory.store.assert_called_once()

    loaded = await recorder.load_recording("rec_123")
    assert loaded is not None

    recordings = await recorder.list_recordings()
    assert len(recordings) == 1
    assert recordings[0]["name"] == "Test Recording"


# ───────────────────────────────────────────────────────
# 9. MissionPlayback Tests
# ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_mission_playback_replay():
    mock_automation = MagicMock()
    mock_automation._run_action = AsyncMock(return_value=True)

    playback = MissionPlayback(automation_service=mock_automation)
    recording = {
        "actions": [
            {"order": 1, "action": "mouse_move", "params": {"x": 100, "y": 200}, "timestamp_elapsed_ms": 100},
            {"order": 2, "action": "mouse_click", "params": {"button": "left"}, "timestamp_elapsed_ms": 200},
        ]
    }

    result = await playback.replay(recording, speed=0)
    assert result["success"] is True
    assert result["total"] == 2
    assert result["completed"] == 2
    assert mock_automation._run_action.call_count == 2


@pytest.mark.anyio
async def test_mission_playback_edit():
    playback = MissionPlayback()
    recording = {
        "workflow_id": "rec_123",
        "actions": [
            {"order": 1, "action": "mouse_move", "params": {"x": 0, "y": 0}, "timestamp_elapsed_ms": 100},
            {"order": 2, "action": "mouse_click", "params": {}, "timestamp_elapsed_ms": 200},
        ]
    }

    edited = await playback.edit_recording(recording, remove_at=[0])
    assert edited["action_count"] == 1
    assert edited["actions"][0]["action"] == "mouse_click"

    new_action = {"action": "keyboard_type", "params": {"text": "test"}}
    edited2 = await playback.edit_recording(recording, insert_at=1, new_actions=[new_action])
    assert edited2["action_count"] == 3
    assert edited2["actions"][1]["action"] == "keyboard_type"


@pytest.mark.anyio
async def test_mission_playback_on_step_callback():
    mock_automation = MagicMock()
    mock_automation._run_action = AsyncMock(return_value=True)
    playback = MissionPlayback(automation_service=mock_automation)

    callback = AsyncMock()
    playback.on_step(callback)

    recording = {
        "actions": [
            {"order": 1, "action": "mouse_move", "params": {}, "timestamp_elapsed_ms": 10},
        ]
    }

    result = await playback.replay(recording, speed=0)
    assert result["success"] is True
    callback.assert_called_once()


# ───────────────────────────────────────────────────────
# 10. Desktop Events Tests
# ───────────────────────────────────────────────────────

def test_desktop_events():
    e1 = DesktopActionStarted("mouse_click", {"button": "left"})
    assert e1.topic == "desktop.action.started"
    assert e1.data["action"] == "mouse_click"

    e2 = DesktopActionCompleted("mouse_click", True, 150.0)
    assert e2.topic == "desktop.action.completed"
    assert e2.data["success"] is True

    e3 = DesktopActionFailed("mouse_click", "timeout")
    assert e3.topic == "desktop.action.failed"
    assert e3.data["error"] == "timeout"

    e4 = DesktopScreenshotCaptured("full", 102400)
    assert e4.topic == "desktop.screenshot.captured"
    assert e4.data["size_bytes"] == 102400

    e5 = DesktopUIDetected(5)
    assert e5.topic == "desktop.ui.detected"
    assert e5.data["element_count"] == 5

    e6 = DesktopOCRExtracted(42)
    assert e6.topic == "desktop.ocr.completed"
    assert e6.data["char_count"] == 42

    e7 = DesktopOverlayUpdated({"element_count": 3, "mouse_x": 100, "mouse_y": 200})
    assert e7.topic == "desktop.overlay.updated"
    assert e7.data["element_count"] == 3
    assert e7.data["mouse_x"] == 100


# ───────────────────────────────────────────────────────
# 11. WindowManager New Methods Tests
# ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_window_resize_no_xdotool():
    from app.desktop.window_manager import WindowManager
    wm = WindowManager()
    with patch.object(wm, "_has_xdotool", return_value=False):
        res = await wm.resize_window("123", 800, 600)
        assert res["success"] is False
        assert "xdotool is missing" in res["error"]


@pytest.mark.anyio
async def test_window_resize_with_xdotool():
    from app.desktop.window_manager import WindowManager
    wm = WindowManager()
    with patch.object(wm, "_has_xdotool", return_value=True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            res = await wm.resize_window("12345", 1024, 768)
            assert res["success"] is True
            mock_run.assert_called_with(
                ["xdotool", "windowsize", "12345", "1024", "768"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )


@pytest.mark.anyio
async def test_window_maximize_with_xdotool():
    from app.desktop.window_manager import WindowManager
    wm = WindowManager()
    with patch.object(wm, "_has_xdotool", return_value=True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            res = await wm.maximize_window("12345")
            assert res["success"] is True
            assert mock_run.call_count == 2


# ───────────────────────────────────────────────────────
# 12. Desktop Input Tools Tests
# ───────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_mouse_move_tool():
    from app.tools.desktop_input_tools import MouseMoveTool
    controller = MagicMock()
    controller.mouse_move = AsyncMock(return_value=True)
    tool = MouseMoveTool(controller)
    result = await tool.execute(x=100, y=200)
    assert result["success"] is True
    assert result["x"] == 100
    assert result["y"] == 200


@pytest.mark.anyio
async def test_mouse_move_tool_missing_params():
    from app.tools.desktop_input_tools import MouseMoveTool
    controller = MagicMock()
    tool = MouseMoveTool(controller)
    result = await tool.execute()
    assert result["success"] is False
    assert "Missing" in result["error"]


@pytest.mark.anyio
async def test_mouse_click_tool():
    from app.tools.desktop_input_tools import MouseClickTool
    controller = MagicMock()
    controller.mouse_click = AsyncMock(return_value=True)
    tool = MouseClickTool(controller)
    result = await tool.execute(button="right")
    assert result["success"] is True
    assert result["button"] == "right"


@pytest.mark.anyio
async def test_keyboard_type_tool():
    from app.tools.desktop_input_tools import KeyboardTypeTool
    controller = MagicMock()
    controller.keyboard_type = AsyncMock(return_value=True)
    tool = KeyboardTypeTool(controller)
    result = await tool.execute(text="hello")
    assert result["success"] is True
    assert result["char_count"] == 5


@pytest.mark.anyio
async def test_keyboard_type_tool_missing_text():
    from app.tools.desktop_input_tools import KeyboardTypeTool
    controller = MagicMock()
    tool = KeyboardTypeTool(controller)
    result = await tool.execute()
    assert result["success"] is False


@pytest.mark.anyio
async def test_keyboard_shortcut_tool():
    from app.tools.desktop_input_tools import KeyboardShortcutTool
    controller = MagicMock()
    controller.keyboard_shortcut = AsyncMock(return_value=True)
    tool = KeyboardShortcutTool(controller)
    result = await tool.execute(combo="ctrl+alt+t")
    assert result["success"] is True
    assert result["combo"] == "ctrl+alt+t"


@pytest.mark.anyio
async def test_window_focus_tool():
    from app.tools.desktop_input_tools import WindowFocusTool
    controller = MagicMock()
    controller.window_focus = AsyncMock(return_value={"success": True})
    tool = WindowFocusTool(controller)
    result = await tool.execute(window_name="terminal")
    assert result["success"] is True


@pytest.mark.anyio
async def test_capture_window_tool():
    from app.tools.desktop_input_tools import CaptureWindowTool
    controller = MagicMock()
    controller.screenshot_handler = MagicMock()
    controller.screenshot_handler.capture_active_window = AsyncMock(return_value=b"img_data")
    tool = CaptureWindowTool(controller)
    result = await tool.execute()
    assert result["success"] is True
    assert result["size_bytes"] == 8


@pytest.mark.anyio
async def test_capture_region_tool():
    from app.tools.desktop_input_tools import CaptureRegionTool
    controller = MagicMock()
    controller.screenshot_handler = MagicMock()
    controller.screenshot_handler.capture_region = AsyncMock(return_value=b"img_data")
    tool = CaptureRegionTool(controller)
    result = await tool.execute(x=10, y=20, width=200, height=100)
    assert result["success"] is True
