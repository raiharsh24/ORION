import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

from app.missions.mission import Mission, MissionStatus, MissionPriority, MissionType
from app.missions.mission_manager import (
    MissionManager, CreateMissionRequest, MissionTelemetry, BUILTIN_MISSIONS
)
from app.missions.mission_history import MissionHistory
from app.events.bus import EventBus
from app.events.events import OrionEvent

@pytest.mark.anyio
async def test_mission_data_model():
    mission = Mission(
        id="test-id",
        name="Test Mission",
        description="Verify model properties",
        priority=MissionPriority.HIGH,
        type=MissionType.SYSTEM,
        metadata={"key": "val"}
    )
    assert mission.id == "test-id"
    assert mission.name == "Test Mission"
    assert mission.description == "Verify model properties"
    assert mission.status == MissionStatus.CREATED
    assert mission.priority == MissionPriority.HIGH
    assert mission.type == MissionType.SYSTEM
    assert mission.metadata == {"key": "val"}
    assert isinstance(mission.created_at, datetime)
    assert isinstance(mission.updated_at, datetime)
    assert mission.workflow_id is None
    assert mission.current_step is None
    assert mission.progress == 0.0


@pytest.mark.anyio
async def test_mission_history_in_memory():
    history = MissionHistory()
    mission1 = Mission("id-1", "m1", "desc1")
    mission2 = Mission("id-2", "m2", "desc2")
    
    # Save
    assert await history.save(mission1) is True
    assert await history.save(mission2) is True
    
    # Load
    loaded = await history.load("id-1")
    assert loaded is not None
    assert loaded.name == "m1"
    
    # List history
    all_history = await history.list_history()
    assert len(all_history) == 2
    assert all_history[0].id == "id-1" or all_history[0].id == "id-2"
    
    # Delete
    assert await history.delete("id-1") is True
    assert await history.delete("id-1") is False  # Already deleted
    
    assert await history.load("id-1") is None
    assert len(await history.list_history()) == 1
    
    # Clear
    await history.clear()
    assert len(await history.list_history()) == 0


@pytest.mark.anyio
async def test_mission_manager_lifecycle():
    event_bus = EventBus()
    telemetry = MissionTelemetry()
    history = MissionHistory()
    
    # Event list to capture published events
    received_events = []
    
    async def mock_publish(event: OrionEvent):
        received_events.append(event)
    
    event_bus.publish = mock_publish  # Mock publish to record events
    
    manager = MissionManager(
        event_bus=event_bus,
        telemetry=telemetry,
        history=history
    )
    
    # Create request
    req = CreateMissionRequest(
        name="Startup Services",
        description="Verify dev startup workflow compilation",
        priority="HIGH",
        type="DEVELOPMENT",
        metadata={"env": "local"}
    )
    
    # 1. Create Mission
    response = await manager.create_mission(req)
    mission_id = response.id
    assert response.name == "Startup Services"
    assert response.status == "CREATED"
    assert response.priority == "HIGH"
    assert response.type == "DEVELOPMENT"
    
    # Assert created event
    assert len(received_events) == 1
    assert received_events[0].topic == "MissionCreated"
    assert received_events[0].data["mission_id"] == mission_id
    
    # Assert listed
    listed = await manager.list_missions()
    assert len(listed) == 1
    assert listed[0].id == mission_id
    
    # 2. Queue Mission
    queued = await manager.queue_mission(mission_id)
    assert queued is True
    
    mission_res = await manager.get_mission(mission_id)
    assert mission_res.status == "QUEUED"
    assert len(received_events) == 2
    assert received_events[1].topic == "MissionQueued"
    
    # 3. Start Mission
    started = await manager.start_mission(mission_id)
    assert started is True
    
    mission_res = await manager.get_mission(mission_id)
    assert mission_res.status == "RUNNING"
    assert len(received_events) == 3
    assert received_events[2].topic == "MissionStarted"
    
    # 4. Pause Mission
    paused = await manager.pause_mission(mission_id)
    assert paused is True
    
    mission_res = await manager.get_mission(mission_id)
    assert mission_res.status == "PAUSED"
    assert len(received_events) == 4
    assert received_events[3].topic == "MissionPaused"
    
    # 5. Resume Mission
    resumed = await manager.resume_mission(mission_id)
    assert resumed is True
    
    mission_res = await manager.get_mission(mission_id)
    assert mission_res.status == "RUNNING"
    assert len(received_events) == 5
    assert received_events[4].topic == "MissionStarted"  # Starts run again
    
    # 6. Complete Mission
    completed = await manager.complete_mission(mission_id)
    assert completed is True
    
    mission_res = await manager.get_mission(mission_id)
    assert mission_res.status == "COMPLETED"
    assert mission_res.progress == 1.0
    assert len(received_events) == 6
    assert received_events[5].topic == "MissionCompleted"
    
    # Verify telemetry recorded
    assert len(telemetry.records) == 1
    assert telemetry.records[0]["mission_id"] == mission_id
    assert telemetry.records[0]["status"] == "COMPLETED"
    assert telemetry.records[0]["duration"] >= 0.0


@pytest.mark.anyio
async def test_invalid_transitions():
    manager = MissionManager()
    req = CreateMissionRequest(
        name="Invalid transitions test",
        description="Fails transitions checks",
        priority="NORMAL",
        type="SYSTEM"
    )
    res = await manager.create_mission(req)
    mission_id = res.id
    
    # Try starting directly from CREATED (should fail transition CREATED -> RUNNING)
    with pytest.raises(ValueError) as excinfo:
        await manager.start_mission(mission_id)
    assert "Invalid state transition" in str(excinfo.value)
    
    # Queue the mission (CREATED -> QUEUED is valid)
    assert await manager.queue_mission(mission_id) is True
    
    # Start the mission (QUEUED -> RUNNING is valid)
    assert await manager.start_mission(mission_id) is True
    
    # Complete the mission (RUNNING -> COMPLETED is valid)
    assert await manager.complete_mission(mission_id) is True
    
    # Try transitioning completed mission to running (COMPLETED -> RUNNING is invalid)
    with pytest.raises(ValueError) as excinfo:
        await manager.start_mission(mission_id)
    assert "Invalid state transition" in str(excinfo.value)


@pytest.mark.anyio
async def test_cancel_and_fail_flows():
    manager = MissionManager()
    
    # Test Cancel from Queued
    res1 = await manager.create_mission(CreateMissionRequest(name="Cancel test", description="Crashes queued"))
    m1_id = res1.id
    assert await manager.queue_mission(m1_id) is True
    assert await manager.cancel_mission(m1_id) is True
    m1_res = await manager.get_mission(m1_id)
    assert m1_res.status == "CANCELLED"
    
    # Test Fail from Running
    res2 = await manager.create_mission(CreateMissionRequest(name="Fail test", description="Crashes running"))
    m2_id = res2.id
    assert await manager.queue_mission(m2_id) is True
    assert await manager.start_mission(m2_id) is True
    assert await manager.fail_mission(m2_id, "Resource lock failed") is True
    m2_res = await manager.get_mission(m2_id)
    assert m2_res.status == "FAILED"
    assert m2_res.metadata["error"] == "Resource lock failed"


@pytest.mark.anyio
async def test_registry_builtins():
    manager = MissionManager()
    builtins = manager.get_registered_builtins()
    assert "dev_startup" in builtins
    assert "build_project" in builtins
    assert "health_check" in builtins
    assert builtins["health_check"]["name"] == "Health Check"
    assert builtins["dev_startup"]["type"] == MissionType.DEVELOPMENT
