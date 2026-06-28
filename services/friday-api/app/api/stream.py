import asyncio
import json
import os
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from app.kernel.kernel import FridayKernel
from app.kernel.state import KernelState
from app.events.events import FridayEvent
from app.core.config import settings

router = APIRouter()

def get_process_memory() -> int:
    try:
        with open("/proc/self/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
    except Exception:
        pass
    return 268435456  # 256MB fallback

def get_cpu_utilization() -> float:
    try:
        with open("/proc/self/stat", "r") as f:
            data = f.read()
        parts = data.split()
        if len(parts) < 17:
            return round(0.5, 1)
        utime = int(parts[13])
        stime = int(parts[14])
        cutime = int(parts[15])
        cstime = int(parts[16])
        total_ticks = utime + stime + cutime + cstime
        try:
            clk_tck = os.sysconf(os.sysconf_names.get("SC_CLK_TCK", 3))
        except (AttributeError, KeyError, ValueError, OSError):
            clk_tck = 100
        active_seconds = total_ticks / clk_tck
        uptime = 0.0
        try:
            with open("/proc/uptime", "r") as f:
                uptime = float(f.read().split()[0])
        except Exception:
            pass
        if uptime > 0:
            return round(min(active_seconds / uptime * 100, 100.0), 1)
        return round(min(active_seconds * 100, 100.0), 1)
    except Exception:
        return round(0.5, 1)

async def generate_system_events():
    kernel = FridayKernel.get_instance()
    health_data = kernel.health()
    mission_manager = kernel.get_service("mission_engine")

    active_mission_id = "None"
    current_tool = ""
    workflow = ""
    is_running = False

    if mission_manager:
        from app.api.missions import sync_mission_progress
        await sync_mission_progress(mission_manager)
        active_missions = list(mission_manager._active_missions.values())
        running_missions = [m for m in active_missions if m.status.value == "RUNNING"]
        if running_missions:
            active_mission = running_missions[0]
            active_mission_id = active_mission.id
            current_tool = active_mission.metadata.get("current_tool") or ""
            workflow = active_mission.metadata.get("workflowName") or ""
            is_running = True

    cpu = get_cpu_utilization()
    mem_mb = round(get_process_memory() / 1024 / 1024, 1)

    automation_svc = kernel.get_service("desktop_automation")
    auto_diags = {}
    if automation_svc:
        auto_diags = automation_svc.get_diagnostics()

    # Workflow Engine telemetry
    workflow_svc = kernel.get_service("workflow_engine")
    current_workflow        = ""
    current_workflow_node   = ""
    workflow_duration_secs  = 0.0
    workflow_branch_last    = ""
    workflow_retries        = 0

    if workflow_svc:
        active_wfs = workflow_svc.get_active_workflows()
        if active_wfs:
            aw = active_wfs[0]
            current_workflow       = aw.get("workflow_name", "")
            current_workflow_node  = aw.get("current_node_id", "") or ""
            workflow_duration_secs = aw.get("duration_seconds", 0.0)
            workflow_retries       = aw.get("total_retries", 0)
            bd_list = aw.get("branch_decisions", [])
            if bd_list:
                last_bd = bd_list[-1]
                workflow_branch_last = f"{last_bd.get('node_id','')}→{last_bd.get('next','')}"

    telemetry_payload = {
        "latency": round(0.5, 1),
        "fps": 60,
        "memory": mem_mb,
        "executionTimeMs": round(5.0, 1),
        "eventsCount": 0,
        "currentTool": current_tool,
        "workflow": workflow,
        "missionId": active_mission_id,
        "current_desktop_task": auto_diags.get("current_desktop_task", "None"),
        "last_executed_action": auto_diags.get("last_executed_action", "None"),
        "average_execution_time_ms": auto_diags.get("average_execution_time_ms", 0.0),
        "failure_count": auto_diags.get("failure_count", 0),
        "queue_length": auto_diags.get("queue_length", 0),
        "current_workflow":         current_workflow,
        "current_workflow_node":    current_workflow_node,
        "workflow_duration_seconds": workflow_duration_secs,
        "workflow_branch_decisions": workflow_branch_last,
        "workflow_retries":         workflow_retries,
    }

    kernel_payload = {
        "kernel_state": kernel.state().value,
        "boot_time_ms": 82.0,
        "registered_services_count": len(kernel._registry.list_services()),
        "uptime": "02:45:12",
        "cpu_utilization": cpu,
        "memory_usage_bytes": get_process_memory(),
        "health": {
            "kernel_status": health_data.kernel_status.value,
            "checked_at": health_data.checked_at.isoformat()
        }
    }

    services_list = []
    subsystems = ["planner", "knowledge", "memory", "desktop", "mission", "workflow", "scheduler", "llm", "agents", "workflow_runtime"]
    for sub in subsystems:
        val = getattr(health_data, sub, None)
        if val:
            services_list.append({
                "name": sub.capitalize() if sub not in ("llm", "workflow_runtime") else sub.replace("_", " ").title(),
                "status": val.status.value,
                "message": val.message or "Service operational."
            })

    health_payload = {
        "status": "online",
        "assistant": "FRIDAY",
        "version": settings.APP_VERSION,
        "services": services_list
    }

    return [
        FridayEvent("TelemetryUpdated", telemetry_payload),
        FridayEvent("KernelHealthChanged", kernel_payload),
        FridayEvent("ServiceStatusChanged", health_payload)
    ]

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    kernel = FridayKernel.get_instance()
    event_bus = kernel.get_service("event_bus")

    queue = asyncio.Queue()

    async def handler(event: FridayEvent):
        await queue.put({
            "topic": event.topic,
            "data": event.data,
            "timestamp": event.timestamp
        })

    event_bus.subscribe("*", handler)

    async def event_sender():
        try:
            while True:
                event_data = await queue.get()
                await websocket.send_json(event_data)
        except asyncio.CancelledError:
            pass

    async def ticker_loop():
        try:
            while True:
                events = await generate_system_events()
                for e in events:
                    await event_bus.publish(e)
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    sender_task = asyncio.create_task(event_sender())
    ticker_task = asyncio.create_task(ticker_loop())

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        sender_task.cancel()
        ticker_task.cancel()
        event_bus.unsubscribe("*", handler)

@router.get("/events")
async def sse_endpoint():
    kernel = FridayKernel.get_instance()
    event_bus = kernel.get_service("event_bus")

    queue = asyncio.Queue()

    async def handler(event: FridayEvent):
        await queue.put({
            "topic": event.topic,
            "data": event.data,
            "timestamp": event.timestamp
        })

    event_bus.subscribe("*", handler)

    async def sse_generator():
        async def ticker_loop():
            try:
                while True:
                    events = await generate_system_events()
                    for e in events:
                        await event_bus.publish(e)
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass

        ticker_task = asyncio.create_task(ticker_loop())

        try:
            while True:
                try:
                    event_data = await asyncio.wait_for(queue.get(), timeout=0.5)
                    yield f"event: {event_data['topic']}\ndata: {json.dumps(event_data)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            ticker_task.cancel()
            event_bus.unsubscribe("*", handler)

    return StreamingResponse(sse_generator(), media_type="text/event-stream")
