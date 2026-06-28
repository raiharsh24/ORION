import React from 'react';
import { useMissionStore } from '../../store';
import type { Mission } from '../../types';

// 1. TypeScript interface for Props
export interface MissionHistoryProps {
  isOpen: boolean;
  onClose: () => void;
  isLoading?: boolean;
  hasError?: boolean;
  archivedMissions?: Mission[];
}

// 2. Export component
export const MissionHistory: React.FC<MissionHistoryProps> = ({
  isOpen,
  onClose,
  isLoading = false,
  hasError = false,
  archivedMissions = [],
}) => {
  // 3. Accessibility comments
  // role="dialog" marks this drawer/panel as containing modal helper content
  // aria-hidden toggles based on open/closed properties

  const { historyMissions } = useMissionStore();

  if (!isOpen) return null;

  // 4. Loading placeholder
  if (isLoading) {
    return (
      <div 
        className="fixed inset-y-0 right-0 w-80 bg-matte-card border-l border-matte-border/30 p-6 animate-pulse z-40"
        aria-busy="true"
        aria-label="Loading history drawer"
      >
        <div className="h-6 w-32 bg-zinc-800 rounded mb-6" />
        {[1, 2, 3].map((n) => (
          <div key={n} className="h-20 bg-zinc-850 rounded-xl mb-4" />
        ))}
      </div>
    );
  }

  // 5. Error state
  if (hasError) {
    return (
      <div 
        className="fixed inset-y-0 right-0 w-80 bg-red-950/20 border-l border-red-900/30 p-6 flex flex-col justify-center items-center text-center gap-2 z-40"
        role="alert"
      >
        <span className="text-xs font-bold text-red-400 uppercase tracking-wider">History Error</span>
        <p className="text-[10px] text-zinc-500 font-mono">Failed to fetch archived history list.</p>
        <button onClick={onClose} className="mt-4 px-3 py-1.5 bg-zinc-900 border border-matte-border rounded text-[10px] uppercase font-mono text-zinc-400">
          Close
        </button>
      </div>
    );
  }

  const combinedHistory: Mission[] = archivedMissions.length > 0 
    ? archivedMissions 
    : historyMissions.length > 0 
      ? historyMissions 
      : [
          {
            id: 'h1',
            name: 'Verify Action Engine',
            description: 'Run tool validation suite tests',
            status: 'COMPLETED',
            priority: 'MEDIUM',
            progress: 100,
            currentStep: 'Completed',
            steps: [],
            durationMs: 8200,
            startedAt: '11:50:00',
            finishedAt: '11:50:08',
          },
          {
            id: 'h2',
            name: 'Scan Desktop Clipboard',
            description: 'Fetch permissions and read clipboard content',
            status: 'CANCELLED',
            priority: 'LOW',
            progress: 60,
            currentStep: 'Read clipboard',
            steps: [],
            durationMs: 3100,
            startedAt: '11:45:00',
            finishedAt: '11:45:03',
          }
        ];

  return (
    <div 
      className="fixed inset-y-0 right-0 w-80 bg-matte-card border-l border-matte-border shadow-[0_0_50px_rgba(0,0,0,0.8)] z-40 flex flex-col transition-all duration-300"
      role="dialog"
      aria-label="Mission History Archives Panel"
      aria-modal="true"
    >
      {/* Header */}
      <div className="p-4.5 border-b border-matte-border/30 flex justify-between items-center bg-black/10">
        <h3 className="text-xs font-bold text-zinc-200 tracking-widest font-mono uppercase">
          History Logs
        </h3>
        <button 
          onClick={onClose}
          className="text-zinc-500 hover:text-zinc-300 focus:outline-none text-[10px] font-mono uppercase tracking-wider border border-matte-border/30 px-2.5 py-1 rounded"
          aria-label="Close History Panel"
        >
          Close
        </button>
      </div>

      {/* 6. Empty state fallback */}
      {combinedHistory.length === 0 ? (
        <div className="flex-1 flex flex-col justify-center items-center text-center p-6 text-zinc-500">
          <span className="text-xs font-mono tracking-wider">No Archive Logs</span>
          <p className="text-[10px] text-zinc-600 font-mono mt-1">No completed or aborted missions.</p>
        </div>
      ) : (
        /* History Archive Items Container */
        <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin">
          {combinedHistory.map((m) => {
            const statusColor = m.status === 'COMPLETED' ? 'text-emerald-400' : 'text-yellow-500';
            return (
              <div 
                key={m.id}
                className="p-3.5 bg-zinc-950/40 border border-matte-border/20 rounded-xl flex flex-col gap-2 hover:border-matte-border/50 transition-colors"
              >
                <div className="flex justify-between items-start gap-2">
                  <h4 className="text-[11px] font-bold text-zinc-200 truncate">{m.name}</h4>
                  <span className={`text-[8px] font-mono uppercase font-bold tracking-wider ${statusColor}`}>
                    {m.status}
                  </span>
                </div>
                <p className="text-[10px] text-zinc-500 font-mono leading-relaxed truncate">{m.description}</p>
                <div className="flex justify-between text-[9px] text-zinc-600 font-mono pt-2 border-t border-matte-border/10">
                  <span>Duration: {(m.durationMs / 1000).toFixed(1)}s</span>
                  <span>End: {m.finishedAt}</span>
                </div>
              </div>
            );
          })}
          {/* TODO: Bind action to reload history items lists dynamically */}
        </div>
      )}
    </div>
  );
};
