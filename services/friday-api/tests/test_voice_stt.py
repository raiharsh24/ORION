import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.voice.stt import MockSpeechProvider, pcm_to_wav
from app.voice.vad import calculate_rms
from app.voice.manager import VoiceSessionManager
from app.voice.events import SpeechStarted, SpeechFinalized
from app.friday.response import FridayResponse

@pytest.mark.anyio
async def test_mock_speech_provider():
    provider = MockSpeechProvider(response_text="Verify system operations")
    
    # Empty input returns empty string
    assert await provider.transcribe(b"") == ""
    
    # Silence or too short audio returns empty string
    assert await provider.transcribe(b"\x00\x00" * 5) == ""
    
    # Valid PCM input transcribes successfully
    pcm_data = b"\x00\x01" * 160  # 320 bytes (10ms)
    assert await provider.transcribe(pcm_data) == "Verify system operations"
    
    # Provider failures raise exception
    provider.failure_mode = True
    with pytest.raises(RuntimeError):
        await provider.transcribe(pcm_data)

@pytest.mark.anyio
async def test_voice_session_manager_success():
    # Setup mocks
    mock_event_bus = MagicMock()
    mock_orchestrator = AsyncMock()
    mock_response = MagicMock(spec=FridayResponse)
    mock_response.response = "Orchestrator successfully processed voice query."
    mock_orchestrator.process_query.return_value = mock_response
    
    async def mock_orchestrator_factory():
        return mock_orchestrator
        
    provider = MockSpeechProvider(response_text="List active workspaces")
    manager = VoiceSessionManager(
        event_bus=mock_event_bus,
        orchestrator_factory=mock_orchestrator_factory,
        speech_provider=provider
    )
    
    # Run audio session
    pcm_data = b"\x00\x01" * 320  # 640 bytes (20ms)
    transcript, response = await manager.process_audio_session("session-12345", pcm_data)
    
    assert transcript == "List active workspaces"
    assert response == "Orchestrator successfully processed voice query."
    
    # Check that events were published
    assert mock_event_bus.publish_background.call_count == 2
    called_topics = [args[0].topic for args, kwargs in mock_event_bus.publish_background.call_args_list]
    assert "SpeechStarted" in called_topics
    assert "SpeechFinalized" in called_topics
    
    # Check orchestrator call
    mock_orchestrator.process_query.assert_called_once_with(prompt="List active workspaces", session_id="session-12345")

@pytest.mark.anyio
async def test_voice_session_manager_empty_audio():
    mock_event_bus = MagicMock()
    mock_orchestrator = AsyncMock()
    
    async def mock_orchestrator_factory():
        return mock_orchestrator
        
    provider = MockSpeechProvider(response_text="Hello")
    manager = VoiceSessionManager(
        event_bus=mock_event_bus,
        orchestrator_factory=mock_orchestrator_factory,
        speech_provider=provider
    )
    
    # Empty audio input
    transcript, response = await manager.process_audio_session("session-12345", b"")
    assert transcript == ""
    assert response == ""
    
    # Orchestrator should not have been called
    mock_orchestrator.process_query.assert_not_called()
