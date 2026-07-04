import { useState, useEffect, useRef } from 'react';
import { WebAudioDecoder } from '../../../services/audio/decoder';
import { AudioQueue } from '../../../services/audio/queue';
import { PlaybackManager } from '../../../services/audio/playback';

export type VoiceState = 'idle' | 'waking' | 'listening' | 'processing' | 'speaking';

export interface UseVoiceInputResult {
  isRecording: boolean;
  receivedBytes: number;
  error: string | null;
  voiceState: VoiceState;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  triggerWakeWord: () => void;
}

export interface UseVoiceInputOptions {
  onWakeWordDetected?: (sessionId: string) => void;
  onSpeechEnded?: (sessionId: string, durationSeconds: number) => void;
  onSpeechFinalized?: (sessionId: string, transcript: string, response: string) => void;
  onError?: (message: string) => void;
}

export function useVoiceInput(
  wsUrl: string = 'ws://localhost:5000/ws/voice',
  options?: UseVoiceInputOptions
): UseVoiceInputResult {
  const [isRecording, setIsRecording] = useState(false);
  const [receivedBytes, setReceivedBytes] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');

  const socketRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const playbackManagerRef = useRef<PlaybackManager | null>(null);
  const silenceTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const triggerWakeWord = () => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send('TRIGGER_WAKE_WORD');
    }
  };

  const startRecording = async () => {
    setError(null);
    setReceivedBytes(0);
    try {
      // 1. Initialize WebSocket connection
      const socket = new WebSocket(wsUrl);
      socket.binaryType = 'arraybuffer';
      socketRef.current = socket;

      socket.onopen = () => {
        console.log('Voice WS connection opened');
        setVoiceState('waking');
      };

      socket.onmessage = async (event) => {
        if (event.data instanceof ArrayBuffer) {
          // This is audio feedback (TTS)
          setVoiceState('speaking');
          if (silenceTimeoutRef.current) {
            clearTimeout(silenceTimeoutRef.current);
          }
          silenceTimeoutRef.current = setTimeout(() => {
            setVoiceState('waking');
          }, 1500);

          if (playbackManagerRef.current) {
            playbackManagerRef.current.handleChunk(event.data).catch((e) => {
              console.error("PlaybackManager chunk error:", e);
            });
          }
        } else {
          try {
            const telemetry = JSON.parse(event.data);
            if (telemetry.status === 'streaming') {
              setReceivedBytes(telemetry.received_bytes);
              if (voiceState !== 'speaking') {
                if (telemetry.session_state === 'WAKING') {
                  setVoiceState('waking');
                } else if (telemetry.session_state === 'LISTENING') {
                  setVoiceState('listening');
                }
              }
            } else if (telemetry.status === 'wake_word_detected') {
              setVoiceState('listening');
              options?.onWakeWordDetected?.(telemetry.session_id);
            } else if (telemetry.status === 'speech_ended') {
              setVoiceState('processing');
              options?.onSpeechEnded?.(telemetry.session_id, telemetry.duration_seconds);
            } else if (telemetry.status === 'speech_finalized') {
              setVoiceState('waking');
              options?.onSpeechFinalized?.(
                telemetry.session_id,
                telemetry.transcript,
                telemetry.response
              );
            } else if (telemetry.status === 'error') {
              setVoiceState('waking');
              setError(telemetry.message);
              options?.onError?.(telemetry.message);
            }
          } catch (e) {
            // Ignore binary responses or invalid JSON
          }
        }
      };

      socket.onerror = (e) => {
        console.error('Voice WS connection error:', e);
        setError('WebSocket connection error.');
        stopRecording();
      };

      socket.onclose = () => {
        console.log('Voice WS connection closed');
        setIsRecording(false);
        setVoiceState('idle');
      };

      // 2. Request user microphone permissions
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      // 3. Setup Web Audio API pipeline (16kHz mono PCM)
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      const audioCtx = new AudioCtx({ sampleRate: 16000 });
      audioContextRef.current = audioCtx;

      // Setup audio playback components
      const decoder = new WebAudioDecoder(audioCtx);
      const queue = new AudioQueue();
      const playbackManager = new PlaybackManager(audioCtx, decoder, queue, 1);
      playbackManagerRef.current = playbackManager;

      const source = audioCtx.createMediaStreamSource(stream);
      const processor = audioCtx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (socket.readyState !== WebSocket.OPEN) return;

        const inputData = e.inputBuffer.getChannelData(0);
        const pcmBuffer = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]));
          pcmBuffer[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }

        socket.send(pcmBuffer.buffer);
      };

      source.connect(processor);
      processor.connect(audioCtx.destination);

      setIsRecording(true);
    } catch (err: any) {
      console.error('Failed to start voice input capture:', err);
      setError(err.message || 'Microphone capture failed.');
      stopRecording();
    }
  };

  const stopRecording = () => {
    setIsRecording(false);
    setVoiceState('idle');

    if (silenceTimeoutRef.current) {
      clearTimeout(silenceTimeoutRef.current);
      silenceTimeoutRef.current = null;
    }

    if (playbackManagerRef.current) {
      playbackManagerRef.current.flush();
      playbackManagerRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }

    if (socketRef.current) {
      if (socketRef.current.readyState === WebSocket.OPEN) {
        socketRef.current.close();
      }
      socketRef.current = null;
    }
  };

  useEffect(() => {
    return () => {
      stopRecording();
    };
  }, []);

  return {
    isRecording,
    receivedBytes,
    error,
    voiceState,
    startRecording,
    stopRecording,
    triggerWakeWord,
  };
}
