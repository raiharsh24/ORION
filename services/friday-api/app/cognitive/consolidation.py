import asyncio
import time
from typing import Dict, Any, Optional
from loguru import logger

from app.cognitive.goal_memory import GoalMemory


class CognitiveConsolidation:
    def __init__(self, goal_memory: GoalMemory,
                 interval_seconds: int = 3600) -> None:
        self._goal_memory = goal_memory
        self._interval = interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.total_runs = 0

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            f"CognitiveConsolidation started (interval={self._interval}s)"
        )

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("CognitiveConsolidation stopped")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self.run_consolidation()
            except Exception as e:
                logger.error(f"CognitiveConsolidation run failed: {e}")
            await asyncio.sleep(self._interval)

    async def run_consolidation(self) -> Dict[str, Any]:
        self.total_runs += 1
        start = time.time()
        stats: Dict[str, Any] = {"goals_saved": 0}

        if self._goal_memory:
            self._goal_memory.save()
            stats["goals_saved"] = len(self._goal_memory._goals) if hasattr(self._goal_memory, '_goals') else 0

        elapsed = (time.time() - start) * 1000
        stats["duration_ms"] = round(elapsed, 2)
        logger.info(f"CognitiveConsolidation completed: {stats}")
        return stats

    def health(self) -> Dict[str, Any]:
        return {
            "status": "HEALTHY" if self._running else "STOPPED",
            "total_runs": self.total_runs,
        }
