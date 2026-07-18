import React, { useMemo } from 'react';
import { useExecutionState } from '../../../../services/realtime/hooks/useExecutionState';
import { useAiStateStore } from '../../sync/useAiStateStore';
import { useSystemStore } from '../../../../store/useSystemStore';

interface Stage {
  id: string;
  label: string;
  angle: number; // degrees
}

const STAGES: Stage[] = [
  { id: 'goal', label: 'Goal', angle: -90 },
  { id: 'planning', label: 'Planning', angle: -45 },
  { id: 'memory', label: 'Memory Recall', angle: 0 },
  { id: 'knowledge', label: 'Knowledge Graph', angle: 45 },
  { id: 'tool', label: 'Tool Selection', angle: 90 },
  { id: 'execution', label: 'Execution', angle: 135 },
  { id: 'reflection', label: 'Reflection', angle: 180 },
  { id: 'completed', label: 'Completed', angle: 225 },
];

export const ExecutionPipelineOverlay: React.FC = () => {
  const execState = useExecutionState();
  const aiState = useAiStateStore((s) => s.state);
  const apiConnected = useSystemStore((s) => s.apiConnected);

  // Map state to stage index
  const activeStageIndex = useMemo(() => {
    if (apiConnected && execState.execution_stage) {
      const s = execState.execution_stage.toLowerCase();
      if (s.includes('goal')) return 0;
      if (s.includes('planning')) return 1;
      if (s.includes('memory') || s.includes('recall')) return 2;
      if (s.includes('knowledge') || s.includes('atlas')) return 3;
      if (s.includes('tool')) return 4;
      if (s.includes('execution') || s.includes('execute') || s.includes('mcp')) return 5;
      if (s.includes('reflection') || s.includes('reflect')) return 6;
      if (s.includes('completed') || s.includes('done') || s.includes('ready') || s.includes('idle')) return 7;
    }
    // Simulation state mapping
    switch (aiState) {
      case 'listening': return 0;
      case 'thinking': return 1;
      case 'memory': return 2;
      case 'knowledge': return 3;
      case 'tool': return 4;
      case 'executing':
      case 'workflow': return 5;
      case 'speaking': return 6;
      case 'idle': return 7;
      default: return 7;
    }
  }, [apiConnected, execState.execution_stage, aiState]);

  const CX = 250;
  const CY = 250;
  const R = 182;
  const textOffset = 26;

  // Node coordinates calculation helper
  const coordinates = useMemo(() => {
    return STAGES.map((s) => {
      const rad = (s.angle * Math.PI) / 180;
      const x = CX + Math.cos(rad) * R;
      const y = CY + Math.sin(rad) * R;
      
      const tx = CX + Math.cos(rad) * (R + textOffset);
      const ty = CY + Math.sin(rad) * (R + textOffset);
      
      let textAnchor: 'start' | 'middle' | 'end' = 'middle';
      const cosVal = Math.cos(rad);
      if (cosVal > 0.1) textAnchor = 'start';
      else if (cosVal < -0.1) textAnchor = 'end';

      return { ...s, x, y, tx, ty, textAnchor };
    });
  }, [R]);

  return (
    <div className="absolute inset-0 pointer-events-none select-none">
      <svg viewBox="0 0 500 500" className="w-full h-full">
        <defs>
          <radialGradient id="ringGlow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#00f2fe" stopOpacity="0.15" />
            <stop offset="100%" stopColor="#00f2fe" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Backing structural circular dial */}
        <circle cx={CX} cy={CY} r={R} fill="none" stroke="rgba(0, 242, 254, 0.08)" strokeWidth="1" />
        <circle cx={CX} cy={CY} r={R + 8} fill="none" stroke="rgba(0, 242, 254, 0.03)" strokeWidth="0.5" />

        {/* Dynamic connection circuit paths */}
        {coordinates.map((curr, idx) => {
          if (idx === coordinates.length - 1) return null;
          const next = coordinates[idx + 1];
          const isCompleted = idx < activeStageIndex;
          const isCurrent = idx === activeStageIndex;
          
          let stroke = 'rgba(0, 242, 254, 0.1)';
          let strokeDash = '';
          if (isCompleted) {
            stroke = '#10b981'; // Green
          } else if (isCurrent) {
            stroke = '#00f2fe';
            strokeDash = '4, 4';
          }

          return (
            <g key={`path-${curr.id}`}>
              <line
                x1={curr.x}
                y1={curr.y}
                x2={next.x}
                y2={next.y}
                stroke={stroke}
                strokeWidth={isCurrent ? '1.8' : '1.0'}
                strokeDasharray={strokeDash}
                style={{ transition: 'stroke 0.4s ease' }}
              />
              {isCurrent && (
                <line
                  x1={curr.x}
                  y1={curr.y}
                  x2={next.x}
                  y2={next.y}
                  stroke="#00f2fe"
                  strokeWidth="2.5"
                  className="animate-pulse"
                  opacity="0.3"
                />
              )}
            </g>
          );
        })}

        {/* Drawing Stage Nodes */}
        {coordinates.map((node, idx) => {
          const isCompleted = idx < activeStageIndex;
          const isActive = idx === activeStageIndex;
          
          let circleColor = 'rgba(39, 39, 42, 0.4)';
          let borderColor = 'rgba(255, 255, 255, 0.15)';
          let glow = '';

          if (isCompleted) {
            circleColor = '#10b981';
            borderColor = '#10b981';
          } else if (isActive) {
            circleColor = '#00f2fe';
            borderColor = '#00f2fe';
            glow = 'drop-shadow(0 0 5px rgba(0, 242, 254, 0.8))';
          }

          return (
            <g key={node.id} className="transition-all duration-300">
              {/* Outer Pulsing Active Ring */}
              {isActive && (
                <>
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r="9"
                    fill="none"
                    stroke="#00f2fe"
                    strokeWidth="0.8"
                    className="animate-ping"
                    opacity="0.4"
                  />
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r="13"
                    fill="none"
                    stroke="rgba(0, 242, 254, 0.25)"
                    strokeWidth="0.5"
                    className="cc-spin-fast"
                    strokeDasharray="4, 4"
                  />
                </>
              )}

              {/* Node Core circle */}
              <circle
                cx={node.x}
                cy={node.y}
                r={isActive ? '5' : '3.5'}
                fill={circleColor}
                stroke={borderColor}
                strokeWidth={isActive ? '1.5' : '0.8'}
                style={{ filter: glow, transition: 'all 0.4s ease' }}
              />

              {/* Node Label Text */}
              <text
                x={node.tx}
                y={node.ty}
                textAnchor={node.textAnchor}
                dominantBaseline="middle"
                className={`font-mono text-[7px] uppercase tracking-wider ${
                  isActive
                    ? 'text-cyan-glow font-black cc-text-glow'
                    : isCompleted
                    ? 'text-emerald-400 font-bold'
                    : 'text-zinc-600'
                }`}
                style={{ transition: 'fill 0.4s ease' }}
              >
                {node.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};
export default ExecutionPipelineOverlay;
