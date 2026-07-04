import json
import time
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
from loguru import logger


class MissionRecorder:
    def __init__(self, automation_service: Any = None, memory_engine: Any = None) -> None:
        self._automation = automation_service
        self._memory = memory_engine
        self._recording: bool = False
        self._actions: List[Dict[str, Any]] = []
        self._start_time: Optional[float] = None

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def action_count(self) -> int:
        return len(self._actions)

    def start_recording(self) -> None:
        if self._recording:
            logger.warning("Already recording")
            return
        self._recording = True
        self._actions = []
        self._start_time = time.time()
        logger.info("Mission recording started")

    def record_action(self, action: str, params: Dict[str, Any], result: Dict[str, Any]) -> None:
        if not self._recording:
            return
        elapsed = time.time() - (self._start_time or time.time())
        self._actions.append({
            "order": len(self._actions) + 1,
            "action": action,
            "params": dict(params),
            "result": result,
            "timestamp_elapsed_ms": round(elapsed * 1000, 1),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })

    def stop_recording(self) -> Dict[str, Any]:
        if not self._recording:
            return {"success": False, "error": "Not recording"}
        self._recording = False
        duration = time.time() - (self._start_time or time.time())
        recording = {
            "workflow_id": f"rec_{int(time.time())}",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "duration_sec": round(duration, 2),
            "action_count": len(self._actions),
            "actions": list(self._actions),
        }
        logger.info(f"Recording stopped: {recording['action_count']} actions over {recording['duration_sec']}s")
        return recording

    async def save_recording(self, recording: Dict[str, Any], name: str = "") -> bool:
        if not self._memory:
            logger.warning("No memory engine available to save recording")
            return False
        try:
            record_id = recording.get("workflow_id", f"rec_{int(time.time())}")
            metadata = {
                "type": "desktop_workflow_recording",
                "name": name or f"Recording {record_id}",
                "recording": recording,
            }
            await self._memory.store(record_id, metadata)
            logger.info(f"Recording saved as '{metadata['name']}' ({record_id})")
            return True
        except Exception as e:
            logger.error(f"Failed to save recording: {e}")
            return False

    async def load_recording(self, record_id: str) -> Optional[Dict[str, Any]]:
        if not self._memory:
            logger.warning("No memory engine available to load recording")
            return None
        try:
            data = await self._memory.retrieve(record_id)
            if data:
                return data.get("recording")
        except Exception as e:
            logger.error(f"Failed to load recording {record_id}: {e}")
        return None

    async def list_recordings(self) -> List[Dict[str, Any]]:
        if not self._memory:
            return []
        try:
            items = await self._memory.list_by_type("desktop_workflow_recording")
            return [
                {"id": k, "name": v.get("name", ""), "recorded_at": v.get("recording", {}).get("recorded_at", "")}
                for k, v in items
            ]
        except Exception as e:
            logger.error(f"Failed to list recordings: {e}")
            return []


class MissionPlayback:
    def __init__(self, automation_service: Any = None) -> None:
        self._automation = automation_service
        self._on_step: Optional[Callable] = None

    def on_step(self, callback: Callable) -> None:
        self._on_step = callback

    async def replay(self, recording: Dict[str, Any], speed: float = 1.0) -> Dict[str, Any]:
        actions = recording.get("actions", [])
        total = len(actions)
        completed = 0
        failed = 0

        logger.info(f"Replaying {total} actions at {speed}x speed")

        for step in actions:
            action = step.get("action", "")
            params = step.get("params", {})
            delay_ms = step.get("timestamp_elapsed_ms", 500)

            if self._on_step:
                await self._on_step(step, completed + 1, total)

            delay = (delay_ms / 1000.0) / speed if speed > 0 else 0.1
            if delay > 0:
                await asyncio.sleep(delay)

            try:
                if self._automation:
                    success = await self._automation._run_action(action, params)
                    if success:
                        completed += 1
                    else:
                        failed += 1
                        logger.warning(f"Replay step {step['order']} failed: {action}")
            except Exception as e:
                failed += 1
                logger.error(f"Replay step {step['order']} error: {e}")

        return {
            "success": failed == 0,
            "total": total,
            "completed": completed,
            "failed": failed,
        }

    async def edit_recording(
        self, recording: Dict[str, Any],
        insert_at: Optional[int] = None,
        remove_at: Optional[List[int]] = None,
        new_actions: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        edited = dict(recording)
        actions = list(recording.get("actions", []))

        if remove_at:
            for idx in sorted(remove_at, reverse=True):
                if 0 <= idx < len(actions):
                    actions.pop(idx)

        if new_actions and insert_at is not None:
            for i, new_action in enumerate(new_actions):
                new_action["order"] = insert_at + i + 1
            actions[insert_at:insert_at] = new_actions

        for i, action in enumerate(actions):
            action["order"] = i + 1

        edited["actions"] = actions
        edited["action_count"] = len(actions)
        edited["edited_at"] = datetime.now(timezone.utc).isoformat()
        return edited
