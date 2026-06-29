from enum import Enum
from typing import Set, Dict
from loguru import logger

class VoiceState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"

class VoiceStateMachine:
    def __init__(self, initial_state: VoiceState = VoiceState.IDLE) -> None:
        self._state = initial_state
        self._transitions: Dict[VoiceState, Set[VoiceState]] = {
            VoiceState.IDLE: {VoiceState.LISTENING, VoiceState.THINKING},
            VoiceState.LISTENING: {VoiceState.THINKING, VoiceState.IDLE},
            VoiceState.THINKING: {VoiceState.SPEAKING, VoiceState.IDLE},
            VoiceState.SPEAKING: {VoiceState.IDLE, VoiceState.LISTENING, VoiceState.THINKING}
        }

    @property
    def current_state(self) -> VoiceState:
        return self._state

    def transition_to(self, new_state: VoiceState) -> None:
        if new_state not in self._transitions[self._state]:
            raise ValueError(f"Invalid state transition from {self._state} to {new_state}")
        logger.info(f"VoiceState transitioned from {self._state} to {new_state}")
        self._state = new_state
