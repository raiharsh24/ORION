import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

from app.missions.mission import Mission, MissionStatus, MissionPriority, MissionType
from app.missions.mission_manager import MissionManager
from app.desktop.automation import DesktopAutomationService
from app.kernel.kernel import FridayKernel
from app.kernel.state import KernelState

@pytest.mark.anyio
async def test_desktop_automation_queue_lifecycle():
    # Setup services
    kernel = FridayKernel.get_instance()
    kernel.reset_instance()
    kernel = FridayKernel.get_instance()
    kernel._state = KernelState.READY
    
    automation = DesktopAutomationService()
    await automation.initialize()
    kernel._registry.register("desktop_automation", automation)
    
    # Mock desktop controller and mission engine
    desktop_mock = MagicMock()
    desktop_mock.open_application = AsyncMock(return_value={"success": True, "pid": 1234})
    desktop_mock.show_notification = AsyncMock(return_value=True)
    kernel._registry.register("desktop_controller", desktop_mock)
    
    manager = MissionManager()
    kernel._registry.register("mission_engine", manager)
    
    # Create an automation mission
    mission = Mission(
        id="auto-test",
        name="Automation Test",
        description="Verify desktop actions execution",
        priority=MissionPriority.NORMAL,
        type=MissionType.AUTOMATION,
        metadata={
            "actions": [
                {"action": "show_notification", "message": "Test notification", "title": "Test"},
                {"action": "open_application", "app_name": "xterm"}
            ]
        }
    )
    manager._active_missions["auto-test"] = mission
    
    # Queue mission
    await manager.queue_mission("auto-test")
    
    # Start mission -> adds to queue
    await manager.start_mission("auto-test")
    assert "auto-test" in automation._queue
    
    # Wait for execution to reach sensitive open_application confirmation
    for _ in range(30):
        if "pending_confirmation" in mission.metadata:
            break
        await asyncio.sleep(0.1)
        
    assert "pending_confirmation" in mission.metadata
    assert mission.metadata["pending_confirmation"]["action"] == "open_application"
    
    # Confirm sensitive action
    automation.confirm_action("auto-test", True)
    
    # Wait for completion
    for _ in range(30):
        if mission.status == MissionStatus.COMPLETED:
            break
        await asyncio.sleep(0.1)
        
    assert mission.status == MissionStatus.COMPLETED
    assert mission.progress in [1.0, 100.0]
    
    # Teardown
    await automation.shutdown()
    kernel.reset_instance()


@pytest.mark.anyio
async def test_desktop_automation_double_initialize():
    automation = DesktopAutomationService()
    await automation.initialize()
    task1 = automation._loop_task
    assert task1 is not None
    assert not task1.done()
    
    # Call initialize again
    await automation.initialize()
    task2 = automation._loop_task
    # Verify it returns the same task and doesn't create a new one
    assert task1 is task2
    
    # Teardown
    await automation.shutdown()
    assert task1.cancelled()

