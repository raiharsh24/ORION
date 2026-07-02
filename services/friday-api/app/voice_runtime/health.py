from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class MicrophoneHealth:
    status: str = "healthy"
    sample_rate: int = 16000
    channels: int = 1
    buffer_usage_bytes: int = 0
    last_frame_timestamp: Optional[datetime] = None
    error_count: int = 0


@dataclass
class SpeakerHealth:
    status: str = "healthy"
    is_speaking: bool = False
    queue_depth: int = 0
    last_synthesis_timestamp: Optional[datetime] = None
    error_count: int = 0


@dataclass
class ConversationHealth:
    status: str = "healthy"
    active_sessions: int = 0
    total_sessions: int = 0
    total_messages: int = 0
    last_activity: Optional[datetime] = None


@dataclass
class VoiceRuntimeHealth:
    status: str = "healthy"
    is_listening: bool = False
    is_processing: bool = False
    is_speaking: bool = False
    pipeline_stage: str = "idle"
    active_sessions: int = 0
    total_sessions: int = 0
    uptime_hours: float = 0.0
    total_utterances: int = 0
    total_interruptions: int = 0
    average_response_time_ms: float = 0.0
    microphone: Optional[MicrophoneHealth] = None
    speaker: Optional[SpeakerHealth] = None
    conversation: Optional[ConversationHealth] = None
    wake_word_engine_available: bool = False
    speech_provider_available: bool = False
    tts_available: bool = False
    runtime_connected: bool = False
    checked_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "is_listening": self.is_listening,
            "is_processing": self.is_processing,
            "is_speaking": self.is_speaking,
            "pipeline_stage": self.pipeline_stage,
            "active_sessions": self.active_sessions,
            "total_sessions": self.total_sessions,
            "uptime_hours": self.uptime_hours,
            "total_utterances": self.total_utterances,
            "total_interruptions": self.total_interruptions,
            "average_response_time_ms": self.average_response_time_ms,
            "microphone": {
                "status": self.microphone.status,
                "sample_rate": self.microphone.sample_rate,
                "buffer_usage_bytes": self.microphone.buffer_usage_bytes,
                "error_count": self.microphone.error_count,
            } if self.microphone else None,
            "speaker": {
                "status": self.speaker.status,
                "is_speaking": self.speaker.is_speaking,
                "queue_depth": self.speaker.queue_depth,
                "error_count": self.speaker.error_count,
            } if self.speaker else None,
            "conversation": {
                "status": self.conversation.status,
                "active_sessions": self.conversation.active_sessions,
                "total_sessions": self.conversation.total_sessions,
                "total_messages": self.conversation.total_messages,
            } if self.conversation else None,
            "wake_word_engine_available": self.wake_word_engine_available,
            "speech_provider_available": self.speech_provider_available,
            "tts_available": self.tts_available,
            "runtime_connected": self.runtime_connected,
            "checked_at": (self.checked_at or datetime.now(timezone.utc)).isoformat(),
        }
