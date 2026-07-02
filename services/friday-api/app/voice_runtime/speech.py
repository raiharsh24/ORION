from typing import Optional, AsyncIterator, Callable, List
from app.voice_runtime.stream import StreamingHandler


class SpeechManager:
    def __init__(self, speech_provider: Any = None,
                 tts_coordinator: Any = None):
        self._speech_provider = speech_provider
        self._tts_coordinator = tts_coordinator
        self._streaming_handler = StreamingHandler()
        self._on_transcript: List[Callable] = []
        self._on_synthesis_start: List[Callable] = []
        self._on_synthesis_chunk: List[Callable] = []
        self._is_speaking = False

    def on_transcript(self, callback: Callable) -> None:
        self._on_transcript.append(callback)

    def on_synthesis_start(self, callback: Callable) -> None:
        self._on_synthesis_start.append(callback)

    def on_synthesis_chunk(self, callback: Callable) -> None:
        self._on_synthesis_chunk.append(callback)

    async def transcribe(self, audio_data: bytes) -> str:
        if not self._speech_provider:
            return ""
        try:
            if hasattr(self._speech_provider, "transcribe"):
                text = await self._speech_provider.transcribe(audio_data)
            else:
                text = ""
            self._streaming_handler.finalize(text)
            for cb in self._on_transcript:
                try:
                    cb(text)
                except Exception:
                    pass
            return text
        except Exception:
            return ""

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        if not self._tts_coordinator:
            return
        self._is_speaking = True
        for cb in self._on_synthesis_start:
            try:
                cb(text)
            except Exception:
                pass
        try:
            if hasattr(self._tts_coordinator, "synthesize_stream"):
                async for chunk in self._tts_coordinator.synthesize_stream(text):
                    if not self._is_speaking:
                        break
                    for cb in self._on_synthesis_chunk:
                        try:
                            cb(chunk)
                        except Exception:
                            pass
                    yield chunk
        except Exception:
            pass
        finally:
            self._is_speaking = False

    def cancel_synthesis(self) -> None:
        self._is_speaking = False
        self._streaming_handler.interrupt()

    def reset(self) -> None:
        self._is_speaking = False
        self._streaming_handler.reset()

    @property
    def streaming_handler(self) -> StreamingHandler:
        return self._streaming_handler

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    @property
    def available(self) -> bool:
        return self._speech_provider is not None or self._tts_coordinator is not None
