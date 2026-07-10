import React, { useId } from 'react';

interface CircularHUDProps {
  value: number;         // 0..100 primary arc
  label?: string;
  sublabel?: string;
  size?: number;
  color?: string;
  trackColor?: string;
}

/**
 * Circular heads-up gauge: rotating tick ring, animated progress arc and a
 * central readout. Used by AI Core Status and reused around the core.
 */
export const CircularHUD: React.FC<CircularHUDProps> = ({
  value,
  label,
  sublabel,
  size = 104,
  color = '#00f2fe',
  trackColor = 'rgba(0,242,254,0.12)',
}) => {
  const gid = useId();
  const r = 42;
  const c = 2 * Math.PI * r;
  const pct = Math.min(100, Math.max(0, value));
  const dash = (pct / 100) * c;

  const ticks = Array.from({ length: 40 });

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
        <defs>
          <linearGradient id={`hud-${gid}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={color} />
            <stop offset="100%" stopColor="#4db8ff" />
          </linearGradient>
        </defs>
        <circle cx="50" cy="50" r={r} fill="none" stroke={trackColor} strokeWidth="4" />
        <circle
          cx="50" cy="50" r={r} fill="none"
          stroke={`url(#hud-${gid})`}
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c}`}
          style={{ transition: 'stroke-dasharray 0.6s ease', filter: `drop-shadow(0 0 4px ${color}88)` }}
        />
      </svg>

      {/* rotating tick ring */}
      <svg viewBox="0 0 100 100" className="absolute inset-0 w-full h-full cc-spin-slow opacity-50">
        {ticks.map((_, i) => {
          const a = (i / ticks.length) * Math.PI * 2;
          const x1 = 50 + Math.cos(a) * 48;
          const y1 = 50 + Math.sin(a) * 48;
          const x2 = 50 + Math.cos(a) * (i % 5 === 0 ? 44 : 46);
          const y2 = 50 + Math.sin(a) * (i % 5 === 0 ? 44 : 46);
          return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth={i % 5 === 0 ? 0.8 : 0.4} opacity={i % 5 === 0 ? 0.7 : 0.35} />;
        })}
      </svg>

      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {label && <span className="text-xl font-bold text-zinc-100 leading-none cc-text-glow">{label}</span>}
        {sublabel && <span className="text-[8px] font-mono uppercase tracking-[0.15em] text-cyan-glow/70 mt-1">{sublabel}</span>}
      </div>
    </div>
  );
};
