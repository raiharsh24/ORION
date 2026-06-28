import React, { useMemo } from 'react';
import type { Workflow, WorkflowNode, WorkflowNodeStatus } from '../../types';

interface WorkflowGraphProps {
  workflow: Workflow | null;
  className?: string;
}

// ─── Status colour mapping ────────────────────────────────────────────────────

const STATUS_COLOURS: Record<WorkflowNodeStatus, { border: string; bg: string; text: string; glow: string }> = {
  PENDING:   { border: 'border-zinc-600',   bg: 'bg-zinc-900/60',   text: 'text-zinc-400',   glow: '' },
  RUNNING:   { border: 'border-cyan-500',   bg: 'bg-cyan-950/60',   text: 'text-cyan-300',   glow: 'shadow-[0_0_12px_rgba(6,182,212,0.5)]' },
  COMPLETED: { border: 'border-emerald-500', bg: 'bg-emerald-950/50', text: 'text-emerald-300', glow: '' },
  FAILED:    { border: 'border-red-500',    bg: 'bg-red-950/60',    text: 'text-red-300',    glow: 'shadow-[0_0_10px_rgba(239,68,68,0.4)]' },
  CANCELLED: { border: 'border-zinc-600',   bg: 'bg-zinc-900/40',   text: 'text-zinc-500',   glow: '' },
  SKIPPED:   { border: 'border-zinc-700',   bg: 'bg-zinc-950/40',   text: 'text-zinc-600',   glow: '' },
  PAUSED:    { border: 'border-amber-500',  bg: 'bg-amber-950/50',  text: 'text-amber-300',  glow: '' },
  WAITING:   { border: 'border-violet-500', bg: 'bg-violet-950/50', text: 'text-violet-300', glow: '' },
  RETRYING:  { border: 'border-orange-500', bg: 'bg-orange-950/50', text: 'text-orange-300', glow: 'shadow-[0_0_10px_rgba(249,115,22,0.4)]' },
};

const NODE_TYPE_ICON: Record<string, string> = {
  'Desktop Action':  '🖥',
  'Mission':         '🎯',
  'LLM Prompt':      '🤖',
  'Knowledge Query': '🔍',
  'Planner Step':    '🗺',
  'Condition':       '⑃',
  'Delay':           '⏱',
  'Notification':    '🔔',
};

// ─── Layout helpers ───────────────────────────────────────────────────────────

/**
 * Assigns nodes to columns (layers) based on topological depth.
 * Returns a Map<node_id, { col, row }>.
 */
function computeLayout(nodes: Record<string, WorkflowNode>) {
  const depth: Record<string, number> = {};

  const getDepth = (id: string, visited = new Set<string>()): number => {
    if (depth[id] !== undefined) return depth[id];
    if (visited.has(id)) return 0;
    visited.add(id);
    const node = nodes[id];
    if (!node || node.depends_on.length === 0) {
      depth[id] = 0;
      return 0;
    }
    const maxDep = Math.max(...node.depends_on.map(d => getDepth(d, new Set(visited))));
    depth[id] = maxDep + 1;
    return depth[id];
  };

  Object.keys(nodes).forEach(id => getDepth(id));

  // Group by depth
  const columns: Record<number, string[]> = {};
  Object.entries(depth).forEach(([id, col]) => {
    columns[col] = columns[col] || [];
    columns[col].push(id);
  });

  const positions: Record<string, { col: number; row: number }> = {};
  Object.entries(columns).forEach(([col, ids]) => {
    ids.forEach((id, row) => {
      positions[id] = { col: parseInt(col), row };
    });
  });

  return positions;
}

// ─── Component ────────────────────────────────────────────────────────────────

