import React, { useState, useEffect, useRef } from 'react';
import { useMissionStore } from '../../store';

// 1. TypeScript interface for Props
export interface MissionLogsProps {
  missionId: string | null;
  isLoading?: boolean;
  hasError?: boolean;
}

// 2. Export component
export const MissionLogs: React.FC<MissionLogsProps> = ({
  missionId,
  isLoading = false,
  hasError = false,
}) => {
  // 3. Accessibility comments
  // role="log" signals an live log output channel
  // aria-live="polite" ensures new messages are read correctly by assistive devices

  const { missions } = useMissionStore();
  const activeMission = missions.find((m) => m.id === missionId);
  const logs = activeMission?.logs || [];

  const [activeFilter, setActiveFilter] = useState<'ALL' | 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS'>('ALL');
  const consoleEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll effect
  useEffect(() => {
    if (consoleEndRef.current) {
      consoleEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  // 4. Loading state
  if (isLoading) {
    return (
      <div 
        className="h-60 bg-zinc-950 p-4 border border-matte-border/20 rounded-xl space-y-2.5 animate-pulse"
        aria-busy="true"
        aria-label="Loading execution logs"
      >
        {[1, 2, 3, 4].map((n) => (
          <div key={n} className="h-3.5 bg-zinc-900 rounded w-5/6" />
        ))}
      </div>
    );
  }

  // 5. Error state
  if (hasError) {
    return (
      <div 
        className="h-60 bg-red-950/10 border border-red-900/20 p-6 flex items-center justify-center text-xs font-mono text-red-400 rounded-xl"
        role="alert"
      >
        Failed to capture live streaming logs console.
      </div>
    );
  }

  // Filter logs based on chosen tab
  const filteredLogs = logs.filter((log) => {
    if (activeFilter === 'ALL') return true;
    if (activeFilter === 'INFO') return log.level === 'INFO' || log.level === 'DEBUG';
    return log.level === activeFilter;
  });

  return (
    <div className="flex flex-col gap-3 bg-matte-card/15 p-4 border border-matte-border/25 rounded-xl flex-1 hover:border-matte-border/40 transition-colors">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center border-b border-matte-border/20 pb-3 gap-3">
        <div className="flex items-center gap-3">
          <h4 className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 font-bold">
            Live Agent Console Logs
          </h4>
          <span className="text-[8px] font-mono px-2 py-0.5 bg-cyan-dim text-cyan-glow border border-cyan-border/20 rounded-sm font-bold uppercase">
            {missionId ? `Mission: ${missionId}` : 'No active mission'}
          </span>
        </div>

        {/* Log Filter Tabs */}
        {missionId && (
          <div className="flex bg-zinc-950/60 border border-matte-border/20 rounded-lg p-0.5">
            {(['ALL', 'INFO', 'WARN', 'ERROR', 'SUCCESS'] as const).map((lvl) => (
              <button
                key={lvl}
                onClick={() => setActiveFilter(lvl)}
                className={`px-2 py-1 text-[8px] font-mono rounded-md uppercase tracking-wider transition-all focus:outline-none
                  ${activeFilter === lvl 
                    ? 'bg-cyan-glow/15 text-cyan-glow font-bold' 
                    : 'text-zinc-500 hover:text-zinc-300'
                  }
                `}
              >
                {lvl}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 6. Empty state fallback */}
      {!missionId ? (
        <div className="h-44 flex items-center justify-center text-center text-xs font-mono text-zinc-600">
          Logs console inactive. Select a mission to stream.
        </div>
      ) : filteredLogs.length === 0 ? (
        <div className="h-44 flex items-center justify-center text-center text-xs font-mono text-zinc-600">
          No logs matching filter level [{activeFilter}].
        </div>
      ) : (
        /* Logs Terminal Console container */
        <div 
          className="h-44 overflow-y-auto font-mono text-[10px] space-y-1.5 text-zinc-300 pr-2 scrollbar-thin select-text"
          role="log"
          aria-live="polite"
        >
          {filteredLogs.map((log, index) => {
            const levelColors = {
              INFO: 'text-zinc-500',
              DEBUG: 'text-purple-400',
              SUCCESS: 'text-emerald-400 font-bold',
              WARN: 'text-orange-400 font-bold',
              ERROR: 'text-red-400 font-bold animate-pulse',
            };
            return (
              <div key={index} className="flex gap-3 hover:bg-white/[0.01] py-0.5 px-1 rounded transition-colors items-start">
                <span className="text-zinc-600 flex-shrink-0 select-none">{log.time}</span>
                <span className={`w-14 uppercase tracking-wider font-bold flex-shrink-0 select-none ${levelColors[log.level]}`}>
                  [{log.level}]
                </span>
                <span className="text-zinc-300 break-all leading-normal flex-1">{log.msg}</span>
              </div>
            );
          })}
          {/* Scroll anchor */}
          <div ref={consoleEndRef} />
        </div>
      )}
    </div>
  );
};
