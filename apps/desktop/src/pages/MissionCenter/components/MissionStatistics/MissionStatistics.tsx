import React from 'react';
import { useMissionStore } from '../../store';

// 1. TypeScript interface for Props
export interface MissionStatisticsProps {
  missionId: string | null;
  isLoading?: boolean;
  hasError?: boolean;
}

// 2. Export component
export const MissionStatistics: React.FC<MissionStatisticsProps> = ({
  missionId,
  isLoading = false,
  hasError = false,
}) => {
  // 3. Accessibility comments
  // role="region" labels this as a statistics info display card
  // aria-label defines the scope of information

  const { missions, historyMissions } = useMissionStore();

  // 4. Loading placeholder
  if (isLoading) {
    return (
      <div 
        className="grid grid-cols-1 md:grid-cols-3 gap-4 p-6 animate-pulse"
        aria-busy="true"
        aria-label="Loading execution statistics"
      >
        {[1, 2, 3].map((n) => (
          <div key={n} className="h-20 bg-zinc-800 rounded-xl" />
        ))}
      </div>
    );
  }

  // 5. Error state
  if (hasError) {
    return (
      <div 
        className="p-6 bg-red-950/15 border border-red-900/30 text-xs font-mono text-red-400 rounded-xl"
        role="alert"
      >
        Failed to fetch diagnostics metrics.
      </div>
    );
  }

  // Compute live statistics dynamically
  const completedCount = missions.filter((m) => m.status === 'COMPLETED').length + historyMissions.filter((m) => m.status === 'COMPLETED').length;
  const failedCount = missions.filter((m) => m.status === 'FAILED').length + historyMissions.filter((m) => m.status === 'FAILED').length;
  const totalRun = completedCount + failedCount;
  const successRate = totalRun > 0 ? (completedCount / totalRun) * 100 : 0;

  const completedOrFailed = [
    ...missions.filter((m) => ['COMPLETED', 'FAILED'].includes(m.status)),
    ...historyMissions.filter((m) => ['COMPLETED', 'FAILED'].includes(m.status)),
  ];
  const totalDuration = completedOrFailed.reduce((acc, curr) => acc + curr.durationMs, 0);
  const averageDurationMs = completedOrFailed.length > 0 ? totalDuration / completedOrFailed.length : 0;

  return (
    <div 
      className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 p-6 bg-matte-card/15 border border-matte-border/20 rounded-xl"
      role="region"
      aria-label="OS Execution Statistics Summary"
    >
      {/* 6. Empty state fallback */}
      {!missionId && totalRun === 0 ? (
        <div className="col-span-full text-center py-6 text-xs font-mono text-zinc-500">
          No statistics active. Run a mission to monitor performance metrics.
        </div>
      ) : (
        <>
          {/* Card 1 */}
          <div className="p-4.5 bg-zinc-950/40 border border-matte-border/20 rounded-xl hover:border-matte-border/40 transition-colors">
            <h5 className="text-[9px] font-mono uppercase tracking-widest text-zinc-500 font-bold">Total Run</h5>
            <div className="text-xl font-bold font-mono text-zinc-200 mt-2">
              {totalRun} Tasks
            </div>
          </div>

          {/* Card 2 */}
          <div className="p-4.5 bg-zinc-950/40 border border-matte-border/20 rounded-xl hover:border-matte-border/40 transition-colors">
            <h5 className="text-[9px] font-mono uppercase tracking-widest text-zinc-500 font-bold">Success Rate</h5>
            <div className={`text-xl font-bold font-mono mt-2 ${successRate >= 80 ? 'text-emerald-400' : successRate >= 50 ? 'text-orange-400' : 'text-red-400'}`}>
              {totalRun > 0 ? `${successRate.toFixed(0)}%` : '100%'}
            </div>
          </div>

          {/* Card 3 */}
          <div className="p-4.5 bg-zinc-950/40 border border-matte-border/20 rounded-xl hover:border-matte-border/40 transition-colors">
            <h5 className="text-[9px] font-mono uppercase tracking-widest text-zinc-500 font-bold">Average Duration</h5>
            <div className="text-xl font-bold font-mono text-cyan-glow mt-2">
              {averageDurationMs > 0 ? `${(averageDurationMs / 1000).toFixed(1)}s` : '--'}
            </div>
          </div>

          {/* Card 4 */}
          <div className="p-4.5 bg-zinc-950/40 border border-matte-border/20 rounded-xl hover:border-matte-border/40 transition-colors">
            <h5 className="text-[9px] font-mono uppercase tracking-widest text-zinc-500 font-bold">Failed Checks</h5>
            <div className="text-xl font-bold font-mono text-red-400 mt-2">
              {failedCount} Errors
            </div>
          </div>
        </>
      )}
    </div>
  );
};
