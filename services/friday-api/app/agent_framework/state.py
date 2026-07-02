from enum import Enum


class AgentState(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING = "waiting"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


VALID_TRANSITIONS = {
    AgentState.IDLE: {AgentState.PLANNING, AgentState.PAUSED, AgentState.COMPLETED},
    AgentState.PLANNING: {AgentState.RUNNING, AgentState.FAILED, AgentState.CANCELLED, AgentState.PAUSED},
    AgentState.RUNNING: {AgentState.WAITING, AgentState.COMPLETED, AgentState.FAILED, AgentState.PAUSED, AgentState.CANCELLED},
    AgentState.WAITING: {AgentState.RUNNING, AgentState.FAILED, AgentState.CANCELLED, AgentState.PAUSED},
    AgentState.PAUSED: {AgentState.IDLE, AgentState.CANCELLED, AgentState.FAILED},
    AgentState.COMPLETED: set(),
    AgentState.FAILED: {AgentState.IDLE},
    AgentState.CANCELLED: {AgentState.IDLE},
}


class StateMachine:
    def __init__(self, initial: AgentState = AgentState.IDLE):
        self._state = initial

    @property
    def state(self) -> AgentState:
        return self._state

    def transition(self, target: AgentState) -> bool:
        if target in VALID_TRANSITIONS.get(self._state, set()):
            self._state = target
            return True
        return False

    def can_transition(self, target: AgentState) -> bool:
        return target in VALID_TRANSITIONS.get(self._state, set())

    def reset(self) -> None:
        self._state = AgentState.IDLE
