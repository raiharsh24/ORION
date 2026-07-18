import React from 'react';
import { Gauge, BrainCircuit, Scan, Timer, ShieldCheck } from 'lucide-react';
import { GlassPanel } from './GlassPanel';
import { CircularHUD } from '../widgets/CircularHUD';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';

const StatRow: React.FC<{ icon: React.ReactNode; label: string; value: string; accent?: string }> = ({
  icon, label, value, accent = 'text-cyan-glow',
}) => (
  <div className="flex flex-col gap-0.5">
    <span className="flex items-center gap-1 text-[7.5px] font-mono uppercase tracking-[0.12em] text-zinc-500">
      {icon}
      {label}
    </span>
    <span className={`text-[10px] font-mono font-bold tabular-nums ${accent}`}>{value}</span>
  </div>
);

export const AICoreStatusPanel: React.FC<{ className?: string }> = ({ className }) => {
  const model = useCommandCenterStore((s) => s.model);
  const contextWindow = useCommandCenterStore((s) => s.contextWindow);
  const responseSpeed = useCommandCenterStore((s) => s.responseSpeed);
  const confidence = useCommandCenterStore((s) => s.confidence);

  // Map system store metrics onto the target specifications dynamically
  const displayModel = model.includes('FRIDAY') ? 'gemini-2.5-flash' : model;
  
  // Calculate context size dynamically (e.g. 128K / 1M)
  const tokensLoaded = Math.round((contextWindow / 100) * 1000);
  const contextReadout = `${tokensLoaded}K / 1M TOKENS`;

  // Scale speed value to response seconds (e.g. 1.24s)
  const responseSeconds = (1.5 - (responseSpeed / 200) * 0.5).toFixed(2);

  return (
    <GlassPanel
      title="AI Core Status"
      icon={<Gauge className="w-3.5 h-3.5" />}
      className={className}
      bodyClassName="flex items-center gap-5 h-[calc(100%-2.75rem)]"
    >
      {/* HUD Scanner Dial */}
      <div className="relative shrink-0 flex items-center justify-center p-1 border border-cyan-border/10 rounded-xl bg-black/25">
        <CircularHUD 
          value={confidence} 
          label={`${confidence.toFixed(1)}%`} 
          sublabel="Confidence" 
          size={98} 
        />
        <div className="absolute inset-0 pointer-events-none border border-cyan-border/5 rounded-xl m-1" />
      </div>

      {/* Specifications list */}
      <div className="flex-1 grid grid-cols-2 gap-x-2 gap-y-2 min-w-0">
        <StatRow 
          icon={<BrainCircuit className="w-3 h-3 text-zinc-500" />} 
          label="Model" 
          value={displayModel} 
          accent="text-zinc-200" 
        />
        <StatRow 
          icon={<Scan className="w-3 h-3 text-zinc-500" />} 
          label="Context Window" 
          value={contextReadout} 
          accent="text-cyan-glow cc-text-glow" 
        />
        <StatRow 
          icon={<Timer className="w-3 h-3 text-zinc-500" />} 
          label="Response Speed" 
          value={`${responseSeconds}s`} 
          accent="text-orange-glow" 
        />
        <StatRow 
          icon={<ShieldCheck className="w-3 h-3 text-zinc-500" />} 
          label="Confidence" 
          value={`${confidence.toFixed(1)}%`} 
          accent="text-emerald-400" 
        />
      </div>
    </GlassPanel>
  );
};
