import time
import uuid
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime, timezone

from app.voice_runtime.base import (
    VoiceSession, VoiceMessage, VoicePipelineStage, VoiceConfig,
)
from app.voice_runtime.vad import VoiceActivityDetector
from app.voice_runtime.wakeword import WakeWordEngine
from app.voice_runtime.audio import AudioProcessor, AudioChunk, AudioBuffer
from app.voice_runtime.stream import StreamingHandler, PartialTranscript
from app.voice_runtime.speech import SpeechManager
from app.voice_runtime.conversation import ConversationManager
from app.voice_runtime.interrupt import InterruptHandler
from app.voice_runtime.metrics import VoiceRuntimeMetrics, VoiceRuntimeMetricsSnapshot
from app.voice_runtime.health import (
    VoiceRuntimeHealth, MicrophoneHealth, SpeakerHealth, ConversationHealth,
)
from app.voice_runtime.events import (
    VoiceRuntimeEvent,
    VoiceStarted, VoiceStopped,
    WakeWordDetected,
    SpeechRecognized,
    ConversationStarted, ConversationEnded,
    VoiceInterrupted, VoiceResumed,
    MissionSubmitted, MissionResponse,
    SpeechSynthesized,
)


class VoiceRuntime:
    def __init__(self, runtime: Any = None,
                 speech_provider: Any = None,
                 tts_coordinator: Any = None,
                 memory_engine: Any = None,
                 config: Optional[VoiceConfig] = None,
                 event_bus: Any = None):
        self._runtime = runtime
        self._config = config or VoiceConfig()
        self._event_bus = event_bus

        self._vad = VoiceActivityDetector(config)
        self._wakeword = WakeWordEngine(config)
        self._audio = AudioProcessor(config)
        self._stream = StreamingHandler()
        self._speech = SpeechManager(
            speech_provider=speech_provider,
            tts_coordinator=tts_coordinator,
        )
        self._conversation = ConversationManager(
            config=config,
            memory_engine=memory_engine,
        )
        self._interrupt = InterruptHandler(runtime=runtime)
        self._metrics = VoiceRuntimeMetrics()
        self._started_at = datetime.now(timezone.utc)
        self._is_listening = False
        self._is_processing = False
        self._on_event: List[Callable] = []

        self._wire_hooks()

    def _wire_hooks(self) -> None:
        self._wakeword.on_detected(self._on_wake_word_detected)

        self._speech.on_transcript(self._on_transcript_received)
        self._speech.on_synthesis_start(self._on_synthesis_started)

        self._conversation.on_session_start(self._on_session_started)
        self._conversation.on_session_end(self._on_session_ended)

        self._interrupt.on_interrupt(self._on_interrupted)
        self._interrupt.on_resume(self._on_resumed)

    def on_event(self, callback: Callable) -> None:
        self._on_event.append(callback)

    def set_event_bus(self, event_bus: Any) -> None:
        self._event_bus = event_bus

    async def start_listening(self, session_id: Optional[str] = None,
                               user_id: str = "default") -> str:
        session = self._conversation.create_session(
            session_id=session_id, user_id=user_id)
        self._is_listening = True
        self._metrics.record_session()
        self._conversation.set_pipeline_stage(
            session.session_id, VoicePipelineStage.LISTENING)
        self._publish_event(VoiceStarted(session.session_id))
        self._publish_event(ConversationStarted(session.session_id))
        return session.session_id

    async def stop_listening(self, session_id: str) -> None:
        self._is_listening = False
        session = self._conversation.get_session(session_id)
        turn_count = session.turn_count if session else 0
        self._publish_event(VoiceStopped(session_id))
        self._publish_event(ConversationEnded(session_id, turn_count))

    async def process_audio_frame(self, session_id: str,
                                   frame: bytes,
                                   frame_duration_ms: int = 30) -> None:
        is_speech = self._vad.process_frame(frame, frame_duration_ms)
        self._audio.add_pcm_data(frame, time.time() * 1000)

    async def process_transcript(self, session_id: str,
                                  text: str) -> Optional[str]:
        wake_word = self._wakeword.process_text(text)
        if wake_word:
            self._publish_event(WakeWordDetected(wake_word, session_id))
            return wake_word

        if not self._wakeword.is_detected:
            return None

        self._is_processing = True
        self._conversation.set_pipeline_stage(
            session_id, VoicePipelineStage.PROCESSING)
        self._metrics.record_utterance()

        self._stream.add_partial(text)
        transcript = self._stream.finalize(text)

        self._publish_event(SpeechRecognized(
            session_id, transcript.text, transcript.confidence))

        response_text = await self._execute_mission(session_id, text)

        self._conversation.add_message(
            session_id, "user", text, duration_ms=0.0)
        self._conversation.add_message(
            session_id, "assistant", response_text, duration_ms=0.0)

        self._is_processing = False
        self._conversation.set_pipeline_stage(
            session_id, VoicePipelineStage.IDLE)

        return response_text

    async def process_audio_and_respond(self, session_id: str,
                                         audio_data: bytes) -> Optional[str]:
        text = await self._speech.transcribe(audio_data)
        if not text:
            return None
        return await self.process_transcript(session_id, text)

    async def _execute_mission(self, session_id: str,
                                transcript: str) -> str:
        if not self._runtime:
            return "I'm not connected to a runtime right now."

        start_time = time.time()

        intent = self._detect_intent(transcript)

        try:
            if hasattr(self._runtime, "submit_and_run"):
                result = await self._runtime.submit_and_run(
                    transcript, intent=intent)
                mission_id = result.mission_id
            elif hasattr(self._runtime, "submit"):
                mission = await self._runtime.submit(transcript, intent=intent)
                mission_id = mission.mission_id
            else:
                return "Runtime is not available."

            self._conversation.set_mission(session_id, mission_id)
            self._interrupt.track_mission(session_id, mission_id)
            self._publish_event(MissionSubmitted(
                session_id, mission_id, transcript))

            if hasattr(self._runtime, "submit"):
                if hasattr(self._runtime, "submit_and_run"):
                    pass
                elif hasattr(self._runtime, "wait_for_all"):
                    await self._runtime.wait_for_all()
                    result = self._runtime.get_status(mission_id)
                    success = result == "completed"
                else:
                    result = True
                    success = True
            else:
                success = getattr(result, "success", False)

            if hasattr(self._runtime, "get_history"):
                ref = self._runtime.get_history(limit=1)
                response_text = self._format_mission_result(success, transcript)
            else:
                response_text = self._format_mission_result(success, transcript)

            elapsed_ms = (time.time() - start_time) * 1000
            self._metrics.record_response_time(elapsed_ms)

            self._publish_event(MissionResponse(
                session_id, mission_id, success, response_text))
            return response_text

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self._metrics.record_response_time(elapsed_ms)
            return f"An error occurred: {str(e)}"

    def _detect_intent(self, text: str) -> str:
        text_lower = text.lower()
        if any(w in text_lower for w in ["search", "find", "look up", "google"]):
            return "search"
        if any(w in text_lower for w in ["code", "write", "program", "script"]):
            return "code"
        if any(w in text_lower for w in ["plan", "schedule", "organize"]):
            return "plan"
        if any(w in text_lower for w in ["email", "send", "message", "compose"]):
            return "communication"
        if any(w in text_lower for w in ["analyze", "analyze", "summarize"]):
            return "analysis"
        return "conversation"

    def _format_mission_result(self, success: bool,
                                 transcript: str) -> str:
        if success:
            return f"Done. I've processed your request: {transcript[:100]}"
        return f"I ran into an issue processing your request. Let me try again."

    async def speak(self, session_id: str, text: str) -> None:
        self._conversation.set_pipeline_stage(
            session_id, VoicePipelineStage.SPEAKING)
        async for chunk in self._speech.synthesize(text):
            if self._interrupt is not None:
                pass
        self._conversation.set_pipeline_stage(
            session_id, VoicePipelineStage.IDLE)

    async def handle_interrupt(self, session_id: str) -> None:
        self._publish_event(VoiceInterrupted(session_id, "user"))
        self._metrics.record_interruption()
        await self._interrupt.cancel_speaking(session_id, self._speech)
        await self._interrupt.handle_user_interrupt(session_id)
        self._stream.interrupt()

    async def resume_after_interrupt(self, session_id: str) -> None:
        await self._interrupt.resume_mission(session_id)
        self._stream.resume()
        self._publish_event(VoiceResumed(session_id))

    async def cancel_mission(self, session_id: str) -> None:
        await self._interrupt.cancel_mission(session_id)

    async def end_session(self, session_id: str) -> None:
        await self._interrupt.cancel_mission(session_id)
        self._conversation.end_session(session_id)
        self._audio.reset()
        self._stream.reset()
        self._vad.reset()

    def register_wake_word(self, word: str) -> None:
        self._wakeword.register_wake_word(word)

    def get_session(self, session_id: str) -> Optional[VoiceSession]:
        return self._conversation.get_session(session_id)

    def list_sessions(self) -> List[VoiceSession]:
        return self._conversation.list_sessions()

    def metrics(self) -> VoiceRuntimeMetricsSnapshot:
        return self._metrics.snapshot()

    def health(self) -> VoiceRuntimeHealth:
        uptime = (datetime.now(timezone.utc) - self._started_at).total_seconds() / 3600
        sessions = self._conversation.list_sessions()
        total_msgs = sum(len(s.messages) for s in sessions)
        last_activity = max((s.updated_at for s in sessions),
                            default=None) if sessions else None
        avg_resp = self._metrics.average_response_time_ms

        mic_h = MicrophoneHealth(
            buffer_usage_bytes=self._audio.buffer.size,
            error_count=0,
        )
        spk_h = SpeakerHealth(
            is_speaking=self._speech.is_speaking,
            queue_depth=0,
            error_count=0,
        )
        conv_h = ConversationHealth(
            active_sessions=self._conversation.active_session_count,
            total_sessions=self._conversation.session_count,
            total_messages=total_msgs,
            last_activity=last_activity,
        )

        return VoiceRuntimeHealth(
            status="healthy",
            is_listening=self._is_listening,
            is_processing=self._is_processing,
            is_speaking=self._speech.is_speaking,
            pipeline_stage="active" if self._is_listening else "idle",
            active_sessions=self._conversation.active_session_count,
            total_sessions=self._conversation.session_count,
            uptime_hours=round(uptime, 2),
            total_utterances=self._metrics.total_utterances,
            total_interruptions=self._metrics.total_interruptions,
            average_response_time_ms=round(avg_resp, 2),
            microphone=mic_h,
            speaker=spk_h,
            conversation=conv_h,
            wake_word_engine_available=True,
            speech_provider_available=self._speech._speech_provider is not None,
            tts_available=self._speech._tts_coordinator is not None,
            runtime_connected=self._runtime is not None,
        )

    def _publish_event(self, event: VoiceRuntimeEvent) -> None:
        for cb in self._on_event:
            try:
                cb(event)
            except Exception:
                pass
        if self._event_bus and hasattr(self._event_bus, "publish_background"):
            try:
                self._event_bus.publish_background(event)
            except RuntimeError:
                pass

    def _on_wake_word_detected(self, phrase: str, remainder: str) -> None:
        pass

    def _on_transcript_received(self, text: str) -> None:
        pass

    def _on_synthesis_started(self, text: str) -> None:
        pass

    def _on_session_started(self, session: VoiceSession) -> None:
        pass

    def _on_session_ended(self, session: VoiceSession) -> None:
        pass

    def _on_interrupted(self, session_id: str, source: str) -> None:
        pass

    def _on_resumed(self, session_id: str, mission_id: str) -> None:
        pass


__all__ = [
    "VoiceRuntime",
    "VoiceSession",
    "VoiceMessage",
    "VoicePipelineStage",
    "VoiceConfig",
    "VoiceActivityDetector",
    "WakeWordEngine",
    "AudioProcessor",
    "AudioChunk",
    "AudioBuffer",
    "StreamingHandler",
    "PartialTranscript",
    "SpeechManager",
    "ConversationManager",
    "InterruptHandler",
    "VoiceRuntimeMetrics",
    "VoiceRuntimeMetricsSnapshot",
    "VoiceRuntimeHealth",
    "MicrophoneHealth",
    "SpeakerHealth",
    "ConversationHealth",
    "VoiceRuntimeEvent",
    "VoiceStarted",
    "VoiceStopped",
    "WakeWordDetected",
    "SpeechRecognized",
    "ConversationStarted",
    "ConversationEnded",
    "VoiceInterrupted",
    "VoiceResumed",
    "MissionSubmitted",
    "MissionResponse",
    "SpeechSynthesized",
]
