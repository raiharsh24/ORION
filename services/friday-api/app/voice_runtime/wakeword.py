from typing import List, Optional, Callable, Set
from app.voice_runtime.base import VoiceConfig


class WakeWordEngine:
    def __init__(self, config: Optional[VoiceConfig] = None):
        self._config = config or VoiceConfig()
        self._wake_words: Set[str] = set(w.lower() for w in self._config.wake_words)
        self._detected: bool = False
        self._on_detect: List[Callable] = []
        self._text_buffer: str = ""
        self._threshold = self._config.wake_word_threshold

    def register_wake_word(self, word: str) -> None:
        self._wake_words.add(word.lower())

    def unregister_wake_word(self, word: str) -> None:
        self._wake_words.discard(word.lower())

    def on_detected(self, callback: Callable) -> None:
        self._on_detect.append(callback)

    def process_transcript(self, text: str) -> Optional[str]:
        self._text_buffer += text.lower()
        for word in self._wake_words:
            idx = self._text_buffer.find(word)
            if idx != -1:
                self._detected = True
                remainder = self._text_buffer[idx + len(word):].strip()
                self._text_buffer = ""
                for cb in self._on_detect:
                    cb(word, remainder)
                return word
        if len(self._text_buffer) > 100:
            self._text_buffer = self._text_buffer[-50:]
        return None

    def process_text(self, text: str) -> Optional[str]:
        return self.process_transcript(text)

    def detect_manually(self, phrase: str = "friday") -> None:
        self._detected = True
        for cb in self._on_detect:
            cb(phrase, "")

    def reset(self) -> None:
        self._detected = False
        self._text_buffer = ""

    @property
    def is_detected(self) -> bool:
        return self._detected

    @property
    def wake_words(self) -> List[str]:
        return list(self._wake_words)

    def set_threshold(self, threshold: float) -> None:
        self._threshold = max(0.0, min(1.0, threshold))

    @property
    def threshold(self) -> float:
        return self._threshold

    def health(self) -> dict:
        return {
            "status": "healthy",
            "registered_wake_words": len(self._wake_words),
            "wake_words": list(self._wake_words),
            "threshold": self._threshold,
        }
