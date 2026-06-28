from loguru import logger
from typing import Optional, Any
from app.voice.stt import BaseSpeechProvider
from app.voice.events import SpeechStarted, SpeechFinalized

class VoiceSessionManager:
    """
    Coordinates voice processing lifecycles, transcribes captured audio via SpeechProviders,
    and feeds translated outputs into FridayOrchestrator for automated query execution.
    """
    def __init__(self, event_bus: Any, orchestrator_factory: Any, speech_provider: Optional[BaseSpeechProvider] = None) -> None:
        self.event_bus = event_bus
        self.orchestrator_factory = orchestrator_factory
        self.speech_provider = speech_provider

    async def process_audio_session(self, session_id: str, audio_data: bytes) -> tuple[str, str]:
        """
        Translates raw speech segment, publishes events, and processes
        the transcript through the main FRIDAY Orchestrator.
        Returns:
            A tuple of (transcript_text, response_text).
        """
        logger.info(f"VoiceSessionManager: starting processing for session '{session_id}' (audio size: {len(audio_data)} bytes)")
        
        # 1. Publish SpeechStarted
        if self.event_bus:
            self.event_bus.publish_background(SpeechStarted(session_id=session_id))
            
        if not self.speech_provider:
            logger.error("VoiceSessionManager: no speech provider configured.")
            return "", ""
            
        # 2. Transcribe Audio
        try:
            transcript = await self.speech_provider.transcribe(audio_data)
        except Exception as e:
            logger.error(f"VoiceSessionManager: transcription failed: {e}")
            raise e
            
        transcript = transcript.strip()
        logger.info(f"VoiceSessionManager: finalized transcription: '{transcript}'")
        
        # 3. Publish SpeechFinalized
        if self.event_bus:
            self.event_bus.publish_background(SpeechFinalized(session_id=session_id, transcript=transcript))
            
        if not transcript:
            logger.info("VoiceSessionManager: transcribed text is empty. Skipping orchestration.")
            return "", ""
            
        # 4. Resolve Orchestrator and Dispatch prompt
        try:
            orchestrator = await self.orchestrator_factory()
            response = await orchestrator.process_query(prompt=transcript, session_id=session_id)
            resp_text = response.response if hasattr(response, "response") else str(response)
            return transcript, resp_text
        except Exception as e:
            logger.error(f"VoiceSessionManager: FridayOrchestrator failed to process query: {e}")
            raise e
