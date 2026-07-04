from abc import ABC, abstractmethod
from fastapi import WebSocket
from loguru import logger

class AudioStreamTransport(ABC):
    """
    Abstract interface for transmitting synthesized audio stream chunks to the target client.
    """
    @abstractmethod
    async def send_audio_chunk(self, chunk: bytes) -> None:
        """Sends a single chunk of audio data to the transport destination."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Cleans up the transport resources."""
        pass

class WebSocketAudioTransport(AudioStreamTransport):
    """
    WebSocket-based implementation of AudioStreamTransport.
    Transmits audio bytes directly over an open FastAPI WebSocket connection.
    """
    def __init__(self, websocket: WebSocket) -> None:
        self._websocket = websocket
        self._closed = False

    async def send_audio_chunk(self, chunk: bytes) -> None:
        if self._closed:
            logger.warning("WebSocketAudioTransport: attempted to send chunk on a closed transport.")
            return
        try:
            await self._websocket.send_bytes(chunk)
        except Exception as e:
            logger.error(f"WebSocketAudioTransport: failed to send audio bytes: {e}")
            self._closed = True
            raise e

    async def close(self) -> None:
        if not self._closed:
            logger.info("WebSocketAudioTransport: closing transport.")
            self._closed = True
            try:
                await self._websocket.close(code=1000)
            except Exception:
                pass
