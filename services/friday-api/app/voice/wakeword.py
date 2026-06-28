from loguru import logger
from app.voice.vad import calculate_rms

class BaseWakeWordEngine:
    """
    Interface for Wake Word/Keyword Spotting engines.
    """
    def detect(self, frame: bytes) -> bool:
        """
        Processes a block of audio.
        Returns:
            True if wake word matches, False otherwise.
        """
        raise NotImplementedError

    def reset(self) -> None:
        """Resets the state of the keyword spotter."""
        raise NotImplementedError


class ThresholdWakeWordEngine(BaseWakeWordEngine):
    """
    A signal-threshold wake word detector for keyword triggers.
    In testing/simulation modes, it supports triggering via specific high-energy
    audio burst signatures (e.g. RMS > 12000) or explicit control signals.
    """
    def __init__(self, wake_phrases=None, trigger_rms_threshold: float = 12000.0) -> None:
        self.wake_phrases = wake_phrases or ["Hey FRIDAY", "FRIDAY"]
        self.trigger_rms_threshold = trigger_rms_threshold
        self.is_triggered = False

    def detect(self, frame: bytes) -> bool:
        if self.is_triggered:
            return True
            
        rms = calculate_rms(frame)
        
        # Audio signature trigger check (deterministic testing hook)
        if rms >= self.trigger_rms_threshold:
            logger.info(f"WakeWord: High-energy audio trigger signature matched (RMS: {rms:.1f})")
            self.is_triggered = True
            return True
            
        return False

    def trigger_manually(self) -> None:
        """Allows direct software injection of wake triggers."""
        logger.info("WakeWord: Manual trigger override injected.")
        self.is_triggered = True

    def reset(self) -> None:
        self.is_triggered = False
