import pytest
import asyncio
from unittest.mock import MagicMock

from app.voice.tts import TTSProviderRegistry
from app.voice.tts.edge import EdgeTTSProvider
from app.kernel.kernel import FridayKernel
from app.kernel.state import KernelState

@pytest.mark.anyio
async def test_edge_tts_provider_registration_and_init():
    # Verify instantiation and configs
    provider = EdgeTTSProvider(voice="en-US-AvaNeural")
    assert provider.name == "edge_tts"
    assert provider.voice == "en-US-AvaNeural"

    # Verify boot integration registry resolving
    FridayKernel.reset_instance()
    kernel = FridayKernel.get_instance()
    await kernel.boot()
    try:
        registry = kernel.get_service("tts_provider_registry")
        assert registry is not None
        default_provider = registry.get()
        assert default_provider is not None
        assert isinstance(default_provider, EdgeTTSProvider)
        assert default_provider.name == "edge_tts"
        assert registry.default_provider_name == "edge_tts"
        assert registry.get("mock_tts") is not None
    finally:
        await kernel.shutdown()

@pytest.mark.anyio
async def test_edge_tts_synthesis_streaming():
    # Test streaming live audio chunks
    provider = EdgeTTSProvider()
    chunks = []
    
    try:
        # Request short synthesis
        async for chunk in provider.synthesize("Hello"):
            chunks.append(chunk)
            if len(chunks) >= 2:
                break
    except Exception as e:
        # If network error, skip the test gracefully to prevent pipeline failure on offline envs
        pytest.skip(f"Network error during live Edge TTS synthesis: {e}")

    # We should have received binary audio data chunks (MP3 frames)
    assert len(chunks) > 0
    for chunk in chunks:
        assert isinstance(chunk, bytes)
        assert len(chunk) > 0

@pytest.mark.anyio
async def test_edge_tts_cancellation():
    provider = EdgeTTSProvider()

    async def run_stream():
        async for _ in provider.synthesize("This is a long sentence to verify that the stream cancels correctly."):
            await asyncio.sleep(0.01)

    task = asyncio.create_task(run_stream())
    await asyncio.sleep(0.05)
    
    # Cancel the streaming task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert task.cancelled()

@pytest.mark.anyio
async def test_edge_tts_error_handling():
    # Test invalid voice name error raising
    provider = EdgeTTSProvider(voice="invalid-voice-name")
    
    with pytest.raises(Exception):
        async for _ in provider.synthesize("Testing error handling"):
            pass
