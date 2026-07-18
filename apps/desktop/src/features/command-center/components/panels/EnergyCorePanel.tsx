import React from 'react';
import { Zap } from 'lucide-react';
import { GlassPanel } from './GlassPanel';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';

export const EnergyCorePanel: React.FC<{ className?: string }> = ({ className }) => {
  const powerLevel = useCommandCenterStore((s) => s.powerLevel);

  // Generate 8 battery blocks
  const blocks = Array.from({ length: 8 });
  const activeCount = Math.round((powerLevel / 100) * blocks.length);

  return (
    <GlassPanel
      title="Energy Core"
      icon={<Zap className="w-3.5 h-3.5" />}
      className={className}
      bodyClassName="h-[calc(100%-2.75rem)] flex items-center justify-between gap-4"
    >
      {/* HUD Reactor Sphere (rotating vector layout) */}
      <div className="relative w-18 h-18 rounded-full border border-orange-border/30 bg-black/45 flex items-center justify-center shrink-0">
        {/* Orbiting ring */}
        <div className="absolute inset-0.5 rounded-full border border-dashed border-orange-glow/40 cc-spin-slow" />
        <div className="absolute inset-1.5 rounded-full border border-orange-glow/15 cc-spin-rev" />

        {/* Central glowing core */}
        <div className="relative w-8 h-8 rounded-full bg-orange-glow/10 border border-orange-glow/50 flex items-center justify-center shadow-[0_0_15px_rgba(255,138,61,0.35)]">
          <span className="absolute inset-0 rounded-full bg-orange-glow/20 blur-md animate-pulse" />
          <Zap className="w-4 h-4 text-orange-glow relative z-10" />
        </div>
      </div>

      {/* Metrics read-out */}
      <div className="flex-1 flex flex-col justify-center gap-2">
        <div className="flex flex-col leading-none">
          <span className="text-[7.5px] font-mono uppercase tracking-[0.15em] text-zinc-500">REACTOR LEVEL</span>
          <span className="text-xl font-bold font-mono text-orange-glow cc-text-glow-orange mt-1">
            {Math.round(powerLevel)}%
          </span>
        </div>

        {/* Battery block meter */}
        <div className="flex flex-col gap-1">
          <div className="flex gap-1">
            {blocks.map((_, i) => {
              const active = i < activeCount;
              return (
                <div
                  key={i}
                  className={`h-3.5 w-2.5 rounded-sm border transition-all duration-300 ${
                    active
                      ? 'bg-orange-glow/85 border-orange-glow shadow-[0_0_6px_rgba(255,138,61,0.4)]'
                      : 'bg-black/45 border-zinc-800'
                  }`}
                />
              );
            })}
          </div>
          <span className="text-[7px] font-mono uppercase tracking-[0.2em] text-zinc-600">Grid Stabilitiy: Nominal</span>
        </div>
      </div>
    </GlassPanel>
  );
};
