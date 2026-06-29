import asyncio
from typing import Optional
from loguru import logger

from app.voice.tts import TTSCoordinator
from app.voice.transport import AudioStreamTransport

class VoiceOutputManager:
    """
    Manages the lifecycle of synthesized speech streams and routes audio chunks 
    from the TTSCoordinator to the configured AudioStreamTransport.
    """
    def __init__(self, tts_coordinator: TTSCoordinator) -> None:
        self.tts_coordinator = tts_coordinator
        self._active_task: Optional[asyncio.Task] = None
        self._transport: Optional[AudioStreamTransport] = None
        self._streaming_active = False
        self.last_error: Optional[Exception] = None

    def set_transport(self, transport: Optional[AudioStreamTransport]) -> None:
        """Configures the current target client transport layer."""
        self._transport = transport

    async def start_streaming(self, text: str, provider_name: Optional[str] = None) -> None:
        """
        Synthesizes the text and streams the generated audio chunks immediately 
        to the configured transport in a background task.
        """
        # Cancel any active stream before starting a new one
        await self.cancel_streaming()
        self.last_error = None

        if not self._transport:
            logger.warning("VoiceOutputManager: no transport configured, skipping streaming synthesis.")
            return

        self._streaming_active = True
        self._active_task = asyncio.create_task(
            self._stream_pipeline(text, provider_name)
        )

    async def _stream_pipeline(self, text: str, provider_name: Optional[str] = None) -> None:
        try:
            logger.info("VoiceOutputManager: starting stream pipeline...")
            async for chunk in self.tts_coordinator.synthesize_stream(text, provider_name):
                if not self._streaming_active:
                    break
                if self._transport:
                    await self._transport.send_audio_chunk(chunk)
            logger.info("VoiceOutputManager: streaming pipeline completed successfully.")
        except asyncio.CancelledError:
            logger.info("VoiceOutputManager: streaming pipeline task was cancelled.")
            raise
        except Exception as e:
            logger.error(f"VoiceOutputManager: error during stream pipeline execution: {e}")
            self.last_error = e
        finally:
            self._streaming_active = False
            self._active_task = None

    async def cancel_streaming(self) -> None:
        """
        Cancels the active streaming task immediately, stopping any further 
        synthesis and transport transmission.
        """
        self._streaming_active = False
        if self._active_task and not self._active_task.done():
            logger.info("VoiceOutputManager: cancelling active audio stream task.")
            self._active_task.cancel()
            try:
                await self._active_task
            except asyncio.CancelledError:
                pass
            finally:
                self._active_task = None

    async def shutdown(self) -> None:
        """Gracefully shuts down the manager, cancelling any active streams and closing the transport."""
        await self.cancel_streaming()
        if self._transport:
            await self._transport.close()
            self._transport = None
