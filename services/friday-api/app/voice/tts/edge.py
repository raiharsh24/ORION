import edge_tts
from typing import AsyncIterator, Optional
from loguru import logger

from app.voice.tts import BaseTTSProvider

class EdgeTTSProvider(BaseTTSProvider):
    """
    Text-to-Speech provider using Microsoft Edge Read Aloud API.
    Streams audio chunk data asynchronously via standard WebSockets.
    """
    def __init__(self, voice: str = "en-US-AvaNeural") -> None:
        self._voice = voice

    @property
    def name(self) -> str:
        return "edge_tts"

    @property
    def voice(self) -> str:
        return self._voice

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        """
        Synthesizes text into a stream of audio chunks.
        Yields:
            Audio chunks as bytes (MP3 format).
        """
        if not text.strip():
            return

        logger.info(f"EdgeTTSProvider: starting streaming synthesis for voice '{self._voice}'")
        try:
            communicate = edge_tts.Communicate(text, self._voice)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]
        except Exception as e:
            logger.error(f"EdgeTTSProvider: synthesis stream failure: {e}")
            raise e
