import React from 'react';
import type { GraphNode } from '../types';
import { useKnowledgeStore } from '../store/useKnowledgeStore';

interface NodeTooltipProps {
  node: GraphNode;
  x: number;
  y: number;
}

export const NodeTooltip: React.FC<NodeTooltipProps> = ({ node, x, y }) => {
  const showFolders = useKnowledgeStore((state) => state.showFolders);

  const getFolderGroup = (n: GraphNode): string => {
    const path = n.metadata?.path || '';
    if (!path) return 'unknown';
    const parts = path.split('/');
    return parts.length <= 1 ? 'root' : parts.slice(0, -1).join('/');
  };

  const groupName = showFolders ? getFolderGroup(node) : node.category;
  const groupLabel = showFolders ? 'Folder' : 'Department';

  const stringToColor = (str: string): string => {
    if (!str) return '#71717a';
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const h = Math.abs(hash) % 360;
    return `hsl(${h}, 75%, 50%)`;
  };

  const activeColor = stringToColor(groupName);

  return (
    <div
      style={{
        position: 'absolute',
        left: x + 15,
        top: y + 15,
        pointerEvents: 'none',
        zIndex: 50
      }}
      className="bg-black/80 border border-cyan-border/25 backdrop-blur-md px-4 py-3 rounded-xl shadow-[0_4px_20px_rgba(0,242,254,0.1)] font-mono text-[10px] w-64 space-y-1.5 animate-in fade-in zoom-in-95 duration-150 select-none text-left"
    >
      <div className="flex justify-between items-start gap-2">
        <span className="font-bold text-zinc-100 truncate text-xs">{node.title}</span>
        <span
          style={{ borderColor: `${activeColor}30`, color: activeColor, backgroundColor: `${activeColor}08` }}
          className="text-[8px] font-extrabold uppercase px-1.5 py-0.5 rounded border tracking-wider"
        >
          {node.type}
        </span>
      </div>

      <p className="text-zinc-400 text-[9px] leading-relaxed line-clamp-2">
        {node.description || 'No description provided.'}
      </p>

      <div className="text-[9px] text-zinc-300">
        <span className="text-zinc-500">{groupLabel}:</span> <span style={{ color: activeColor }} className="font-semibold">{groupName}</span>
      </div>

      <div className="pt-1.5 border-t border-matte-border/20 flex justify-between text-[8px] text-zinc-500 uppercase tracking-wider">
        <span>Status: <span className="font-bold text-emerald-400">{node.status}</span></span>
        <span>Importance: {(node.importance * 100).toFixed(0)}%</span>
      </div>

      <div className="pt-1.5 text-[8px] text-cyan-400/90 font-bold uppercase tracking-wider text-center animate-pulse">
        ⚡ Click to filter connections
      </div>
    </div>
  );
};
export default NodeTooltip;
