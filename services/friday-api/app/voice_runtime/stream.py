from typing import Optional, List, Dict, Any, AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class PartialTranscript:
    text: str
    is_final: bool = False
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    segment_index: int = 0


class StreamingHandler:
    def __init__(self):
        self._transcripts: List[PartialTranscript] = []
        self._current_text: str = ""
        self._segment_index: int = 0
        self._on_partial: List[Callable] = []
        self._on_final: List[Callable] = []
        self._buffer: str = ""
        self._is_interrupted: bool = False

    def on_partial(self, callback: Callable) -> None:
        self._on_partial.append(callback)

    def on_final(self, callback: Callable) -> None:
        self._on_final.append(callback)

    def add_partial(self, text: str, confidence: float = 1.0) -> PartialTranscript:
        transcript = PartialTranscript(
            text=text,
            is_final=False,
            confidence=confidence,
            segment_index=self._segment_index,
        )
        self._transcripts.append(transcript)
        self._current_text = text
        self._buffer += text
        for cb in self._on_partial:
            try:
                cb(transcript)
            except Exception:
                pass
        return transcript

    def finalize(self, text: str, confidence: float = 1.0) -> PartialTranscript:
        transcript = PartialTranscript(
            text=text,
            is_final=True,
            confidence=confidence,
            segment_index=self._segment_index,
        )
        self._transcripts.append(transcript)
        self._current_text = text
        self._buffer += text
        self._segment_index += 1
        for cb in self._on_final:
            try:
                cb(transcript)
            except Exception:
                pass
        return transcript

    def reset(self) -> None:
        self._transcripts.clear()
        self._current_text = ""
        self._buffer = ""
        self._is_interrupted = False

    def interrupt(self) -> None:
        self._is_interrupted = True

    def resume(self) -> None:
        self._is_interrupted = False

    @property
    def current_text(self) -> str:
        return self._current_text

    @property
    def full_text(self) -> str:
        return self._buffer

    @property
    def is_interrupted(self) -> bool:
        return self._is_interrupted

    @property
    def transcripts(self) -> List[PartialTranscript]:
        return list(self._transcripts)

    def clear_buffer(self) -> None:
        self._buffer = ""
        self._transcripts.clear()
