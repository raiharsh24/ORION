import uuid
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from app.kernel.kernel import FridayKernel
from app.voice.vad import EnergyThresholdVAD
from app.voice.wakeword import ThresholdWakeWordEngine
from app.voice.events import WakeWordDetected, VoiceStarted, VoiceEnded

MAX_RECORDING_DURATION_SECONDS = 15.0
MAX_AUDIO_BUFFER_SIZE_BYTES = 1024 * 1024  # 1MB

router = APIRouter()

@router.websocket("/ws/voice")
async def voice_websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for bi-directional streaming of raw PCM audio data,
    processing Voice Activity Detection (VAD) and Wake Word keyword matching.
    Handles graceful client disconnects, resource cleanups, and transition events.
    """
    await websocket.accept()
    logger.info("Voice WebSocket connection established.")
    
    # Resolve Kernel, EventBus, and VoiceOutputManager services
    kernel = FridayKernel.get_instance()
    event_bus = kernel.get_service("event_bus")
    voice_output_manager = kernel.get_service("voice_output_manager")
    if voice_output_manager:
        from app.voice.transport import WebSocketAudioTransport
        voice_output_manager.set_transport(WebSocketAudioTransport(websocket))
    
    # Initialize VAD and Wake Word Engines
    wakeword_engine = ThresholdWakeWordEngine()
    vad_engine = EnergyThresholdVAD()
    
    # State tracking variables
    session_state = "WAKING"  # States: "WAKING", "LISTENING"
    session_id = None
    voice_start_time = 0.0
    received_bytes = 0
    speech_started_detected = False
    
    # Sub-frame slicing parameters (mono 16kHz 16-bit PCM: 30ms = 960 bytes)
    FRAME_SIZE = 960
    FRAME_MS = 30
    audio_buffer = b""
    session_audio_buffer = b""

    try:
        while True:
            try:
                message = await websocket.receive()
            except WebSocketDisconnect:
                logger.info("Voice WebSocket: client disconnected gracefully (connection closed).")
                break
            except RuntimeError as e:
                if "disconnect message has been received" in str(e):
                    logger.info("Voice WebSocket: client disconnected (disconnect message already processed).")
                    break
                raise e

            # Handle explicit Starlette disconnect signals
            if message.get("type") == "websocket.disconnect":
                logger.info("Voice WebSocket: received disconnect control frame.")
                break

            is_bytes = "bytes" in message
            if is_bytes:
                audio_bytes = message["bytes"]
                received_bytes += len(audio_bytes)
                audio_buffer += audio_bytes
                
            elif "text" in message:
                text_cmd = message["text"]
                logger.info(f"Voice WS control message received: {text_cmd}")
                
                # Test trigger interface
                if text_cmd == "TRIGGER_WAKE_WORD":
                    if voice_output_manager:
                        await voice_output_manager.cancel_streaming()
                    wakeword_engine.trigger_manually()
                    # Trigger immediately by buffering an empty evaluations frame
                    audio_buffer += b"\x00" * FRAME_SIZE
                    
                await websocket.send_json({
                    "status": "control_ack",
                    "session_state": session_state,
                    "received_bytes": received_bytes,
                    "message": f"Processed control event: {text_cmd}"
                })
                
            # Process any buffered sub-frames (bytes or injected triggers)
            while len(audio_buffer) >= FRAME_SIZE:
                frame = audio_buffer[:FRAME_SIZE]
                audio_buffer = audio_buffer[FRAME_SIZE:]
                
                if session_state == "WAKING":
                    # Check if keyword is matched
                    if wakeword_engine.detect(frame):
                        session_id = str(uuid.uuid4())
                        logger.info(f"WakeWord: Phrase detected. Initializing voice session '{session_id}'")
                        
                        # Broadcast WakeWordDetected
                        if event_bus:
                            event_bus.publish_background(WakeWordDetected(
                                phrase="FRIDAY",
                                session_id=session_id
                            ))
                        
                        # Transition state to LISTENING
                        session_state = "LISTENING"
                        voice_start_time = asyncio.get_event_loop().time()
                        speech_started_detected = False
                        session_audio_buffer = b""
                        
                        # Broadcast VoiceStarted
                        if event_bus:
                            event_bus.publish_background(VoiceStarted(session_id=session_id))
                            
                        await websocket.send_json({
                            "status": "wake_word_detected",
                            "session_id": session_id
                        })
                        vad_engine.reset()
                        
                elif session_state == "LISTENING":
                    is_speech = vad_engine.process_frame(frame, FRAME_MS)
                    
                    if is_speech:
                        if voice_output_manager:
                            await voice_output_manager.cancel_streaming()
                        speech_started_detected = True
                        
                    # Accumulate speech samples once speech activity starts
                    if speech_started_detected:
                        session_audio_buffer += frame
                        
                    limit_exceeded = False
                    if speech_started_detected:
                        current_duration = asyncio.get_event_loop().time() - voice_start_time
                        current_size = len(session_audio_buffer)
                        if current_duration > MAX_RECORDING_DURATION_SECONDS:
                            limit_exceeded = True
                            logger.warning(f"Voice session buffer duration limit exceeded ({current_duration:.2f}s > {MAX_RECORDING_DURATION_SECONDS}s). Gracefully finalizing.")
                        elif current_size > MAX_AUDIO_BUFFER_SIZE_BYTES:
                            limit_exceeded = True
                            logger.warning(f"Voice session buffer size limit exceeded ({current_size} bytes > {MAX_AUDIO_BUFFER_SIZE_BYTES} bytes). Gracefully finalizing.")

                    # End of speech transition (VAD falls silent or limit exceeded after user starts talking)
                    if speech_started_detected and (not is_speech or limit_exceeded):
                        duration = asyncio.get_event_loop().time() - voice_start_time
                        logger.info(f"VAD: Speech completed. Duration: {duration:.2f}s (limit exceeded: {limit_exceeded})")
                        
                        # Broadcast VoiceEnded
                        if event_bus:
                            event_bus.publish_background(VoiceEnded(
                                session_id=session_id,
                                duration_seconds=duration
                            ))
                            
                        await websocket.send_json({
                            "status": "speech_ended",
                            "session_id": session_id,
                            "duration_seconds": duration
                        })
                        
                        # Process speech-to-text and query execution
                        voice_manager = kernel.get_service("voice_manager")
                        if voice_manager:
                            try:
                                transcript, response_text = await voice_manager.process_audio_session(
                                    session_id, session_audio_buffer
                                )
                                logger.info(f"Voice query processed. Transcript: '{transcript}', Response: '{response_text}'")
                                
                                await websocket.send_json({
                                    "status": "speech_finalized",
                                    "session_id": session_id,
                                    "transcript": transcript,
                                    "response": response_text
                                })
                            except Exception as e:
                                logger.error(f"Voice session query processing failed: {e}")
                                await websocket.send_json({
                                    "status": "error",
                                    "session_id": session_id,
                                    "message": f"Query execution failed: {str(e)}"
                                })
                        
                        # Reset engines and loop back to WAKING
                        session_state = "WAKING"
                        session_id = None
                        speech_started_detected = False
                        session_audio_buffer = b""
                        wakeword_engine.reset()
                        vad_engine.reset()
                        
            # Send periodic telemetry status frames back to client if audio bytes were received
            if is_bytes:
                await websocket.send_json({
                    "status": "streaming",
                    "session_state": session_state,
                    "received_bytes": received_bytes,
                    "chunk_size": len(audio_bytes)
                })
                
    except Exception as e:
        logger.error(f"Voice WebSocket unexpected error during session processing: {e}")
        
    finally:
        # Release all buffers, queues, and resources
        audio_buffer = b""
        session_audio_buffer = b""
        wakeword_engine.reset()
        vad_engine.reset()
        if voice_output_manager:
            await voice_output_manager.shutdown()
        
        # Publish VoiceEnded if connection is terminated during an active session
        if session_state == "LISTENING" and session_id:
            duration = asyncio.get_event_loop().time() - voice_start_time
            logger.info(f"Voice WebSocket: session ended on client disconnect. Duration: {duration:.2f}s")
            if event_bus:
                event_bus.publish_background(VoiceEnded(
                    session_id=session_id,
                    duration_seconds=duration
                ))
            session_state = "WAKING"
            session_id = None
