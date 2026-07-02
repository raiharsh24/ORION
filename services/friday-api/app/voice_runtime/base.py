from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum


class VoicePipelineStage(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    WAKE_WORD = "wake_word"
    STREAMING = "streaming"
    RECOGNIZING = "recognizing"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    ERROR = "error"


@dataclass
class VoiceMessage:
    role: str
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VoiceSession:
    session_id: str
    user_id: str = "default"
    active_mission_id: Optional[str] = None
    messages: List[VoiceMessage] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    last_speaker: str = ""
    turn_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    pipeline_stage: VoicePipelineStage = VoicePipelineStage.IDLE
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str,
                    duration_ms: float = 0.0) -> VoiceMessage:
        msg = VoiceMessage(role=role, content=content, duration_ms=duration_ms)
        self.messages.append(msg)
        self.last_speaker = role
        self.turn_count += 1 if role == "user" else 0
        self.updated_at = datetime.now(timezone.utc)
        return msg

    def get_context_summary(self) -> str:
        recent = self.messages[-5:] if len(self.messages) > 5 else self.messages
        return "\n".join(f"{m.role}: {m.content[:200]}" for m in recent)


@dataclass
class VoiceConfig:
    sample_rate: int = 16000
    channels: int = 1
    sample_width: int = 2
    chunk_duration_ms: int = 30
    min_speech_duration_ms: int = 150
    silence_timeout_ms: int = 1200
    max_recording_duration_s: float = 30.0
    wake_words: List[str] = field(default_factory=lambda: ["friday"])
    wake_word_threshold: float = 0.5
    energy_threshold: float = 500.0
    noise_floor_alpha: float = 0.05
    max_conversation_turns: int = 100
    streaming_buffer_size: int = 10
    auto_endpoint_timeout_ms: int = 2000
