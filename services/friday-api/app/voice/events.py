from app.events.events import FridayEvent
from typing import Dict, Any

class WakeWordDetected(FridayEvent):
    """
    Triggered when a valid wake phrase is matched.
    """
    def __init__(self, phrase: str, session_id: str) -> None:
        super().__init__("WakeWordDetected", {
            "phrase": phrase,
            "session_id": session_id
        })

class VoiceStarted(FridayEvent):
    """
    Triggered when user speech activity begins.
    """
    def __init__(self, session_id: str) -> None:
        super().__init__("VoiceStarted", {
            "session_id": session_id
        })

class VoiceEnded(FridayEvent):
    """
    Triggered when user speech activity ceases.
    """
    def __init__(self, session_id: str, duration_seconds: float) -> None:
        super().__init__("VoiceEnded", {
            "session_id": session_id,
            "duration_seconds": duration_seconds
        })

class SpeechStarted(FridayEvent):
    """
    Triggered when the transcription pipeline starts processing speech.
    """
    def __init__(self, session_id: str) -> None:
        super().__init__("SpeechStarted", {
            "session_id": session_id
        })

class SpeechPartial(FridayEvent):
    """
    Triggered during multi-stage transcriptions for partial real-time updates.
    """
    def __init__(self, session_id: str, transcript: str) -> None:
        super().__init__("SpeechPartial", {
            "session_id": session_id,
            "transcript": transcript
        })

class SpeechFinalized(FridayEvent):
    """
    Triggered when the transcription pipeline completes speech conversion.
    """
    def __init__(self, session_id: str, transcript: str) -> None:
        super().__init__("SpeechFinalized", {
            "session_id": session_id,
            "transcript": transcript
        })
