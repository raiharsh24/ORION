from typing import Optional, List, AsyncIterator
from dataclasses import dataclass, field
from app.voice_runtime.base import VoiceConfig


@dataclass
class AudioChunk:
    data: bytes
    sequence: int = 0
    timestamp_ms: float = 0.0
    is_final: bool = False
    is_speech: bool = False


class AudioBuffer:
    def __init__(self, max_size_bytes: int = 1048576):
        self._chunks: List[AudioChunk] = []
        self._max_size = max_size_bytes
        self._current_size = 0
        self._sequence = 0

    def add_chunk(self, data: bytes, timestamp_ms: float = 0.0,
                  is_speech: bool = False) -> AudioChunk:
        chunk = AudioChunk(
            data=data,
            sequence=self._sequence,
            timestamp_ms=timestamp_ms,
            is_speech=is_speech,
        )
        self._sequence += 1
        self._chunks.append(chunk)
        self._current_size += len(data)
        if self._current_size > self._max_size:
            removed = self._chunks.pop(0)
            self._current_size -= len(removed.data)
        return chunk

    def get_all(self) -> bytes:
        return b"".join(c.data for c in self._chunks)

    def get_speech(self) -> bytes:
        return b"".join(c.data for c in self._chunks if c.is_speech)

    def clear(self) -> None:
        self._chunks.clear()
        self._current_size = 0

    @property
    def size(self) -> int:
        return self._current_size

    @property
    def count(self) -> int:
        return len(self._chunks)

    @property
    def duration_ms(self) -> float:
        total_samples = self._current_size // 2
        return (total_samples / 16000.0) * 1000 if total_samples > 0 else 0.0


class AudioProcessor:
    def __init__(self, config: Optional[VoiceConfig] = None):
        self._config = config or VoiceConfig()
        self._buffer = AudioBuffer()

    def reset(self) -> None:
        self._buffer.clear()

    def add_pcm_data(self, data: bytes, timestamp_ms: float = 0.0) -> AudioChunk:
        return self._buffer.add_chunk(data, timestamp_ms)

    def get_pcm_data(self) -> bytes:
        return self._buffer.get_all()

    def get_speech_data(self) -> bytes:
        return self._buffer.get_speech()

    def convert_to_wav(self, pcm_data: bytes) -> bytes:
        sample_rate = self._config.sample_rate
        channels = self._config.channels
        sample_width = self._config.sample_width
        data_size = len(pcm_data)
        header_size = 44
        total_size = header_size + data_size

        header = b"RIFF"
        header += (total_size - 8).to_bytes(4, "little")
        header += b"WAVE"
        header += b"fmt "
        header += (16).to_bytes(4, "little")
        header += (1).to_bytes(2, "little")
        header += channels.to_bytes(2, "little")
        header += sample_rate.to_bytes(4, "little")
        header += (sample_rate * channels * sample_width).to_bytes(4, "little")
        header += (channels * sample_width).to_bytes(2, "little")
        header += (sample_width * 8).to_bytes(2, "little")
        header += b"data"
        header += data_size.to_bytes(4, "little")

        return header + pcm_data

    @property
    def buffer(self) -> AudioBuffer:
        return self._buffer

    @property
    def config(self) -> VoiceConfig:
        return self._config
