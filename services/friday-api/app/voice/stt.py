import struct
from loguru import logger

class BaseSpeechProvider:
    """
    Interface for Speech-to-Text translation providers.
    """
    async def transcribe(self, audio_data: bytes) -> str:
        """
        Transcribes the raw 16kHz mono 16-bit PCM bytes to text.
        """
        raise NotImplementedError


def pcm_to_wav(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, bit_depth: int = 16) -> bytes:
    """
    Prepends a standard 44-byte RIFF/WAVE header to raw PCM bytes.
    """
    num_samples = len(pcm_data) // (bit_depth // 8)
    data_chunk_size = num_samples * channels * (bit_depth // 8)
    riff_chunk_size = 36 + data_chunk_size
    
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        riff_chunk_size,
        b"WAVE",
        b"fmt ",
        16,                # Subchunk1Size
        1,                 # AudioFormat (1 = PCM)
        channels,          # NumChannels
        sample_rate,       # SampleRate
        sample_rate * channels * (bit_depth // 8),  # ByteRate
        channels * (bit_depth // 8),  # BlockAlign
        bit_depth,         # BitsPerSample
        b"data",
        data_chunk_size
    )
    return header + pcm_data


class GeminiSpeechProvider(BaseSpeechProvider):
    """
    STT provider using the official Google Gemini SDK.
    Inherits model configurations from Friday's LLMRouter/GeminiAdapter.
    """
    def __init__(self, gemini_adapter) -> None:
        self.adapter = gemini_adapter

    async def transcribe(self, audio_data: bytes) -> str:
        if not audio_data or len(audio_data) < 320:  # Less than 10ms of audio
            return ""
            
        wav_data = pcm_to_wav(audio_data)
        model = self.adapter._get_model()
        
        prompt = (
            "Transcribe the spoken audio accurately. Output only the transcript text, nothing else. "
            "If there is no speech or only background static, output empty string."
        )
        
        try:
            # Send WAV binary data directly inline to the model
            response = await model.generate_content_async([
                {
                    "mime_type": "audio/wav",
                    "data": wav_data
                },
                prompt
            ])
            transcript = response.text.strip() if response.text else ""
            return transcript
        except Exception as e:
            logger.error(f"Gemini Speech STT failed: {e}")
            raise e


class MockSpeechProvider(BaseSpeechProvider):
    """
    Mock speech provider for testing and validation.
    """
    def __init__(self, response_text: str = "Hello FRIDAY") -> None:
        self.response_text = response_text
        self.failure_mode = False

    async def transcribe(self, audio_data: bytes) -> str:
        if self.failure_mode:
            raise RuntimeError("Mock STT Provider Failure simulation.")
        if not audio_data or len(audio_data) < 320:
            return ""
        return self.response_text
