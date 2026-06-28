import React from 'react';
import { useKernelHealth } from '../../hooks';
import { useKernelStore } from '../../store';

// 1. TypeScript interface for Props
export interface KernelHealthPanelProps {
  isLoading?: boolean;
  hasError?: boolean;
}

// 2. Export component
export const KernelHealthPanel: React.FC<KernelHealthPanelProps> = ({
  isLoading = false,
  hasError = false,
}) => {
  const { cpu, memory, uptime, state } = useKernelHealth();

  // 3. Accessibility comments
  // role="region" labels this as containing diagnostic information
  // aria-label outlines the kernel health statistics

  // 4. Loading state
  if (isLoading) {
    return (
      <div 
        className="p-4 bg-zinc-950/20 border border-matte-border/20 rounded-xl space-y-3 animate-pulse"
        aria-busy="true"
        aria-label="Loading kernel health stats"
      >
        <div className="h-4 w-1/2 bg-zinc-800 rounded" />
        <div className="h-3 w-full bg-zinc-800 rounded" />
        <div className="h-3 w-3/4 bg-zinc-800 rounded" />
      </div>
    );
  }

  // 5. Error state
  if (hasError) {
    return (
      <div 
        className="p-4 bg-red-950/15 border border-red-900/30 text-xs font-mono text-red-400 rounded-xl"
        role="alert"
      >
        Failed to fetch Kernel status heartbeats.
      </div>
    );
  }

  // 6. Empty state fallback
  if (!state) {
    return (
      <div className="p-4 border border-dashed border-matte-border/30 rounded-xl text-center text-xs font-mono text-zinc-500">
        Kernel offline
      </div>
    );
  }

  return (
    <div 
      className="p-4.5 border border-matte-border/20 rounded-xl bg-matte-card/30 backdrop-blur-sm flex flex-col gap-4.5"
      role="region"
      aria-label="FRIDAY Kernel Health Metrics"
    >
      <div className="flex justify-between items-center border-b border-matte-border/10 pb-3">
        <h4 className="text-[10px] font-mono uppercase tracking-widest text-zinc-400 font-bold">
          Kernel Status
        </h4>
        <span className="text-[9px] font-mono px-2 py-0.5 bg-emerald-dim text-emerald-400 border border-emerald-500/20 rounded-sm font-bold uppercase">
          {state}
        </span>
      </div>

      {/* Metrics breakdown */}
      <div className="space-y-4 font-mono text-[11px] text-zinc-300">
        <div className="flex justify-between items-center">
          <span className="text-zinc-500 uppercase tracking-wider text-[9px]">Uptime</span>
          <span className="text-zinc-200">{uptime}</span>
        </div>

        <div className="flex justify-between items-center border-t border-matte-border/10 pt-2.5">
          <span className="text-zinc-500 uppercase tracking-wider text-[9px]">Registered Services</span>
          <span className="text-cyan-glow font-bold">{useKernelStore.getState().registeredServicesCount} Active</span>
        </div>

        {/* CPU Util */}
        <div className="space-y-1.5 border-t border-matte-border/10 pt-2.5">
          <div className="flex justify-between items-center text-[9px] uppercase tracking-wider">
            <div className="flex items-center gap-1.5 text-zinc-500">
              <span>CPU Util</span>
              {cpu > 80 && (
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-red-500"></span>
                </span>
              )}
            </div>
            <span className={`font-bold ${cpu > 80 ? 'text-red-400' : 'text-zinc-300'}`}>{cpu.toFixed(1)}%</span>
          </div>
          <div className="w-full bg-zinc-950/50 h-1.5 rounded-full overflow-hidden border border-matte-border/10">
            <div 
              className={`h-full rounded-full transition-all duration-300
                ${cpu > 80 ? 'bg-red-500' : 'bg-cyan-glow'}
              `}
              style={{ width: `${Math.min(100, cpu)}%` }}
            />
          </div>
        </div>

        {/* Memory Util */}
        <div className="space-y-1.5">
          <div className="flex justify-between items-center text-[9px] uppercase tracking-wider">
            <div className="flex items-center gap-1.5 text-zinc-500">
              <span>Memory Heap</span>
              {memory > 800 && (
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-orange-500"></span>
                </span>
              )}
            </div>
            <span className={`font-bold ${memory > 800 ? 'text-orange-400' : 'text-zinc-300'}`}>{memory} MB</span>
          </div>
          <div className="w-full bg-zinc-950/50 h-1.5 rounded-full overflow-hidden border border-matte-border/10">
            <div 
              className={`h-full rounded-full transition-all duration-300
                ${memory > 800 ? 'bg-orange-500' : 'bg-cyan-glow'}
              `}
              style={{ width: `${Math.min(100, (memory / 1024) * 100)}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
};