export const WorkflowGraph: React.FC<WorkflowGraphProps> = ({ workflow, className = '' }) => {
  const positions = useMemo(
    () => (workflow ? computeLayout(workflow.nodes) : {}),
    [workflow]
  );

  if (!workflow) {
    return (
      <div className={`flex items-center justify-center h-32 rounded-xl border border-dashed border-matte-border/20 bg-matte-card/20 text-zinc-600 text-[10px] font-mono ${className}`}>
        No workflow selected
      </div>
    );
  }

  if (Object.keys(workflow.nodes).length === 0) {
    return (
      <div className={`flex items-center justify-center h-32 rounded-xl border border-dashed border-matte-border/20 bg-matte-card/20 text-zinc-600 text-[10px] font-mono ${className}`}>
        Workflow has no nodes
      </div>
    );
  }

  const nodeList = Object.values(workflow.nodes);
  const maxCol   = Math.max(...Object.values(positions).map(p => p.col), 0);
  const maxRow   = Math.max(...Object.values(positions).map(p => p.row), 0);

  const COL_W  = 160;
  const ROW_H  = 72;
  const PAD_X  = 24;
  const PAD_Y  = 24;
  const NODE_W = 140;
  const NODE_H = 52;

  const svgW = (maxCol + 1) * COL_W + PAD_X * 2;
  const svgH = (maxRow + 1) * ROW_H + PAD_Y * 2;

  const nodeCenter = (id: string) => {
    const pos = positions[id];
    if (!pos) return { x: 0, y: 0 };
    return {
      x: PAD_X + pos.col * COL_W + NODE_W / 2,
      y: PAD_Y + pos.row * ROW_H + NODE_H / 2,
    };
  };

  // Collect edges
  const edges: { from: string; to: string; type: 'dep' | 'success' | 'failure' }[] = [];
  nodeList.forEach(node => {
    node.depends_on.forEach(dep => edges.push({ from: dep, to: node.id, type: 'dep' }));
    if (node.on_success) edges.push({ from: node.id, to: node.on_success, type: 'success' });
    if (node.on_failure) edges.push({ from: node.id, to: node.on_failure, type: 'failure' });
  });

  return (
    <div className={`rounded-xl border border-matte-border/20 bg-matte-card/20 overflow-hidden ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-matte-border/15 bg-black/10">
        <div className="flex items-center gap-2">
          <span className="text-[9px] font-mono uppercase tracking-widest text-zinc-500 font-bold">Execution Graph</span>
          <span className={`text-[8px] font-mono px-1.5 py-0.5 rounded font-bold uppercase ${
            workflow.status === 'RUNNING'   ? 'bg-cyan-500/20 text-cyan-400' :
            workflow.status === 'COMPLETED' ? 'bg-emerald-500/20 text-emerald-400' :
            workflow.status === 'FAILED'    ? 'bg-red-500/20 text-red-400' :
            workflow.status === 'PAUSED'    ? 'bg-amber-500/20 text-amber-400' :
            'bg-zinc-800 text-zinc-500'
          }`}>
            {workflow.status}
          </span>
        </div>
        <span className="text-[9px] font-mono text-zinc-600 truncate max-w-[120px]">{workflow.name}</span>
      </div>

      {/* SVG Graph */}
      <div className="overflow-x-auto overflow-y-hidden">
        <svg
          width={svgW}
          height={Math.max(svgH, 100)}
          className="block"
          aria-label={`Workflow graph for ${workflow.name}`}
        >
          {/* Edges */}
          {edges.map((edge, i) => {
            const from = nodeCenter(edge.from);
            const to   = nodeCenter(edge.to);
            if (!from || !to) return null;
            const colour =
              edge.type === 'success' ? '#10b981' :
              edge.type === 'failure' ? '#ef4444' :
              '#3f3f46';
            const midX = (from.x + to.x) / 2;
            return (
              <path
                key={`edge-${i}`}
                d={`M ${from.x} ${from.y} C ${midX} ${from.y}, ${midX} ${to.y}, ${to.x} ${to.y}`}
                fill="none"
                stroke={colour}
                strokeWidth={edge.type === 'dep' ? 1 : 1.5}
                strokeDasharray={edge.type === 'dep' ? undefined : '4 3'}
                opacity={0.6}
                markerEnd={`url(#arrow-${edge.type})`}
              />
            );
          })}

          {/* Arrow markers */}
          <defs>
            {(['dep', 'success', 'failure'] as const).map(t => (
              <marker key={t} id={`arrow-${t}`} markerWidth="6" markerHeight="6"
                refX="5" refY="3" orient="auto">
                <path d="M0,0 L6,3 L0,6 Z"
                  fill={t === 'success' ? '#10b981' : t === 'failure' ? '#ef4444' : '#3f3f46'} />
              </marker>
            ))}
          </defs>

          {/* Nodes */}
          {nodeList.map(node => {
            const pos = positions[node.id];
            if (!pos) return null;
            const x = PAD_X + pos.col * COL_W;
            const y = PAD_Y + pos.row * ROW_H;
            const colours = STATUS_COLOURS[node.status] || STATUS_COLOURS.PENDING;
            const isRunning = node.status === 'RUNNING';
            const icon = NODE_TYPE_ICON[node.type] || '◆';

            return (
              <g key={node.id} aria-label={`Node ${node.name} status ${node.status}`}>
                {/* Pulse ring for running node */}
                {isRunning && (
                  <rect
                    x={x - 3} y={y - 3}
                    width={NODE_W + 6} height={NODE_H + 6}
                    rx={10} ry={10}
                    fill="none" stroke="rgba(6,182,212,0.4)"
                    strokeWidth={2}
                    className="animate-ping"
                  />
                )}
                {/* Node box (foreignObject for HTML rendering inside SVG) */}
                <foreignObject x={x} y={y} width={NODE_W} height={NODE_H}>
                  <div
                    className={`
                      w-full h-full rounded-lg border px-2 py-1.5 flex flex-col justify-between
                      cursor-default transition-all duration-200
                      ${colours.border} ${colours.bg} ${colours.glow}
                    `}
                    title={node.error || node.name}
                  >
                    <div className="flex items-center gap-1">
                      <span className="text-[10px] leading-none">{icon}</span>
                      <span className={`text-[8px] font-mono font-bold truncate leading-tight ${colours.text}`}>
                        {node.name}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[7px] font-mono text-zinc-600 uppercase truncate">
                        {node.type}
                      </span>
                      <span className={`text-[7px] font-mono font-bold uppercase ${colours.text}`}>
                        {node.status}
                      </span>
                    </div>
                    {node.retry_count > 0 && (
                      <div className="text-[6px] font-mono text-orange-400">
                        retry {node.retry_count}/{node.max_retries ?? '?'}
                      </div>
                    )}
                  </div>
                </foreignObject>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 px-4 py-2 border-t border-matte-border/10 bg-black/5">
        {[
          { label: 'Running',   colour: 'bg-cyan-500' },
          { label: 'Done',      colour: 'bg-emerald-500' },
          { label: 'Failed',    colour: 'bg-red-500' },
          { label: 'Pending',   colour: 'bg-zinc-600' },
          { label: 'Skipped',   colour: 'bg-zinc-700' },
        ].map(({ label, colour }) => (
          <div key={label} className="flex items-center gap-1">
            <div className={`w-1.5 h-1.5 rounded-full ${colour}`} />
            <span className="text-[7px] font-mono text-zinc-600 uppercase">{label}</span>
          </div>
        ))}
        <div className="ml-auto flex items-center gap-3">
          <div className="flex items-center gap-1">
            <div className="w-3 h-px bg-zinc-600" />
            <span className="text-[7px] font-mono text-zinc-600">Dep</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-px bg-emerald-500 border-dashed" style={{borderTop: '1px dashed'}} />
            <span className="text-[7px] font-mono text-zinc-600">Success</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-px bg-red-500" style={{borderTop: '1px dashed'}} />
            <span className="text-[7px] font-mono text-zinc-600">Fail</span>
          </div>
        </div>
      </div>
    </div>
  );
};
