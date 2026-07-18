import React from 'react';
import type { AgentStatus } from '../../data/mock';

const styles: Record<AgentStatus, { dot: string; text: string; ring: string }> = {
  ACTIVE: { dot: 'bg-emerald-400', text: 'text-emerald-400', ring: 'border-emerald-400/30' },
  BUSY: { dot: 'bg-orange-glow', text: 'text-orange-glow', ring: 'border-orange-border' },
  IDLE: { dot: 'bg-zinc-500', text: 'text-zinc-500', ring: 'border-zinc-600/40' },
  ERROR: { dot: 'bg-rose-500', text: 'text-rose-400', ring: 'border-rose-500/30' },
};

export const StatusPill: React.FC<{ status: AgentStatus; labelOverride?: string; className?: string }> = ({ 
  status, labelOverride, className = '' 
}) => {
  const s = styles[status] || styles.IDLE;
  const labelText = labelOverride || status;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border ${s.ring} bg-black/30 ${className}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot} ${status !== 'IDLE' ? 'cc-blink' : ''}`} />
      <span className={`text-[8px] font-mono font-bold uppercase tracking-[0.15em] ${s.text}`}>{labelText}</span>
    </span>
  );
};
