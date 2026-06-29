import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

from app.voice.state import VoiceState, VoiceStateMachine
from app.voice.tts import BaseTTSProvider, TTSProviderRegistry, MockTTSProvider, TTSCoordinator
from app.voice.playback import AudioPlaybackController
from app.kernel.kernel import FridayKernel
from app.kernel.state import KernelState

@pytest.mark.anyio
async def test_voice_state_transitions():
    state_machine = VoiceStateMachine()
    assert state_machine.current_state == VoiceState.IDLE

    # Valid transitions from IDLE
    state_machine.transition_to(VoiceState.LISTENING)
    assert state_machine.current_state == VoiceState.LISTENING

    state_machine.transition_to(VoiceState.THINKING)
    assert state_machine.current_state == VoiceState.THINKING

    state_machine.transition_to(VoiceState.SPEAKING)
    assert state_machine.current_state == VoiceState.SPEAKING

    # Transition to IDLE from SPEAKING
    state_machine.transition_to(VoiceState.IDLE)
    assert state_machine.current_state == VoiceState.IDLE

    # Invalid transitions
    with pytest.raises(ValueError, match="Invalid state transition"):
        state_machine.transition_to(VoiceState.SPEAKING)  # Cannot go from IDLE to SPEAKING directly

@pytest.mark.anyio
async def test_provider_registration():
    registry = TTSProviderRegistry()
    assert registry.default_provider_name is None

    mock1 = MockTTSProvider()
    registry.register(mock1, is_default=False)
    assert registry.default_provider_name == "mock_tts"
    assert registry.get() is mock1

    class CustomTTSProvider(BaseTTSProvider):
        @property
        def name(self) -> str:
            return "custom_tts"
        async def synthesize(self, text: str):
            yield b"custom"

    custom_provider = CustomTTSProvider()
    registry.register(custom_provider, is_default=True)
    assert registry.default_provider_name == "custom_tts"
    assert registry.get() is custom_provider
    assert registry.get("mock_tts") is mock1

    assert "mock_tts" in registry.list_providers()
    assert "custom_tts" in registry.list_providers()

@pytest.mark.anyio
async def test_coordinator_initialization_and_chunking():
    registry = TTSProviderRegistry()
    mock_provider = MockTTSProvider()
    registry.register(mock_provider)

    coordinator = TTSCoordinator(registry)
    
    # Test sentence chunking output
    text_input = "Hello. This is FRIDAY! How can I help you?"
    chunks = []
    async for chunk in coordinator.synthesize_stream(text_input):
        chunks.append(chunk.decode())

    # We split by '.', '!', '?'
    # Sentences: "Hello", "This is FRIDAY", "How can I help you"
    assert chunks == ["AUDIO:Hello", "AUDIO:This is FRIDAY", "AUDIO:How can I help you"]

@pytest.mark.anyio
async def test_di_and_module_registration():
    # Reset and boot kernel
    FridayKernel.reset_instance()
    kernel = FridayKernel.get_instance()
    
    await kernel.boot()
    try:
        assert kernel.state() == KernelState.READY

        # 1. Verify DI registration
        state_machine = kernel.get_service("voice_state_machine")
        assert state_machine is not None
        assert isinstance(state_machine, VoiceStateMachine)

        tts_registry = kernel.get_service("tts_provider_registry")
        assert tts_registry is not None
        assert isinstance(tts_registry, TTSProviderRegistry)

        tts_coordinator = kernel.get_service("tts_coordinator")
        assert tts_coordinator is not None
        assert isinstance(tts_coordinator, TTSCoordinator)

        voice_manager = kernel.get_service("voice_manager")
        assert voice_manager is not None
        assert voice_manager.state_machine is state_machine
        assert voice_manager.tts_coordinator is tts_coordinator

        # 2. Verify FridayModuleRegistry contains modules
        modules = kernel._module_registry.list_modules()
        assert "voice_state_machine" in modules
        assert "tts_provider_registry" in modules
        assert "tts_coordinator" in modules
        assert "voice_manager" in modules
        
    finally:
        await kernel.shutdown()
