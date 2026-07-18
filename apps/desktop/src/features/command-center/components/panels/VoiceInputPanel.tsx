import React, { useEffect, useState, useRef } from 'react';
import { Mic, MicOff, Check } from 'lucide-react';
import { GlassPanel } from './GlassPanel';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';
import { useAiStateStore } from '../../sync/useAiStateStore';

const LIFECYCLE_STEPS = [
  { label: 'Listening', color: 'text-cyan-glow', border: 'border-cyan-border/40', activeGlow: 'rgba(0, 242, 254, 0.45)' },
  { label: 'Transcribing', color: 'text-purple-400', border: 'border-purple-500/30', activeGlow: 'rgba(167, 139, 250, 0.45)' },
  { label: 'Thinking', color: 'text-orange-glow', border: 'border-orange-500/30', activeGlow: 'rgba(255, 138, 61, 0.45)' },
  { label: 'Planning', color: 'text-blue-400', border: 'border-blue-500/30', activeGlow: 'rgba(59, 130, 246, 0.45)' },
  { label: 'Executing', color: 'text-emerald-400', border: 'border-emerald-500/30', activeGlow: 'rgba(16, 185, 129, 0.45)' },
  { label: 'Speaking', color: 'text-cyan-glow', border: 'border-cyan-border/40', activeGlow: 'rgba(0, 242, 254, 0.45)' },
];

