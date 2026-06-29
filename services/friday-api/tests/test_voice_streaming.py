import pytest
import asyncio
from typing import AsyncIterator
from unittest.mock import MagicMock

from app.voice.tts import BaseTTSProvider, TTSProviderRegistry, TTSCoordinator
from app.voice.transport import AudioStreamTransport
from app.voice.output_manager import VoiceOutputManager
from app.kernel.kernel import FridayKernel
from app.kernel.state import KernelState

class MockStreamTransport(AudioStreamTransport):
    def __init__(self) -> None:
        self.sent_chunks = []
        self.closed = False

    async def send_audio_chunk(self, chunk: bytes) -> None:
        self.sent_chunks.append(chunk)

    async def close(self) -> None:
        self.closed = True

class SlowTTSProvider(BaseTTSProvider):
    def __init__(self) -> None:
        self.step = 0
        self.cancelled = False

    @property
    def name(self) -> str:
        return "slow_tts"

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        try:
            for i in range(5):
                await asyncio.sleep(0.02)
                yield f"CHUNK-{i}".encode()
                self.step += 1
        except asyncio.CancelledError:
            self.cancelled = True
            raise

@pytest.mark.anyio
async def test_voice_streaming_pipelined_and_ordered():
    registry = TTSProviderRegistry()
    slow_prov = SlowTTSProvider()
    registry.register(slow_prov, is_default=True)
    coordinator = TTSCoordinator(registry)
    output_manager = VoiceOutputManager(coordinator)
    
    transport = MockStreamTransport()
    output_manager.set_transport(transport)

    # Start streaming
    await output_manager.start_streaming("This is a slow test sentence.")
    
    # Wait for the background task to run
    await asyncio.sleep(0.15)
    
    # Verify chunks were received in order and immediately (pipelined)
    assert len(transport.sent_chunks) == 5
    assert transport.sent_chunks == [
        b"CHUNK-0", b"CHUNK-1", b"CHUNK-2", b"CHUNK-3", b"CHUNK-4"
    ]

@pytest.mark.anyio
async def test_voice_streaming_cancellation():
    registry = TTSProviderRegistry()
    slow_prov = SlowTTSProvider()
    registry.register(slow_prov, is_default=True)
    coordinator = TTSCoordinator(registry)
    output_manager = VoiceOutputManager(coordinator)
    
    transport = MockStreamTransport()
    output_manager.set_transport(transport)

    # Start streaming
    await output_manager.start_streaming("This is a cancellation test sentence.")
    
    # Wait for a couple chunks
    await asyncio.sleep(0.05)
    
    # Cancel streaming
    await output_manager.cancel_streaming()
    
    # Keep wait to ensure it stopped
    await asyncio.sleep(0.05)

    # Verify stream stopped midway
    assert len(transport.sent_chunks) < 5
    assert slow_prov.cancelled is True

@pytest.mark.anyio
async def test_voice_streaming_transport_cleanup():
    registry = TTSProviderRegistry()
    slow_prov = SlowTTSProvider()
    registry.register(slow_prov, is_default=True)
    coordinator = TTSCoordinator(registry)
    output_manager = VoiceOutputManager(coordinator)
    
    transport = MockStreamTransport()
    output_manager.set_transport(transport)

    await output_manager.shutdown()
    
    assert transport.closed is True
    assert output_manager._transport is None

@pytest.mark.anyio
async def test_voice_streaming_error_propagation():
    class CrashingTTSProvider(BaseTTSProvider):
        @property
        def name(self) -> str:
            return "crashing_tts"
        async def synthesize(self, text: str) -> AsyncIterator[bytes]:
            yield b"START"
            raise RuntimeError("TTS error crash")

    registry = TTSProviderRegistry()
    crash_prov = CrashingTTSProvider()
    registry.register(crash_prov, is_default=True)
    coordinator = TTSCoordinator(registry)
    output_manager = VoiceOutputManager(coordinator)
    
    transport = MockStreamTransport()
    output_manager.set_transport(transport)

    # Should raise error during stream execution background task wait
    await output_manager.start_streaming("Test crash.")
    
    # Wait for background task to crash
    await asyncio.sleep(0.05)

    assert len(transport.sent_chunks) == 1
    assert transport.sent_chunks[0] == b"START"
    assert output_manager.last_error is not None
    assert isinstance(output_manager.last_error, RuntimeError)
    assert str(output_manager.last_error) == "TTS error crash"

@pytest.mark.anyio
async def test_kernel_integration_di_and_modules():
    FridayKernel.reset_instance()
    kernel = FridayKernel.get_instance()
    await kernel.boot()
    try:
        # Check DI singletons
        output_manager = kernel.get_service("voice_output_manager")
        assert output_manager is not None
        assert isinstance(output_manager, VoiceOutputManager)

        voice_manager = kernel.get_service("voice_manager")
        assert voice_manager.voice_output_manager is output_manager

        # Check module registry lists it
        assert "voice_output_manager" in kernel._module_registry.list_modules()
    finally:
        await kernel.shutdown()
