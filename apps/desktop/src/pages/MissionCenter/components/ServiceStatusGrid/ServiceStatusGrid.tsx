import React from 'react';
import { useServiceStatus } from '../../hooks';

// 1. TypeScript interface for Props
export interface ServiceStatusGridProps {
  isLoading?: boolean;
  hasError?: boolean;
}

// 2. Export component
export const ServiceStatusGrid: React.FC<ServiceStatusGridProps> = ({
  isLoading = false,
  hasError = false,
}) => {
  const { services } = useServiceStatus();

  // 3. Accessibility comments
  // role="grid" identifies this component as holding status data grid cells
  // aria-readonly indicates that statuses can be read but not modified directly

  // 4. Loading placeholder
  if (isLoading) {
    return (
      <div 
        className="grid grid-cols-1 gap-2.5 p-4 animate-pulse"
        aria-busy="true"
        aria-label="Loading service statuses"
      >
        {[1, 2, 3, 4].map((n) => (
          <div key={n} className="h-8 bg-zinc-800 rounded-lg" />
        ))}
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
        Failed to verify dynamic subsystem status.
      </div>
    );
  }

  // 6. Empty state fallback
  if (services.length === 0) {
    return (
      <div className="p-4 border border-dashed border-matte-border/30 rounded-xl text-center text-xs font-mono text-zinc-500">
        No registered subsystems detected.
      </div>
    );
  }

  const statusThemes = {
    HEALTHY: 'bg-emerald-dim border-emerald-500/20 text-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.02)]',
    WARNING: 'bg-orange-950/20 border-orange-500/20 text-orange-400',
    ERROR: 'bg-red-950/20 border-red-500/20 text-red-400 animate-pulse',
    OFFLINE: 'bg-zinc-950/50 border-zinc-900/50 text-zinc-600',
  };

  const statusBullet = {
    HEALTHY: 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]',
    WARNING: 'bg-orange-500 shadow-[0_0_8px_rgba(249,115,22,0.5)]',
    ERROR: 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)] animate-pulse',
    OFFLINE: 'bg-zinc-700',
  };

  return (
    <div 
      className="flex flex-col gap-4 bg-matte-card/15 p-4.5 border border-matte-border/20 rounded-xl hover:border-matte-border/40 transition-colors"
      role="grid"
      aria-label="Service Heartbeat Status"
      aria-readonly="true"
    >
      <h4 className="text-[10px] font-mono uppercase tracking-widest text-zinc-400 font-bold border-b border-matte-border/10 pb-3">
        Subsystems Checklist
      </h4>

      <div className="grid grid-cols-1 gap-2 max-h-56 overflow-y-auto pr-1 scrollbar-thin">
        {services.map((svc) => {
          // Generate mock latency numbers based on status
          const getLatencyText = () => {
            if (svc.status === 'HEALTHY') return `${Math.floor(Math.random() * 8) + 8}ms`;
            if (svc.status === 'WARNING') return `${Math.floor(Math.random() * 40) + 80}ms`;
            if (svc.status === 'ERROR') return `${Math.floor(Math.random() * 200) + 400}ms`;
            return 'timeout';
          };

          return (
            <div 
              key={svc.name}
              role="gridcell"
              className={`p-2.5 rounded-xl border flex items-center justify-between text-[10px] font-mono tracking-wider transition-colors duration-200 hover:bg-white/[0.01]
                ${statusThemes[svc.status]}
              `}
            >
              <div className="flex flex-col gap-0.5">
                <span className="font-medium text-zinc-200">{svc.name}</span>
                {svc.message && (
                  <span className="text-[8px] text-zinc-500 lowercase leading-none">{svc.message}</span>
                )}
              </div>
              <div className="flex items-center gap-2.5">
                <span className="text-[8px] text-zinc-500 font-mono tracking-normal font-bold lowercase">
                  {getLatencyText()}
                </span>
                <span className={`w-1.5 h-1.5 rounded-full ${statusBullet[svc.status]}`} />
                <span className="text-[8px] uppercase tracking-wider font-bold">{svc.status}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
