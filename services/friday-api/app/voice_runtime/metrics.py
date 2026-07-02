import time
import statistics
from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class VoiceRuntimeMetricsSnapshot:
    total_utterances: int = 0
    total_interruptions: int = 0
    total_sessions: int = 0
    average_response_time_ms: float = 0.0
    average_speech_duration_ms: float = 0.0
    average_transcript_confidence: float = 1.0
    interrupt_frequency: float = 0.0
    stream_health_score: float = 1.0
    peak_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    latency_p95_ms: float = 0.0
    uptime_hours: float = 0.0


class VoiceRuntimeMetrics:
    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self._start_time = time.time()
        self._utterances = 0
        self._interruptions = 0
        self._sessions = 0
        self._response_times: List[float] = []
        self._speech_durations: List[float] = []
        self._transcript_confidences: List[float] = []
        self._stream_errors = 0
        self._stream_total = 0

    def record_utterance(self) -> None:
        self._utterances += 1

    def record_interruption(self) -> None:
        self._interruptions += 1

    def record_session(self) -> None:
        self._sessions += 1

    def record_response_time(self, ms: float) -> None:
        self._response_times.append(ms)

    def record_speech_duration(self, ms: float) -> None:
        self._speech_durations.append(ms)

    def record_transcript_confidence(self, confidence: float) -> None:
        self._transcript_confidences.append(confidence)

    def record_stream_event(self, success: bool) -> None:
        self._stream_total += 1
        if not success:
            self._stream_errors += 1

    def snapshot(self) -> VoiceRuntimeMetricsSnapshot:
        uptime = (time.time() - self._start_time) / 3600
        avg_resp = statistics.mean(self._response_times) if self._response_times else 0.0
        avg_speech = statistics.mean(self._speech_durations) if self._speech_durations else 0.0
        avg_conf = statistics.mean(self._transcript_confidences) if self._transcript_confidences else 1.0
        int_freq = self._interruptions / max(self._utterances, 1)
        stream_health = 1.0 - (self._stream_errors / max(self._stream_total, 1))
        p95 = sorted(self._response_times)[int(len(self._response_times) * 0.95)] if len(self._response_times) >= 20 else (max(self._response_times) if self._response_times else 0.0)

        return VoiceRuntimeMetricsSnapshot(
            total_utterances=self._utterances,
            total_interruptions=self._interruptions,
            total_sessions=self._sessions,
            average_response_time_ms=round(avg_resp, 2),
            average_speech_duration_ms=round(avg_speech, 2),
            average_transcript_confidence=round(avg_conf, 3),
            interrupt_frequency=round(int_freq, 3),
            stream_health_score=round(stream_health, 3),
            peak_latency_ms=round(max(self._response_times), 2) if self._response_times else 0.0,
            min_latency_ms=round(min(self._response_times), 2) if self._response_times else 0.0,
            latency_p95_ms=round(p95, 2),
            uptime_hours=round(uptime, 2),
        )

    @property
    def total_utterances(self) -> int:
        return self._utterances

    @property
    def total_interruptions(self) -> int:
        return self._interruptions

    @property
    def average_response_time_ms(self) -> float:
        return statistics.mean(self._response_times) if self._response_times else 0.0
