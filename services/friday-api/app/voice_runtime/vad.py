from typing import Optional, List, Callable
from app.voice_runtime.base import VoiceConfig


class VoiceActivityDetector:
    def __init__(self, config: Optional[VoiceConfig] = None):
        self._config = config or VoiceConfig()
        self._is_speaking = False
        self._speech_start_ms: Optional[float] = None
        self._silence_start_ms: Optional[float] = None
        self._frame_count = 0
        self._noise_floor = self._config.energy_threshold
        self._adaptive = True
        self._on_speech_start: List[Callable] = []
        self._on_speech_end: List[Callable] = []
        self._on_noise_update: List[Callable] = []

    def on_speech_start(self, callback: Callable) -> None:
        self._on_speech_start.append(callback)

    def on_speech_end(self, callback: Callable) -> None:
        self._on_speech_end.append(callback)

    def process_frame(self, frame: bytes, frame_duration_ms: int = 30) -> bool:
        energy = self._calculate_energy(frame)
        threshold = self._noise_floor * 1.5
        is_speech = energy > threshold

        if self._adaptive:
            self._noise_floor = (
                (1 - self._config.noise_floor_alpha) * self._noise_floor
                + self._config.noise_floor_alpha * energy
            )

        if is_speech and not self._is_speaking:
            self._speech_start_ms = self._frame_count * frame_duration_ms
            self._silence_start_ms = None
            if self._frame_count * frame_duration_ms - (self._speech_start_ms or 0) >= self._config.min_speech_duration_ms:
                self._is_speaking = True
                for cb in self._on_speech_start:
                    cb()
            return True

        if not is_speech and self._is_speaking:
            if self._silence_start_ms is None:
                self._silence_start_ms = self._frame_count * frame_duration_ms
            silence_duration = (self._frame_count * frame_duration_ms) - self._silence_start_ms
            if silence_duration >= self._config.silence_timeout_ms:
                self._is_speaking = False
                for cb in self._on_speech_end:
                    cb()
                return False
            return True

        if not is_speech and not self._is_speaking:
            self._speech_start_ms = None
            self._silence_start_ms = None

        self._frame_count += 1
        return self._is_speaking

    def reset(self) -> None:
        self._is_speaking = False
        self._speech_start_ms = None
        self._silence_start_ms = None
        self._frame_count = 0

    def set_config(self, config: VoiceConfig) -> None:
        self._config = config

    def set_adaptive(self, enabled: bool) -> None:
        self._adaptive = enabled

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    @property
    def noise_floor(self) -> float:
        return self._noise_floor

    @property
    def energy_threshold(self) -> float:
        return self._noise_floor * 1.5

    def _calculate_energy(self, frame: bytes) -> float:
        if not frame:
            return 0.0
        samples = len(frame) // 2
        if samples == 0:
            return 0.0
        import struct
        total = 0
        for i in range(min(samples, len(frame) // 2)):
            val = struct.unpack_from("<h", frame, i * 2)[0]
            total += abs(val)
        return total / samples
