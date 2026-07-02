from typing import Dict, Set, Optional, List


class MissionStateMachine:
    STATES = [
        "created", "planning", "waiting", "ready",
        "running", "paused", "failed", "recovering",
        "completed", "archived",
    ]

    TRANSITIONS: Dict[str, Set[str]] = {
        "created": {"planning", "failed", "archived"},
        "planning": {"waiting", "ready", "failed", "paused"},
        "waiting": {"ready", "failed", "cancelled"},
        "ready": {"running", "failed", "archived"},
        "running": {"paused", "completed", "failed", "recovering"},
        "paused": {"running", "failed", "archived"},
        "failed": {"recovering", "archived"},
        "recovering": {"running", "failed", "archived"},
        "completed": {"archived"},
        "archived": set(),
    }

    TERMINAL_STATES = {"completed", "archived"}

    def __init__(self, initial_state: str = "created"):
        if initial_state not in self.STATES:
            raise ValueError(f"Invalid initial state: {initial_state}")
        self._current = initial_state
        self._history: List[str] = [initial_state]

    @property
    def current(self) -> str:
        return self._current

    @property
    def history(self) -> List[str]:
        return list(self._history)

    def can_transition(self, target: str) -> bool:
        return target in self.TRANSITIONS.get(self._current, set())

    def transition(self, target: str) -> bool:
        if not self.can_transition(target):
            return False
        self._history.append(target)
        self._current = target
        return True

    def is_terminal(self) -> bool:
        return self._current in self.TERMINAL_STATES

    def is_active(self) -> bool:
        return self._current in {"running", "planning", "waiting", "ready", "recovering"}

    def reset(self, state: str = "created") -> None:
        self._current = state
        self._history = [state]
