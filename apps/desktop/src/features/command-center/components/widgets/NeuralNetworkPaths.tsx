import React, { useMemo } from 'react';
import { useAiStateStore } from '../../sync/useAiStateStore';

export const NeuralNetworkPaths: React.FC = () => {
  const aiState = useAiStateStore((s) => s.state);

  // Coordinate configurations for a responsive 1000x600 coordinate viewbox
  const center = { x: 500, y: 300 };

  // Targets coordinates corresponding to panel midpoint locations
  const targets = useMemo(() => [
    { id: 'overview', x: 180, y: 150, cx: 350, cy: 220 }, // Top-Left
    { id: 'agents', x: 180, y: 440, cx: 350, cy: 380 },   // Bottom-Left
    { id: 'graph', x: 820, y: 240, cx: 650, cy: 250 },    // Mid-Right
    { id: 'memory', x: 820, y: 440, cx: 650, cy: 370 },   // Bottom-Right
  ], []);

  // Determine trace glow colors and animation speeds based on AI Core status
  const flowConfig = useMemo(() => {
    switch (aiState) {
      case 'thinking':
        return { color: '#c084fc', speed: '4.5s', opacity: 0.8 }; // Purple planning flow
      case 'executing':
      case 'tool':
      case 'workflow':
        return { color: '#ff8a3d', speed: '2s', opacity: 1.0 };   // Rapid orange execution sparks
      case 'speaking':
        return { color: '#00f2fe', speed: '3.5s', opacity: 0.9 };  // Cyan voice modulation
      case 'idle':
      default:
        return { color: '#00f2fe', speed: '8s', opacity: 0.45 };   // Slow cyan standby pulse
    }
  }, [aiState]);

  return (
    <div className="absolute inset-0 pointer-events-none select-none z-0 w-full h-full">
      <svg viewBox="0 0 1000 600" preserveAspectRatio="none" className="w-full h-full opacity-60">
        <defs>
          {/* Neon path glows */}
          <filter id="pathGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {targets.map((t) => {
          // Construct bezier path from center coordinates to panel midpoint
          const pathD = `M ${center.x},${center.y} C ${t.cx},${t.cy} ${t.cx - (center.x - t.x) * 0.3},${t.y} ${t.x},${t.y}`;

          return (
            <g key={t.id}>
              {/* Backing structural circuit line */}
              <path
                d={pathD}
                fill="none"
                stroke="rgba(0, 242, 254, 0.05)"
                strokeWidth="1.2"
              />
              
              {/* Secondary fine glowing track */}
              <path
                d={pathD}
                fill="none"
                stroke={flowConfig.color}
                strokeWidth="1.0"
                opacity={flowConfig.opacity * 0.18}
                style={{ transition: 'stroke 0.4s ease, opacity 0.4s ease' }}
              />

              {/* Pulsing data-packet glow sweeping along the bezier paths */}
              <path
                d={pathD}
                fill="none"
                stroke={flowConfig.color}
                strokeWidth="1.6"
                filter="url(#pathGlow)"
                strokeDasharray="24, 180"
                strokeDashoffset="0"
                style={{
                  strokeDashoffset: 'var(--dashoffset)',
                  animation: `cc-neural-flow ${flowConfig.speed} linear infinite`,
                  transition: 'stroke 0.4s ease',
                  opacity: flowConfig.opacity,
                }}
                className="cc-neural-trace"
              />
            </g>
          );
        })}
      </svg>

      <style>{`
        @keyframes cc-neural-flow {
          0% {
            stroke-dashoffset: 204;
          }
          100% {
            stroke-dashoffset: 0;
          }
        }
      `}</style>
    </div>
  );
};
export default NeuralNetworkPaths;
