import React from 'react';
import { Gauge, BrainCircuit, Wind, Timer, ShieldCheck } from 'lucide-react';
import { GlassPanel } from './GlassPanel';
import { CircularHUD } from '../widgets/CircularHUD';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';

const StatRow: React.FC<{ icon: React.ReactNode; label: string; value: string; accent?: string }> = ({
  icon, label, value, accent = 'text-cyan-glow',
}) => (
  <div className="flex items-center justify-between gap-2">
    <span className="flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-[0.12em] text-zinc-400">
      <span className="text-zinc-500">{icon}</span>
      {label}
    </span>
    <span className={`text-[11px] font-mono font-bold tabular-nums ${accent}`}>{value}</span>
  </div>
);

export const AICoreStatusPanel: React.FC<{ className?: string }> = ({ className }) => {
  const model = useCommandCenterStore((s) => s.model);
  const contextWindow = useCommandCenterStore((s) => s.contextWindow);
  const responseSpeed = useCommandCenterStore((s) => s.responseSpeed);
  const confidence = useCommandCenterStore((s) => s.confidence);

  return (
    <GlassPanel
      title="AI Core Status"
      icon={<Gauge className="w-3.5 h-3.5" />}
      className={className}
      bodyClassName="flex items-center gap-4 h-[calc(100%-2.75rem)]"
    >
      <CircularHUD value={confidence} label={`${Math.round(confidence)}%`} sublabel="Confidence" size={104} />
      <div className="flex-1 space-y-2.5 min-w-0">
        <StatRow icon={<BrainCircuit className="w-3 h-3" />} label="Model" value={model} />
        <StatRow icon={<Wind className="w-3 h-3" />} label="Context" value={`${Math.round(contextWindow)}%`} />
        <StatRow icon={<Timer className="w-3 h-3" />} label="Speed" value={`${responseSpeed} t/s`} accent="text-orange-glow" />
        <StatRow icon={<ShieldCheck className="w-3 h-3" />} label="Confidence" value={`${Math.round(confidence)}%`} accent="text-emerald-400" />
      </div>
    </GlassPanel>
  );
};
