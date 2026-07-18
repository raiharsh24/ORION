import React from 'react';
import type { Mission } from '../../types';
import type { ExecutionStatePayload } from '../../../../services/realtime/eventTypes';

// 1. TypeScript interface for Props
export interface MissionDetailsProps {
  mission: Mission | null;
  execState?: ExecutionStatePayload;
  isLoading?: boolean;
  hasError?: boolean;
}

// 2. Export component
export const MissionDetails: React.FC<MissionDetailsProps> = ({
  mission,
  execState,
  isLoading = false,
  hasError = false,
}) => {
  // 3. Accessibility comments
  // role="region" groups information for assistive technologies
  // aria-label defines the details metadata scope

  // 4. Loading state
  if (isLoading) {
    return (
      <div 
        className="p-6 bg-zinc-950/20 border border-matte-border/20 rounded-xl space-y-4 animate-pulse"
        aria-busy="true"
        aria-label="Loading mission details"
      >
        <div className="h-4 w-1/3 bg-zinc-800 rounded" />
        <div className="h-3.5 w-full bg-zinc-800 rounded" />
        <div className="h-3.5 w-5/6 bg-zinc-800 rounded" />
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
        Failed to fetch detailed mission schemas.
      </div>
    );
  }

  return (
    <div 
      className="p-6 bg-matte-card/15 border border-matte-border/20 rounded-xl flex flex-col gap-4"
      role="region"
      aria-label="Active Mission Details Panel"
    >
      <div className="border-b border-matte-border/20 pb-3 flex justify-between items-center">
        <h4 className="text-[10px] font-mono uppercase tracking-widest text-zinc-500">
          Mission Config & Parameters
        </h4>
        {mission && (
          <span className="text-[8px] font-mono px-2 py-0.5 rounded bg-zinc-900 border border-matte-border/30 text-zinc-400">
            ID: {mission.id}
          </span>
        )}
      </div>

      {/* 6. Empty state fallback */}
      {!mission ? (
        <div className="text-center py-6 text-xs font-mono text-zinc-500">
          No active mission selected. Select an item to inspect.
        </div>
      ) : (
        /* Details layout metadata */
        <div className="space-y-3.5 font-mono text-[11px] text-zinc-300 select-text">
          <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-matte-border/10">
            <span className="text-zinc-500 uppercase tracking-wider text-[9px]">Name</span>
            <span className="col-span-2 text-zinc-200 font-bold">{mission.name}</span>
          </div>

          <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-matte-border/10">
            <span className="text-zinc-500 uppercase tracking-wider text-[9px]">Description</span>
            <span className="col-span-2 text-zinc-400 leading-relaxed">{mission.description}</span>
          </div>

          <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-matte-border/10">
            <span className="text-zinc-500 uppercase tracking-wider text-[9px]">Workflow</span>
            <span className="col-span-2 text-purple-400 font-bold">{mission.workflowName || 'N/A'}</span>
          </div>

          <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-matte-border/10">
            <span className="text-zinc-500 uppercase tracking-wider text-[9px]">Current Tool</span>
            <span className="col-span-2 text-zinc-400">{mission.currentTool || 'None'}</span>
          </div>

          <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-matte-border/10">
            <span className="text-zinc-500 uppercase tracking-wider text-[9px]">Steps List</span>
            <span className="col-span-2 text-zinc-400">
              {mission.steps.length > 0 ? mission.steps.join(' → ') : 'None'}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-matte-border/10">
            <span className="text-zinc-500 uppercase tracking-wider text-[9px]">Time Metadata</span>
            <span className="col-span-2 text-zinc-400">
              Created: {mission.createdAt || '--'} | Started: {mission.startedAt || '--'} {mission.finishedAt ? `| Finished: ${mission.finishedAt}` : ''}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-matte-border/10">
            <span className="text-zinc-500 uppercase tracking-wider text-[9px]">Priority</span>
            <span className="col-span-2 text-cyan-glow font-bold">{mission.priority}</span>
          </div>

          {mission.error && (
            <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-red-900/10">
              <span className="text-red-400 uppercase tracking-wider text-[9px]">Error Detail</span>
              <span className="col-span-2 text-red-400 leading-normal bg-red-950/20 border border-red-900/30 p-2 rounded-lg font-bold">
                {mission.error}
              </span>
            </div>
          )}

          {/* Execution State from live pipeline */}
          {execState && execState.execution_stage !== 'idle' && (
            <div className="flex flex-col gap-2 mt-4 border-t border-matte-border/10 pt-4">
              <span className="text-zinc-500 uppercase tracking-wider text-[9px]">Live Execution State</span>
              <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-matte-border/10">
                <span className="text-zinc-500 uppercase tracking-wider text-[9px]">Stage</span>
                <span className="col-span-2 text-cyan-glow font-bold">{execState.execution_stage}</span>
              </div>
              {execState.active_task && (
                <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-matte-border/10">
                  <span className="text-zinc-500 uppercase tracking-wider text-[9px]">Active Task</span>
                  <span className="col-span-2 text-zinc-200 font-bold">{execState.active_task}</span>
                </div>
              )}
              {execState.selected_tool && (
                <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-matte-border/10">
                  <span className="text-zinc-500 uppercase tracking-wider text-[9px]">Selected Tool</span>
                  <span className="col-span-2 text-purple-400 font-bold">{execState.selected_tool}</span>
                </div>
              )}
              <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-matte-border/10">
                <span className="text-zinc-500 uppercase tracking-wider text-[9px]">Confidence</span>
                <span className="col-span-2">
                  <span className={`font-bold ${execState.confidence > 0.7 ? 'text-emerald-400' : execState.confidence > 0.4 ? 'text-orange-400' : 'text-zinc-400'}`}>
                    {(execState.confidence * 100).toFixed(0)}%
                  </span>
                </span>
              </div>
              {execState.completed_tasks.length > 0 && (
                <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-matte-border/10">
                  <span className="text-zinc-500 uppercase tracking-wider text-[9px]">Done</span>
                  <span className="col-span-2 text-emerald-400">{execState.completed_tasks.length} / {execState.planner_tasks.length} tasks</span>
                </div>
              )}
            </div>
          )}

          {/* JSON viewer schema bindings for extra key-value metadata logs */}
          <div className="flex flex-col gap-2 mt-4">
            <span className="text-zinc-500 uppercase tracking-wider text-[9px]">JSON Parameter Settings</span>
            <pre className="p-3 bg-zinc-950/60 border border-matte-border/25 rounded-lg text-[9px] text-cyan-glow/85 overflow-x-auto scrollbar-thin max-h-36 select-all font-mono leading-relaxed">
              {JSON.stringify({
                id: mission.id,
                name: mission.name,
                priority: mission.priority,
                status: mission.status,
                workflowName: mission.workflowName,
                stepsCount: mission.steps.length,
                durationMs: mission.durationMs,
                error: mission.error || null,
              }, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};
