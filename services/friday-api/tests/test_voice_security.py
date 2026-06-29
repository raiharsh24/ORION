import pytest
import struct
import asyncio
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.kernel.kernel import FridayKernel
from app.kernel.state import KernelState
import app.api.voice as voice_module

@pytest.mark.anyio
@patch("app.friday.orchestrator.FridayOrchestrator.process_query")
async def test_voice_security_limits(mock_process_query):
    # Set small limits for testing to trigger limit handlers immediately
    original_duration_limit = voice_module.MAX_RECORDING_DURATION_SECONDS
    original_size_limit = voice_module.MAX_AUDIO_BUFFER_SIZE_BYTES
    
    voice_module.MAX_RECORDING_DURATION_SECONDS = 0.4
    voice_module.MAX_AUDIO_BUFFER_SIZE_BYTES = 2000 # 2KB

    # Boot kernel
    kernel = FridayKernel.get_instance()
    if kernel._state in (KernelState.STOPPED, KernelState.ERROR):
        kernel._state = KernelState.STOPPED
        kernel._config.api_keys.gemini_api_key = "dummy-key"
        await kernel.boot()

    # Mock Speech Provider
    from app.voice.stt import MockSpeechProvider
    mock_resp = MagicMock()
    mock_resp.response = "Limit hit response"
    mock_process_query.return_value = mock_resp

    voice_manager = kernel.get_service("voice_manager")
    original_provider = voice_manager.speech_provider
    voice_manager.speech_provider = MockSpeechProvider(response_text="Limit test")

    try:
        client = TestClient(app)
        
        # Test 1: Oversized memory size limit exceeded
        print("\n[DEBUG] Starting Test 1 (Oversized memory)...")
        with client.websocket_connect("/ws/voice") as websocket:
            websocket.send_text("TRIGGER_WAKE_WORD")
            websocket.receive_json()  # control_ack
            websocket.receive_json()  # wake_word_detected
            
            speech_frame = struct.pack("<h", 3000) * 480 # 960 bytes
            
            # Send 5 frames to trigger VAD speech active (150ms minimum duration threshold)
            for i in range(5):
                websocket.send_bytes(speech_frame)
                resp = websocket.receive_json()
                assert resp["session_state"] == "LISTENING"
            
            # Send 6th frame
            websocket.send_bytes(speech_frame)
            resp = websocket.receive_json()
            assert resp["session_state"] == "LISTENING"

            # Send 7th frame -> exceeds 2000 bytes session_audio_buffer size limit!
            websocket.send_bytes(speech_frame)
            
            # Read responses
            ended_msg = None
            finalized_msg = None
            for i in range(5):
                resp = websocket.receive_json()
                if resp.get("status") == "speech_ended":
                    ended_msg = resp
                elif resp.get("status") == "speech_finalized":
                    finalized_msg = resp
                    break
            
            assert ended_msg is not None
            assert finalized_msg is not None
            assert finalized_msg["transcript"] == "Limit test"

        # Test 2: Duration limit exceeded
        print("\n[DEBUG] Starting Test 2 (Duration limit)...")
        with client.websocket_connect("/ws/voice") as websocket:
            websocket.send_text("TRIGGER_WAKE_WORD")
            websocket.receive_json()  # control_ack
            websocket.receive_json()  # wake_word_detected
            
            # Send 5 frames to trigger VAD speech active (150ms minimum duration threshold)
            for i in range(5):
                websocket.send_bytes(speech_frame)
                websocket.receive_json()

            # Wait for duration limit (0.4s) to pass from voice_start_time
            await asyncio.sleep(0.5)

            # Send 6th frame, triggering duration limit check!
            websocket.send_bytes(speech_frame)
            
            ended_msg = None
            finalized_msg = None
            for i in range(5):
                resp = websocket.receive_json()
                if resp.get("status") == "speech_ended":
                    ended_msg = resp
                elif resp.get("status") == "speech_finalized":
                    finalized_msg = resp
                    break
            
            assert ended_msg is not None
            assert finalized_msg is not None
            assert finalized_msg["transcript"] == "Limit test"

        # Test 3: Normal conversation (no limit hit, ended by VAD silence)
        print("\n[DEBUG] Starting Test 3 (Normal conversation)...")
        with client.websocket_connect("/ws/voice") as websocket:
            websocket.send_text("TRIGGER_WAKE_WORD")
            websocket.receive_json()  # control_ack
            websocket.receive_json()  # wake_word_detected
            
            # Send 5 frames to trigger VAD speech active
            for i in range(5):
                websocket.send_bytes(speech_frame)
                websocket.receive_json()

            # Send silence/no speech to finalize naturally
            silence = struct.pack("<h", 0) * 480
            ended_msg = None
            for _ in range(50):
                websocket.send_bytes(silence)
                resp = websocket.receive_json()
                if resp.get("status") == "speech_ended":
                    ended_msg = resp
                    break
            assert ended_msg is not None

        # Test 4: Multiple reconnects
        print("\n[DEBUG] Starting Test 4 (Multiple reconnects)...")
        for _ in range(3):
            with client.websocket_connect("/ws/voice") as websocket:
                websocket.send_text("TRIGGER_WAKE_WORD")
                websocket.receive_json()  # control_ack
                websocket.receive_json()  # wake_word_detected

    finally:
        voice_module.MAX_RECORDING_DURATION_SECONDS = original_duration_limit
        voice_module.MAX_AUDIO_BUFFER_SIZE_BYTES = original_size_limit
        voice_manager.speech_provider = original_provider
