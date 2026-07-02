from typing import Dict, Any, Optional
from datetime import datetime, timezone


class AgentContext:
    def __init__(self):
        self._data: Dict[str, Dict[str, Any]] = {}
        self._shared: Dict[str, Any] = {}
        self._history: Dict[str, list] = {}

    def set(self, agent_id: str, key: str, value: Any) -> None:
        if agent_id not in self._data:
            self._data[agent_id] = {}
        self._data[agent_id][key] = value

    def get(self, agent_id: str, key: str, default: Any = None) -> Any:
        return self._data.get(agent_id, {}).get(key, default)

    def get_all(self, agent_id: str) -> Dict[str, Any]:
        return dict(self._data.get(agent_id, {}))

    def clear_agent(self, agent_id: str) -> None:
        self._data.pop(agent_id, None)

    def set_shared(self, key: str, value: Any) -> None:
        self._shared[key] = value

    def get_shared(self, key: str, default: Any = None) -> Any:
        return self._shared.get(key, default)

    def add_to_history(self, agent_id: str, entry: Any) -> None:
        if agent_id not in self._history:
            self._history[agent_id] = []
        self._history[agent_id].append({
            "entry": entry,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_history(self, agent_id: str, limit: int = 50) -> list:
        return list(self._history.get(agent_id, [])[-limit:])

    def transfer(self, from_agent: str, to_agent: str, keys: list[str]) -> int:
        count = 0
        src = self._data.get(from_agent, {})
        if to_agent not in self._data:
            self._data[to_agent] = {}
        for key in keys:
            if key in src:
                self._data[to_agent][key] = src[key]
                count += 1
        return count

    def health(self) -> dict:
        return {
            "agents_with_context": len(self._data),
            "shared_keys": len(self._shared),
            "agents_with_history": len(self._history),
            "total_entries": sum(len(v) for v in self._history.values()),
        }
