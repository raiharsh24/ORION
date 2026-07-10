import React, { useId } from 'react';

interface SparklineProps {
  data: number[];
  color?: string;
  height?: number;
  min?: number;
  max?: number;
  className?: string;
  strokeWidth?: number;
}

/**
 * Lightweight animated SVG line graph with a gradient area fill.
 * Re-renders smoothly as the underlying series updates each tick.
 */
export const Sparkline: React.FC<SparklineProps> = ({
  data,
  color = '#00f2fe',
  height = 40,
  min = 0,
  max = 100,
  className = '',
  strokeWidth = 1.6,
}) => {
  const gid = useId();
  const W = 100;
  const H = height;
  const range = Math.max(1, max - min);

  const pts = data.length
    ? data.map((v, i) => {
        const x = data.length === 1 ? 0 : (i / (data.length - 1)) * W;
        const y = H - ((Math.min(max, Math.max(min, v)) - min) / range) * H;
        return [x, y] as const;
      })
    : [[0, H] as const];

  const line = pts.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`).join(' ');
  const area = `${line} L${W},${H} L0,${H} Z`;
  const last = pts[pts.length - 1];

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className={`w-full ${className}`}
      style={{ height: H }}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={`grad-${gid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#grad-${gid})`} />
      <path
        d={line}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
        style={{ filter: `drop-shadow(0 0 3px ${color}66)`, transition: 'd 0.3s linear' }}
      />
      {/* leading pulse dot */}
      <circle cx={last[0]} cy={last[1]} r={1.6} fill={color} vectorEffect="non-scaling-stroke">
        <animate attributeName="opacity" values="1;0.3;1" dur="1.6s" repeatCount="indefinite" />
      </circle>
    </svg>
  );
};
