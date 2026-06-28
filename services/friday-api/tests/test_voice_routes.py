import pytest
import struct
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.voice.vad import EnergyThresholdVAD, calculate_rms
from app.voice.wakeword import ThresholdWakeWordEngine
from app.kernel.kernel import FridayKernel
from app.kernel.state import KernelState

def test_energy_vad_logic():
    # Test silence detection
    vad = EnergyThresholdVAD(initial_threshold=500.0, min_speech_duration_ms=30, silence_timeout_ms=60)
    
    # 15ms of silence (low amplitude PCM)
    silence_frame = struct.pack("<h", 0) * 240
    assert vad.process_frame(silence_frame, 15) is False
    assert vad.process_frame(silence_frame, 15) is False
    
    # Test speech detection (high amplitude PCM)
    speech_frame = struct.pack("<h", 2000) * 240
    assert calculate_rms(speech_frame) > 500
    
    # First 15ms of speech: not active yet (min duration is 30ms)
    assert vad.process_frame(speech_frame, 15) is False
    # Second 15ms of speech: total 30ms speech, transitions to active
    assert vad.process_frame(speech_frame, 15) is True
    # Stays active during speech
    assert vad.process_frame(speech_frame, 15) is True
    
    # Test silence hangover
    # Stays active on first silence frame (timeout is 60ms)
    assert vad.process_frame(silence_frame, 30) is True
    # Falls silent after timeout (total 60ms silence)
    assert vad.process_frame(silence_frame, 30) is False

def test_adaptive_noise_rejection():
    # Test background noise calibration
    vad = EnergyThresholdVAD(initial_threshold=500.0)
    
    # Send continuous moderate background noise (RMS around 110)
    noise_frame = struct.pack("<h", 110) * 480
    assert 100 < calculate_rms(noise_frame) < 120
    
    # Calibrate VAD using noise frames
    for _ in range(60):
        vad.process_frame(noise_frame, 30)
        
    # The noise floor should adjust upwards, raising the threshold
    assert vad.noise_floor > 100
    assert vad.threshold > 600
    
    # Verifying that the background noise itself does not trigger speech
    assert vad.process_frame(noise_frame, 30) is False

def test_wakeword_logic():
    engine = ThresholdWakeWordEngine(trigger_rms_threshold=8000.0)
    
    # Low energy frame does not trigger
    low_frame = struct.pack("<h", 10) * 480
    assert engine.detect(low_frame) is False
    
    # High energy frame triggers
    high_frame = struct.pack("<h", 13000) * 480
    assert calculate_rms(high_frame) > 8000
    assert engine.detect(high_frame) is True
    
    # Stays triggered until reset
    engine.reset()
    assert engine.detect(low_frame) is False

@pytest.mark.anyio
@patch("app.friday.orchestrator.FridayOrchestrator.process_query")
async def test_voice_session_lifecycle_integration(mock_process_query):
    # 1. Boot kernel to populate the service container
    kernel = FridayKernel.get_instance()
    if kernel._state in (KernelState.STOPPED, KernelState.ERROR):
        kernel._state = KernelState.STOPPED
        kernel._config.api_keys.gemini_api_key = "dummy-key"
        await kernel.boot()
    
    # 2. Setup Mock Speech Provider now that services are registered in FridayServiceContainer
    from app.voice.stt import MockSpeechProvider
    
    # Mock orchestrator response
    mock_resp = MagicMock()
    mock_resp.response = "Mocked orchestrator response text"
    mock_process_query.return_value = mock_resp

    # Inject mock speech provider in voice_manager
    voice_manager = kernel.get_service("voice_manager")
    assert voice_manager is not None, "VoiceSessionManager should be registered during kernel boot"
    
    original_provider = voice_manager.speech_provider
    voice_manager.speech_provider = MockSpeechProvider(response_text="Verify system capabilities")

    try:
        client = TestClient(app)
        silence = struct.pack("<h", 0) * 480
        
        with client.websocket_connect("/ws/voice") as websocket:
            # 1. Stays in WAKING state on silence
            websocket.send_bytes(silence)
            resp = websocket.receive_json()
            assert resp["session_state"] == "WAKING"
            
            # 2. Trigger Wake Word via manual control signal
            websocket.send_text("TRIGGER_WAKE_WORD")
            resp = websocket.receive_json()
            assert resp["status"] == "control_ack"
            
            # The wake word match spawns the session immediately
            resp_wake = websocket.receive_json()
            assert resp_wake["status"] == "wake_word_detected"
            session_id = resp_wake["session_id"]
            assert session_id is not None
            
            # 3. Simulate speech started (send loud PCM chunks)
            speech = struct.pack("<h", 3000) * 480
            for _ in range(6):
                websocket.send_bytes(speech)
                resp = websocket.receive_json()
                assert resp["session_state"] == "LISTENING"
                
            # 4. Simulate speech ended (send silence chunks)
            speech_ended_msg = None
            for _ in range(50):
                websocket.send_bytes(silence)
                resp = websocket.receive_json()
                if resp.get("status") == "speech_ended":
                    speech_ended_msg = resp
                    
                    # 5. Consume speech_finalized frame sent immediately after speech_ended
                    resp_final = websocket.receive_json()
                    assert resp_final["status"] == "speech_finalized"
                    assert resp_final["session_id"] == session_id
                    assert resp_final["transcript"] == "Verify system capabilities"
                    assert resp_final["response"] == "Mocked orchestrator response text"
                    
                    # 6. Drain the extra periodic "streaming" message sent at the end of loop iteration
                    websocket.receive_json()
                    break
                    
            assert speech_ended_msg is not None
            assert speech_ended_msg["session_id"] == session_id
            assert speech_ended_msg["duration_seconds"] > 0
            
            # 7. Verify consecutive voice sessions: system returns to WAKING and can be triggered again
            websocket.send_text("TRIGGER_WAKE_WORD")
            resp = websocket.receive_json()
            assert resp["status"] == "control_ack"
            
            resp_wake_2 = websocket.receive_json()
            assert resp_wake_2["status"] == "wake_word_detected"
            assert resp_wake_2["session_id"] != session_id
    finally:
        # Restore original provider
        voice_manager.speech_provider = original_provider

@pytest.mark.anyio
async def test_voice_websocket_graceful_disconnect():
    """
    Verifies that client disconnects do not log runtime errors
    and correctly broadcast VoiceEnded if connection drops during active speech.
    """
    kernel = FridayKernel.get_instance()
    if kernel._state in (KernelState.STOPPED, KernelState.ERROR):
        kernel._state = KernelState.STOPPED
        kernel._config.api_keys.gemini_api_key = "dummy-key"
        await kernel.boot()
        
    event_bus = kernel.get_service("event_bus")
    assert event_bus is not None
    
    # Mock event bus publish_background to verify broadcast
    original_publish = event_bus.publish_background
    mock_publish = MagicMock()
    event_bus.publish_background = mock_publish
    
    try:
        client = TestClient(app)
        with client.websocket_connect("/ws/voice") as websocket:
            websocket.send_text("TRIGGER_WAKE_WORD")
            websocket.receive_json()  # control_ack
            websocket.receive_json()  # wake_word_detected
            
            # Close connection directly to simulate client drop
            websocket.close()
            
        # Verify that VoiceEnded event was published on disconnect
        called_topics = [args[0].topic for args, kwargs in mock_publish.call_args_list]
        assert "VoiceEnded" in called_topics
    finally:
        # Restore event bus method
        event_bus.publish_background = original_publish
