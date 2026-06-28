import { useState, useEffect, useRef } from 'react';

export interface UseVoiceInputResult {
  isRecording: boolean;
  receivedBytes: number;
  error: string | null;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
}

export function useVoiceInput(wsUrl: string = 'ws://localhost:5000/ws/voice'): UseVoiceInputResult {
  const [isRecording, setIsRecording] = useState(false);
  const [receivedBytes, setReceivedBytes] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);

  const startRecording = async () => {
    setError(null);
    try {
      // 1. Initialize WebSocket connection
      const socket = new WebSocket(wsUrl);
      socket.binaryType = 'arraybuffer';
      socketRef.current = socket;

      socket.onopen = () => {
        console.log('Voice WS connection opened');
      };

      socket.onmessage = (event) => {
        try {
          const telemetry = JSON.parse(event.data);
          if (telemetry.status === 'streaming') {
            setReceivedBytes(telemetry.received_bytes);
          }
        } catch (e) {
          // Ignore binary responses or invalid JSON
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
      };

      // 2. Request user microphone permissions
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      // 3. Setup Web Audio API pipeline
      // We target 16kHz mono sampling
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
      const audioCtx = new AudioCtx({ sampleRate: 16000 });
      audioContextRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      
      // Create ScriptProcessorNode for buffer sampling
      const processor = audioCtx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (socket.readyState !== WebSocket.OPEN) return;

        // Get single channel Float32 float samples (-1.0 to 1.0)
        const inputData = e.inputBuffer.getChannelData(0);
        
        // Convert Float32 samples to Int16 PCM bytes
        const pcmBuffer = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          const s = Math.max(-1, Math.min(1, inputData[i]));
          pcmBuffer[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }

        // Send binary PCM frame over WebSocket
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
    // Stop recording state
    setIsRecording(false);

    // Release microphone track resources
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    // Disconnect processors
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }

    // Close AudioContext
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }

    // Close WebSocket connection
    if (socketRef.current) {
      if (socketRef.current.readyState === WebSocket.OPEN) {
        socketRef.current.close();
      }
      socketRef.current = null;
    }
  };

  // Clean up all resources when component unmounts
  useEffect(() => {
    return () => {
      stopRecording();
    };
  }, []);

  return {
    isRecording,
    receivedBytes,
    error,
    startRecording,
    stopRecording,
  };
}