export const VoiceInputPanel: React.FC<{ className?: string }> = ({ className }) => {
  const listening = useCommandCenterStore((s) => s.listening);
  const voiceLevel = useCommandCenterStore((s) => s.voiceLevel);
  const toggleListening = useCommandCenterStore((s) => s.toggleListening);
  const aiState = useAiStateStore((s) => s.state);
  const transition = useAiStateStore((s) => s.transition);

  // Local state tracking the lifecycle stepper index
  const [activeStep, setActiveStep] = useState<number>(-1);
  const [phase, setPhase] = useState(0);
  const prevAiState = useRef(aiState);

  // Synchronize stepper along with aiState changes with realistic animations
  useEffect(() => {
    let timer1: any;
    let timer2: any;

    if (aiState === 'listening') {
      setActiveStep(0); // Listening
    } else if (aiState === 'thinking') {
      // Transition through Transcribing (1) before showing Thinking (2)
      setActiveStep(1); // Transcribing
      timer1 = setTimeout(() => {
        setActiveStep(2); // Thinking
        timer2 = setTimeout(() => {
          setActiveStep(3); // Planning
        }, 1400);
      }, 1200);
    } else if (aiState === 'executing' || aiState === 'tool' || aiState === 'workflow') {
      setActiveStep(4); // Executing
    } else if (aiState === 'speaking') {
      setActiveStep(5); // Speaking
    } else if (aiState === 'idle') {
      // If we finished speaking, hold completed state for 2s then turn off
      if (prevAiState.current === 'speaking') {
        setActiveStep(5);
        timer1 = setTimeout(() => {
          setActiveStep(-1);
        }, 2000);
      } else {
        setActiveStep(-1);
      }
    }

    prevAiState.current = aiState;
    return () => {
      clearTimeout(timer1);
      clearTimeout(timer2);
    };
  }, [aiState]);

  // Audio wave animation driver loop
  useEffect(() => {
    let frame: number;
    const animate = () => {
      setPhase((p) => (p + 0.15) % (Math.PI * 2));
      frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, []);

  const handleMicClick = () => {
    toggleListening();
    const nextState = !listening ? 'listening' : 'idle';
    transition(nextState);
  };

  // Wave path generator that modulates parameters based on lifecycle stage
  const generateWavePath = (offset: number, scale: number, count = 30) => {
    const points: string[] = [];
    
    // Default values
    let amplitude = 2;
    let frequency = 4.5;
    let isSquare = false;
    let isNoise = false;

    if (activeStep === 0) { // Listening
      amplitude = 18 * (0.2 + voiceLevel * 0.8);
      frequency = 4.5;
    } else if (activeStep === 1) { // Transcribing
      amplitude = 6;
      frequency = 8.0;
    } else if (activeStep === 2) { // Thinking
      amplitude = 12;
      frequency = 2.0;
    } else if (activeStep === 3) { // Planning
      amplitude = 10;
      frequency = 3.0;
      isSquare = true;
    } else if (activeStep === 4) { // Executing
      amplitude = 16;
      frequency = 12.0;
      isNoise = true;
    } else if (activeStep === 5) { // Speaking
      // Modulate with wave cycles
      amplitude = 14 * (0.3 + Math.sin(phase * 1.5) * 0.6);
      frequency = 5.0;
    }

    for (let i = 0; i <= count; i++) {
      const ratio = i / count;
      const x = ratio * 100;
      const envelope = Math.sin(ratio * Math.PI); // Pinches waves at borders
      
      let waveVal = Math.sin(ratio * Math.PI * frequency + phase + offset);
      if (isSquare) {
        waveVal = waveVal >= 0 ? 1 : -1;
      } else if (isNoise) {
        waveVal = waveVal * 0.6 + (Math.random() - 0.5) * 0.8;
      }

      const y = 25 + waveVal * amplitude * envelope * scale;
      points.push(`${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`);
    }
    return points.join(' ');
  };

  // Get current wave color
  const getWaveColor = () => {
    if (activeStep === 1) return '#c084fc'; // Purple
    if (activeStep === 2) return '#ff8a3d'; // Orange
    if (activeStep === 3) return '#60a5fa'; // Blue
    if (activeStep === 4) return '#34d399'; // Green
    return '#00f2fe'; // Cyan
  };

  return (
    <GlassPanel
      title="Voice Panel"
      icon={<Mic className="w-3.5 h-3.5" />}
      live={activeStep >= 0}
      liveColor={activeStep === 0 ? 'green' : 'cyan'}
      className={className}
      bodyClassName="h-[calc(100%-2.75rem)] flex flex-col justify-between"
    >
      {/* 6-Stage Stepper Header */}
      <div className="grid grid-cols-6 gap-0.5 mb-1.5">
        {LIFECYCLE_STEPS.map((step, idx) => {
          const isDone = idx < activeStep;
          const isActive = idx === activeStep;
          
          let circleBg = 'bg-zinc-950 border-zinc-800';
          let borderPulse = 'border-transparent';
          if (isDone) {
            circleBg = 'bg-emerald-500/20 border-emerald-500';
          } else if (isActive) {
            circleBg = 'bg-cyan-glow/15 border-cyan-glow';
            borderPulse = 'animate-pulse';
          }

          return (
            <div key={step.label} className="flex flex-col items-center gap-1 min-w-0">
              <div 
                className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center text-[7px] transition-all duration-300 ${circleBg} ${borderPulse}`}
                style={{ boxShadow: isActive ? `0 0 6px ${step.activeGlow}` : 'none' }}
              >
                {isDone ? (
                  <Check className="w-2.5 h-2.5 text-emerald-400" />
                ) : isActive ? (
                  <div className="w-1.5 h-1.5 rounded-full bg-cyan-glow" />
                ) : null}
              </div>
              <span 
                className={`text-[5.5px] font-mono uppercase tracking-wider text-center truncate w-full ${
                  isActive ? step.color + ' font-bold' : isDone ? 'text-zinc-500' : 'text-zinc-700'
                }`}
              >
                {step.label}
              </span>
            </div>
          );
        })}
      </div>

      {/* SVG Waveform Visualizer */}
      <div className="relative flex-1 flex items-center justify-center bg-black/45 rounded-xl border border-cyan-border/10 overflow-hidden px-4 py-1.5 min-h-[56px]">
        <svg viewBox="0 0 100 50" preserveAspectRatio="none" className="w-full h-12 opacity-85">
          <path
            d={generateWavePath(0, 0.45)}
            fill="none"
            stroke={getWaveColor() + '40'}
            strokeWidth="0.8"
            style={{ transition: 'stroke 0.3s ease' }}
          />
          <path
            d={generateWavePath(Math.PI * 0.5, 0.65)}
            fill="none"
            stroke={getWaveColor() + '60'}
            strokeWidth="1"
            style={{ transition: 'stroke 0.3s ease' }}
          />
          <path
            d={generateWavePath(Math.PI, 1.0)}
            fill="none"
            stroke={getWaveColor()}
            strokeWidth="1.5"
            style={{
              filter: `drop-shadow(0 0 4px ${getWaveColor()}aa)`,
              transition: 'stroke 0.3s ease, d 0.1s linear',
            }}
          />
        </svg>

        <div className="absolute inset-x-0 bottom-1 flex justify-between px-3 text-[6.5px] font-mono text-zinc-600">
          <span>{activeStep >= 0 ? LIFECYCLE_STEPS[activeStep].label.toUpperCase() : 'STANDBY'}</span>
          <span>SYNC FREQ</span>
        </div>
      </div>

      {/* Control bar */}
      <div className="flex items-center justify-between gap-3 mt-2 shrink-0">
        <div className="flex flex-col">
          <span className="text-[7.5px] font-mono uppercase tracking-[0.15em] text-zinc-500">Audio Sync</span>
          <span
            className={`text-[9px] font-mono font-bold uppercase tracking-wider ${
              listening ? 'text-emerald-400 cc-blink' : 'text-zinc-500'
            }`}
          >
            {listening ? '● Listening...' : '○ Mic Standby'}
          </span>
        </div>

        {/* Centered Glowing Mic Button */}
        <button
          onClick={handleMicClick}
          className={`w-9 h-9 rounded-full flex items-center justify-center border transition-all duration-300 ${
            listening
              ? 'bg-cyan-glow/15 border-cyan-glow shadow-[0_0_18px_rgba(0,242,254,0.45)] text-cyan-glow'
              : 'bg-black/55 border-zinc-700 hover:border-cyan-border/40 text-zinc-400 hover:text-zinc-200'
          }`}
          title={listening ? 'Mute microphone' : 'Activate microphone'}
        >
          {listening ? <Mic className="w-4 h-4" /> : <MicOff className="w-4 h-4" />}
        </button>

        <div className="text-right">
          <span className="text-[7.5px] font-mono uppercase tracking-[0.15em] text-zinc-500">Voice Power</span>
          <span className="text-[9px] font-mono font-bold text-zinc-300 block">
            {listening ? `${Math.round(voiceLevel * 100)}%` : '0%'}
          </span>
        </div>
      </div>
    </GlassPanel>
  );
};
export default VoiceInputPanel;
