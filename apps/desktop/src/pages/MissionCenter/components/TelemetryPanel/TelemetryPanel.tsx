import React from 'react';
import { useTelemetry } from '../../hooks';

// 1. TypeScript interface for Props
export interface TelemetryPanelProps {
  isLoading?: boolean;
  hasError?: boolean;
}

// 2. Export component
export const TelemetryPanel: React.FC<TelemetryPanelProps> = ({
  isLoading = false,
  hasError = false,
}) => {
  const { telemetry } = useTelemetry();

  // 3. Accessibility comments
  // role="status" makes this panel act as an announcement region for metric updates
  // aria-live="polite" avoids interrupting active screen reader readings

  // 4. Loading state
  if (isLoading) {
    return (
      <div 
        className="flex justify-between items-center px-4 py-2 border-t border-matte-border/20 bg-black/10 animate-pulse h-10 w-full"
        aria-busy="true"
        aria-label="Loading telemetry readouts"
      >
        <div className="h-3 w-20 bg-zinc-800 rounded" />
        <div className="h-3 w-28 bg-zinc-800 rounded" />
      </div>
    );
  }

  // 5. Error state
  if (hasError) {
    return (
      <div 
        className="px-4 py-2 bg-red-950/15 border-t border-red-900/30 text-[10px] font-mono text-red-400 text-center"
        role="alert"
      >
        Telemetry stream error.
      </div>
    );
  }

  // 6. Empty state fallback
  if (!telemetry) {
    return (
      <div className="px-4 py-2 text-[10px] font-mono text-zinc-600 text-center">
        No Telemetry data
      </div>
    );
  }

  return (
    <div 
      className="flex flex-wrap items-center justify-between gap-y-2 px-6 py-3 border-t border-matte-border/30 bg-black/25 text-[9px] font-mono text-zinc-500 uppercase tracking-widest w-full"
      role="status"
      aria-live="polite"
      aria-label="OS Diagnostic Telemetry Strip"
    >
      <div className="flex flex-wrap gap-x-6 gap-y-1">
        <span>Latency: <span className="text-cyan-glow font-bold">{telemetry.latency}ms</span></span>
        <span>FPS: <span className="text-zinc-300 font-bold">{telemetry.fps}</span></span>
        <span>Memory: <span className="text-zinc-300 font-bold">{telemetry.memory}MB</span></span>
        <span>Execution: <span className="text-zinc-300 font-bold">{telemetry.executionTimeMs}ms</span></span>
        <span>Events: <span className="text-zinc-300 font-bold">{telemetry.eventsCount}</span></span>
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-1">
        <span>Tool: <span className="text-purple-400 font-bold">{telemetry.currentTool || 'None'}</span></span>
        <span>Workflow: <span className="text-zinc-400 font-bold">{telemetry.workflow || 'None'}</span></span>
        <span>ID: <span className="text-zinc-400">{telemetry.missionId}</span></span>
      </div>
    </div>
  );
};
