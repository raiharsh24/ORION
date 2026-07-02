from typing import Dict, Any


class VoiceRuntimeEvent:
    def __init__(self, topic: str, data: Dict[str, Any]):
        self.topic = topic
        self.data = data

    def to_dict(self) -> Dict[str, Any]:
        return {"topic": self.topic, "data": self.data}


class VoiceStarted(VoiceRuntimeEvent):
    def __init__(self, session_id: str):
        super().__init__("VoiceStarted", {"session_id": session_id})


class VoiceStopped(VoiceRuntimeEvent):
    def __init__(self, session_id: str, duration_s: float = 0.0):
        super().__init__("VoiceStopped", {"session_id": session_id,
                                           "duration_seconds": duration_s})


class WakeWordDetected(VoiceRuntimeEvent):
    def __init__(self, phrase: str, session_id: str):
        super().__init__("WakeWordDetected", {"phrase": phrase,
                                                "session_id": session_id})


class SpeechRecognized(VoiceRuntimeEvent):
    def __init__(self, session_id: str, transcript: str, confidence: float = 1.0):
        super().__init__("SpeechRecognized", {"session_id": session_id,
                                               "transcript": transcript,
                                               "confidence": confidence})


class ConversationStarted(VoiceRuntimeEvent):
    def __init__(self, session_id: str):
        super().__init__("ConversationStarted", {"session_id": session_id})


class ConversationEnded(VoiceRuntimeEvent):
    def __init__(self, session_id: str, turn_count: int = 0):
        super().__init__("ConversationEnded", {"session_id": session_id,
                                                "turn_count": turn_count})


class VoiceInterrupted(VoiceRuntimeEvent):
    def __init__(self, session_id: str, source: str = "user"):
        super().__init__("VoiceInterrupted", {"session_id": session_id,
                                               "source": source})


class VoiceResumed(VoiceRuntimeEvent):
    def __init__(self, session_id: str):
        super().__init__("VoiceResumed", {"session_id": session_id})


class MissionSubmitted(VoiceRuntimeEvent):
    def __init__(self, session_id: str, mission_id: str, transcript: str):
        super().__init__("MissionSubmitted", {"session_id": session_id,
                                               "mission_id": mission_id,
                                               "transcript": transcript})


class MissionResponse(VoiceRuntimeEvent):
    def __init__(self, session_id: str, mission_id: str, success: bool,
                 response_text: str):
        super().__init__("MissionResponse", {"session_id": session_id,
                                              "mission_id": mission_id,
                                              "success": success,
                                              "response_text": response_text})


class SpeechSynthesized(VoiceRuntimeEvent):
    def __init__(self, session_id: str, text: str, duration_ms: float = 0.0):
        super().__init__("SpeechSynthesized", {"session_id": session_id,
                                                "text": text,
                                                "duration_ms": duration_ms})
