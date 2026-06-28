import math
import struct
from typing import List
from loguru import logger

class BaseVAD:
    """
    Interface for Voice Activity Detection engines.
    """
    def process_frame(self, frame: bytes, frame_duration_ms: int) -> bool:
        """
        Process a slice of audio data.
        Returns:
            True if speech is active, False if silent.
        """
        raise NotImplementedError

    def reset(self) -> None:
        """Resets the state machine of the VAD."""
        raise NotImplementedError


def calculate_rms(frame: bytes) -> float:
    """
    Calculates the Root Mean Square (RMS) energy level of 16-bit PCM samples.
    """
    count = len(frame) // 2
    if count == 0:
        return 0.0
    try:
        shorts = struct.unpack(f"{count}h", frame)
        sum_squares = sum(s * s for s in shorts)
        return math.sqrt(sum_squares / count)
    except Exception as e:
        logger.warning(f"Error calculating audio frame RMS: {e}")
        return 0.0


class EnergyThresholdVAD(BaseVAD):
    """
    An adaptive energy threshold VAD that tracks the noise floor dynamically.
    Optimized for raw PCM input frames.
    """
    def __init__(self, initial_threshold: float = 1000.0, min_speech_duration_ms: int = 150, silence_timeout_ms: int = 1200) -> None:
        self.base_offset = initial_threshold
        self.threshold = initial_threshold
        self.noise_floor = initial_threshold / 2
        self.min_speech_duration_ms = min_speech_duration_ms
        self.silence_timeout_ms = silence_timeout_ms
        
        # State tracking flags
        self.is_speech_active = False
        self.silence_accumulator_ms = 0
        self.speech_accumulator_ms = 0
        
        # Noise calibration buffers
        self.noise_samples: List[float] = []

    def process_frame(self, frame: bytes, frame_duration_ms: int) -> bool:
        """
        Evaluates a frame against the dynamic threshold to track state changes.
        """
        rms = calculate_rms(frame)
        
        # Noise floor tracking: if current block energy is below threshold,
        # adjust background noise floor to adapt to environmental sound.
        if rms < self.threshold:
            self.noise_samples.append(rms)
            if len(self.noise_samples) > 50:
                self.noise_samples.pop(0)
            self.noise_floor = sum(self.noise_samples) / len(self.noise_samples)
            # Re-calibrate threshold: noise floor + offset
            self.threshold = self.noise_floor + self.base_offset

        is_frame_speech = rms > self.threshold
        
        if is_frame_speech:
            self.silence_accumulator_ms = 0
            self.speech_accumulator_ms += frame_duration_ms
            
            # Start of speech trigger gate
            if not self.is_speech_active and self.speech_accumulator_ms >= self.min_speech_duration_ms:
                self.is_speech_active = True
                logger.info(f"VAD: Speech started detected (RMS: {rms:.1f}, Threshold: {self.threshold:.1f})")
        else:
            self.speech_accumulator_ms = 0
            if self.is_speech_active:
                self.silence_accumulator_ms += frame_duration_ms
                
                # End of speech silence timeout gate
                if self.silence_accumulator_ms >= self.silence_timeout_ms:
                    self.is_speech_active = False
                    self.silence_accumulator_ms = 0
                    logger.info("VAD: Speech ended detected.")
                    
        return self.is_speech_active

    def reset(self) -> None:
        self.is_speech_active = False
        self.silence_accumulator_ms = 0
        self.speech_accumulator_ms = 0
        self.noise_samples.clear()
        self.threshold = self.base_offset
        self.noise_floor = self.base_offset / 2
