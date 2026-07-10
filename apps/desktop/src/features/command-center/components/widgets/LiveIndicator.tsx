import React from 'react';

interface LiveIndicatorProps {
  label?: string;
  color?: 'cyan' | 'orange' | 'green';
  className?: string;
}

const dot: Record<NonNullable<LiveIndicatorProps['color']>, string> = {
  cyan: 'bg-cyan-glow shadow-[0_0_8px_rgba(0,242,254,0.9)]',
  orange: 'bg-orange-glow shadow-[0_0_8px_rgba(255,138,61,0.9)]',
  green: 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.9)]',
};

const text: Record<NonNullable<LiveIndicatorProps['color']>, string> = {
  cyan: 'text-cyan-glow',
  orange: 'text-orange-glow',
  green: 'text-emerald-400',
};

export const LiveIndicator: React.FC<LiveIndicatorProps> = ({ label = 'LIVE', color = 'cyan', className = '' }) => (
  <span className={`inline-flex items-center gap-1.5 ${className}`}>
    <span className={`w-1.5 h-1.5 rounded-full cc-blink ${dot[color]}`} />
    <span className={`text-[8px] font-mono font-bold uppercase tracking-[0.2em] ${text[color]}`}>{label}</span>
  </span>
);
