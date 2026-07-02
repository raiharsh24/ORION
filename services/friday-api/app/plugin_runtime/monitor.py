import time
from typing import Dict, Optional, Any, List
from datetime import datetime, timezone
from dataclasses import dataclass, field
from collections import defaultdict
from loguru import logger

from app.plugin_runtime.base import PluginInstance, ExecutionStats, PluginRuntimeState
from app.plugin_runtime.health import PluginRuntimeHealth


@dataclass
class CrashRecord:
    plugin_id: str
    plugin_name: str
    error: str
    timestamp: datetime
    stage: str = ""


class PluginMonitor:
    def __init__(self) -> None:
        self._start_time: float = time.time()
        self._execution_log: Dict[str, ExecutionStats] = defaultdict(ExecutionStats)
        self._crash_history: List[CrashRecord] = []
        self._load_times: Dict[str, List[float]] = defaultdict(list)
        self._sandbox_violations: Dict[str, int] = defaultdict(int)
        self._peak_plugins: int = 0
        self._resource_warnings: List[Dict[str, Any]] = []

    def record_load(self, plugin_id: str, load_time_ms: float) -> None:
        self._load_times[plugin_id].append(load_time_ms)

    def record_execution(self, plugin_id: str, duration_ms: float,
                         success: bool) -> None:
        stats = self._execution_log[plugin_id]
        stats.total_executions += 1
        stats.total_execution_time_ms += duration_ms
        stats.last_execution_time = datetime.now(timezone.utc)
        if success:
            stats.successful_executions += 1
        else:
            stats.failed_executions += 1
        stats.average_execution_time_ms = (
            stats.total_execution_time_ms / stats.total_executions
        )

    def record_crash(self, plugin_id: str, plugin_name: str,
                      error: str, stage: str = "") -> None:
        record = CrashRecord(
            plugin_id=plugin_id,
            plugin_name=plugin_name,
            error=error,
            timestamp=datetime.now(timezone.utc),
            stage=stage,
        )
        self._crash_history.append(record)
        logger.error(f"Plugin '{plugin_name}' crashed at stage '{stage}': {error}")

    def record_sandbox_violation(self, plugin_id: str) -> None:
        self._sandbox_violations[plugin_id] += 1

    def record_resource_warning(self, plugin_id: str, resource: str,
                                 usage: float, limit: float) -> None:
        self._resource_warnings.append({
            "plugin_id": plugin_id,
            "resource": resource,
            "usage": usage,
            "limit": limit,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def set_peak_plugins(self, count: int) -> None:
        self._peak_plugins = max(self._peak_plugins, count)

    def get_execution_stats(self, plugin_id: Optional[str] = None) -> Any:
        if plugin_id:
            return self._execution_log.get(plugin_id, ExecutionStats())
        return dict(self._execution_log)

    def get_crash_history(self, plugin_id: Optional[str] = None,
                          limit: int = 50) -> List[CrashRecord]:
        if plugin_id:
            return [c for c in self._crash_history
                    if c.plugin_id == plugin_id][:limit]
        return self._crash_history[:limit]

    def get_average_load_time(self) -> float:
        all_times = []
        for times in self._load_times.values():
            all_times.extend(times)
        if not all_times:
            return 0.0
        return sum(all_times) / len(all_times)

    def get_health(self, instances: Dict[str, PluginInstance]) -> PluginRuntimeHealth:
        running = sum(1 for i in instances.values()
                      if i.state == PluginRuntimeState.READY)
        failed = sum(1 for i in instances.values()
                     if i.state == PluginRuntimeState.FAILED)
        suspended = sum(1 for i in instances.values()
                        if i.state == PluginRuntimeState.SUSPENDED)
        total_execs = sum(s.total_executions for s in self._execution_log.values())
        total_success = sum(s.successful_executions for s in self._execution_log.values())
        total_fails = sum(s.failed_executions for s in self._execution_log.values())

        last_crash = None
        if self._crash_history:
            c = self._crash_history[-1]
            last_crash = {
                "plugin_id": c.plugin_id,
                "plugin_name": c.plugin_name,
                "error": c.error,
                "stage": c.stage,
                "timestamp": c.timestamp.isoformat(),
            }

        details = []
        for inst in instances.values():
            stats = self._execution_log.get(inst.plugin_id, ExecutionStats())
            details.append({
                "plugin_id": inst.plugin_id,
                "name": inst.name,
                "state": inst.state.value,
                "reload_count": inst.reload_count,
                "error_count": inst.error_count,
                "executions": stats.total_executions,
                "sandbox_violations": self._sandbox_violations.get(inst.plugin_id, 0),
            })

        total_violations = sum(self._sandbox_violations.values())
        total_reloads = sum(i.reload_count for i in instances.values())
        uptime = time.time() - self._start_time

        overall = "healthy"
        if failed > 0:
            overall = "degraded"
        if len(self._crash_history) > 0 and self._crash_history[-1].timestamp:
            recent_secs = (datetime.now(timezone.utc) - self._crash_history[-1].timestamp).total_seconds()
            if recent_secs < 60:
                overall = "critical"

        return PluginRuntimeHealth(
            overall_status=overall,
            total_plugins=len(instances),
            running_plugins=running,
            failed_plugins=failed,
            suspended_plugins=suspended,
            total_executions=total_execs,
            successful_executions=total_success,
            failed_executions=total_fails,
            total_reloads=total_reloads,
            sandbox_violations=total_violations,
            average_load_time_ms=self.get_average_load_time(),
            peak_plugins=self._peak_plugins,
            uptime_seconds=uptime,
            last_crash=last_crash,
            plugin_details=details,
        )

    def reset(self) -> None:
        self._start_time = time.time()
        self._execution_log.clear()
        self._crash_history.clear()
        self._load_times.clear()
        self._sandbox_violations.clear()
        self._peak_plugins = 0
        self._resource_warnings.clear()
