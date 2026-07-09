import React from 'react';
import { useKnowledgeStore } from '../store/useKnowledgeStore';
import { Activity } from 'lucide-react';

export const Legend: React.FC = () => {
  const { nodes, departmentFilter, setDepartmentFilter } = useKnowledgeStore();

  const categoriesList = [
    { name: 'Manifest', color: '#00f2fe' },
    { name: 'Personal', color: '#ec4899' },
    { name: 'Business', color: '#3b82f6' },
    { name: 'Product', color: '#10b981' },
    { name: 'Development', color: '#8b5cf6' },
    { name: 'Research', color: '#eab308' },
    { name: 'Memory', color: '#14b8a6' },
    { name: 'Documents', color: '#64748b' }
  ];

  const getCountForCat = (catName: string) => {
    return nodes.filter((n) => n.category === catName).length;
  };

  const statusCounts = {
    HEALTHY: nodes.filter((n) => n.status === 'HEALTHY').length,
    WARNING: nodes.filter((n) => n.status === 'WARNING').length,
    DEPRECATED: nodes.filter((n) => n.status === 'DEPRECATED').length,
    EXPERIMENTAL: nodes.filter((n) => n.status === 'EXPERIMENTAL').length,
    BROKEN: nodes.filter((n) => n.status === 'BROKEN' || n.status === 'ERROR').length,
    DISCONNECTED: nodes.filter((n) => n.status === 'DISCONNECTED' || n.status === 'OFFLINE').length
  };

  return (
    <div className="absolute top-5 left-5 bg-black/55 border border-matte-border/30 backdrop-blur-md px-4 py-4.5 rounded-2xl w-60 select-none space-y-4 pointer-events-auto z-20">
      {/* System Status counts */}
      <div className="space-y-2">
        <h4 className="font-mono text-[9px] text-zinc-500 uppercase tracking-widest flex items-center gap-1.5">
          <Activity className="w-3 h-3 text-cyan-glow" /> System Health Diagnostics
        </h4>
        <div className="grid grid-cols-2 gap-2 text-[9px] font-mono">
          <div className="flex items-center gap-1.5 p-1.5 bg-zinc-900/35 border border-matte-border/15 rounded-lg text-cyan-glow">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-glow" />
            <span>OK: {statusCounts.HEALTHY}</span>
          </div>
          <div className="flex items-center gap-1.5 p-1.5 bg-zinc-900/35 border border-matte-border/15 rounded-lg text-amber-400">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
            <span>WARN: {statusCounts.WARNING}</span>
          </div>
          <div className="flex items-center gap-1.5 p-1.5 bg-zinc-900/35 border border-matte-border/15 rounded-lg text-purple-400">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-500" />
            <span>DEP: {statusCounts.DEPRECATED}</span>
          </div>
          <div className="flex items-center gap-1.5 p-1.5 bg-zinc-900/35 border border-matte-border/15 rounded-lg text-blue-400">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
            <span>EXP: {statusCounts.EXPERIMENTAL}</span>
          </div>
          <div className="flex items-center gap-1.5 p-1.5 bg-zinc-900/35 border border-matte-border/15 rounded-lg text-red-400 col-span-2">
            <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
            <span>BROKEN/ERR: {statusCounts.BROKEN}</span>
          </div>
        </div>
      </div>

      {/* Cluster/Category filters */}
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <h4 className="font-mono text-[9px] text-zinc-500 uppercase tracking-widest">
            Department Clusters
          </h4>
          {departmentFilter && (
            <button
              onClick={() => setDepartmentFilter(null)}
              className="text-[8px] font-mono text-cyan-glow hover:underline uppercase tracking-wider cursor-pointer"
            >
              Reset
            </button>
          )}
        </div>
        <div className="space-y-1 max-h-[140px] overflow-y-auto scrollbar-none pr-1">
          {categoriesList.map((cat) => {
            const count = getCountForCat(cat.name);
            if (count === 0) return null;
            const isActive = departmentFilter === cat.name;

            return (
              <button
                key={cat.name}
                onClick={() => setDepartmentFilter(isActive ? null : cat.name)}
                className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg border font-mono text-[9px] uppercase tracking-wider tracking-tight transition-all cursor-pointer
                  ${isActive
                    ? 'bg-zinc-800/80 border-cyan-glow/40 text-zinc-100 font-bold'
                    : 'bg-zinc-900/25 border-transparent text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/30'
                  }
                `}
              >
                <div className="flex items-center gap-2">
                  <span style={{ backgroundColor: cat.color }} className="w-2 h-2 rounded-full flex-shrink-0" />
                  <span>{cat.name}</span>
                </div>
                <span className="text-[8px] font-bold text-zinc-500">{count}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
export default Legend;
