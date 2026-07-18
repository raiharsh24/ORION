import React from 'react';

// 1. TypeScript interface for Props
export interface MissionProgressProps {
  progress?: number;
  status?: string;
  isLoading?: boolean;
  hasError?: boolean;
  durationMs?: number;
  activeTask?: string;
  plannerTasks?: { id: string; title: string; status: string }[];
}

// 2. Export component
export const MissionProgress: React.FC<MissionProgressProps> = ({
  progress = 0,
  status = 'UNKNOWN',
  isLoading = false,
  hasError = false,
  durationMs = 0,
  activeTask,
  plannerTasks,
}) => {
  // 3. Accessibility comments
  // role="progressbar" captures status updates dynamically
  // aria-valuenow communicates raw progress percentages

  // 4. Loading state
  if (isLoading) {
    return (
      <div className="flex flex-col items-center gap-3 bg-matte-card/20 p-6 border border-matte-border/20 rounded-xl w-44 animate-pulse">
        <div className="w-24 h-24 rounded-full border-4 border-zinc-800" />
        <div className="h-4 w-12 bg-zinc-800 rounded" />
      </div>
    );
  }

  // 5. Error state
  if (hasError) {
    return (
      <div 
        className="w-44 h-44 bg-red-950/15 border border-dashed border-red-900/30 rounded-xl flex items-center justify-center text-[10px] text-red-400 font-mono"
        role="alert"
      >
        Err Progress
      </div>
    );
  }

  // 6. Empty state fallback
  if (progress === null || progress === undefined) {
    return (
      <div className="text-[10px] text-zinc-500 font-mono w-44 text-center py-6 border border-dashed border-matte-border/30 rounded-xl">
        Progress Undefined
      </div>
    );
  }

  const strokeDashoffset = 220 - (220 * progress) / 100;

  // Estimate Remaining Time (ETA)
  const remainingSeconds = progress > 0 && progress < 100
    ? Math.max(0, Math.round((durationMs * (100 - progress)) / progress / 1000))
    : 0;

  return (
    <div 
      className="flex flex-col items-center gap-4 bg-matte-card/20 p-6 border border-matte-border/20 rounded-xl w-44 hover:border-matte-border/40 transition-colors"
      role="progressbar"
      aria-label="Overall execution progress"
      aria-valuenow={progress}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <h4 className="text-[9px] font-mono uppercase tracking-widest text-zinc-500 font-bold">
        Status Gauge
      </h4>

      <div className="relative w-28 h-28 flex items-center justify-center">
        {/* SVG Circular Gauge */}
        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 80 80">
          {/* Background circle */}
          <circle
            cx="40"
            cy="40"
            r="35"
            className="stroke-zinc-950/60 fill-none stroke-2"
          />
          {/* Progress circle */}
          <circle
            cx="40"
            cy="40"
            r="35"
            className={`fill-none stroke-2 transition-all duration-500 ease-out
              ${status === 'FAILED' ? 'stroke-red-500 shadow-[0_0_10px_rgba(239,68,68,0.3)]' : 'stroke-cyan-glow'}
            `}
            strokeDasharray="220"
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
          />
        </svg>

        {/* Core details absolute positioning inside radial layout */}
        <div className="absolute flex flex-col items-center text-center">
          <span className="text-xl font-extrabold tracking-tighter text-zinc-100 font-mono">
            {progress}%
          </span>
          <span className={`text-[8px] font-mono uppercase tracking-widest mt-0.5 font-bold
            ${status === 'FAILED' ? 'text-red-400' : 'text-cyan-glow'}
          `}>
            {status}
          </span>
        </div>
      </div>

      {status === 'RUNNING' && (
        <div className="flex flex-col gap-1 text-[9px] font-mono text-zinc-500 uppercase tracking-widest mt-1 border-t border-matte-border/10 pt-3 w-full text-center">
          <div>
            Elapsed: <span className="text-zinc-300 font-bold">{durationMs ? `${(durationMs / 1000).toFixed(0)}s` : '0s'}</span>
          </div>
          <div>
            ETA: <span className="text-cyan-glow font-bold">{progress > 0 ? `${remainingSeconds}s` : 'Estimating...'}</span>
          </div>
        </div>
      )}

      {status === 'COMPLETED' && (
        <div className="text-[9px] font-mono text-zinc-500 uppercase tracking-widest mt-1 border-t border-matte-border/10 pt-3 w-full text-center">
          Done: <span className="text-emerald-400 font-bold">{durationMs ? `${(durationMs / 1000).toFixed(0)}s` : '0s'}</span>
        </div>
      )}

      {status === 'FAILED' && (
        <div className="text-[9px] font-mono text-zinc-500 uppercase tracking-widest mt-1 border-t border-matte-border/10 pt-3 w-full text-center">
          Failed at: <span className="text-red-400 font-bold">{durationMs ? `${(durationMs / 1000).toFixed(0)}s` : '0s'}</span>
        </div>
      )}

      {status === 'CANCELLED' && (
        <div className="text-[9px] font-mono text-zinc-500 uppercase tracking-widest mt-1 border-t border-matte-border/10 pt-3 w-full text-center">
          Aborted at: <span className="text-yellow-500 font-bold">{durationMs ? `${(durationMs / 1000).toFixed(0)}s` : '0s'}</span>
        </div>
      )}

      {status === 'PENDING' && (
        <div className="text-[9px] font-mono text-zinc-500 uppercase tracking-widest mt-1 border-t border-matte-border/10 pt-3 w-full text-center">
          State: <span className="text-zinc-400 font-bold">In Queue</span>
        </div>
      )}

      {/* Live Execution State */}
      {activeTask && (
        <div className="text-[9px] font-mono mt-1 border-t border-matte-border/10 pt-3 w-full text-center">
          <div className="text-zinc-500 uppercase tracking-widest mb-1">Active Task</div>
          <div className="text-cyan-glow font-bold truncate">{activeTask}</div>
        </div>
      )}
      {plannerTasks && plannerTasks.length > 0 && (
        <div className="text-[9px] font-mono mt-1 border-t border-matte-border/10 pt-3 w-full text-left">
          <div className="text-zinc-500 uppercase tracking-widest mb-1.5 text-center">Plan Tasks</div>
          {plannerTasks.map((t) => (
            <div key={t.id} className="flex items-center gap-1.5 py-0.5">
              <span className={`w-1.5 h-1.5 rounded-full ${
                t.status === 'completed' ? 'bg-emerald-400' :
                t.status === 'running' ? 'bg-cyan-glow animate-pulse' :
                t.status === 'failed' ? 'bg-red-400' : 'bg-zinc-700'
              }`} />
              <span className={`truncate ${t.status === 'completed' ? 'text-emerald-400/70' : 'text-zinc-400'}`}>
                {t.title}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
