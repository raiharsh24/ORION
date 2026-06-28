import React from 'react';
import { Play, Pause, RotateCcw, Ban, CheckSquare, RefreshCw } from 'lucide-react';
import { useMissionStore } from '../../store';

// 1. TypeScript interface for Props
export interface MissionToolbarProps {
  missionId: string | null;
  status?: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  isLoading?: boolean;
  hasError?: boolean;
}

// 2. Export component
export const MissionToolbar: React.FC<MissionToolbarProps> = ({
  missionId,
  status = 'PENDING',
  isLoading = false,
  hasError = false,
}) => {
  const { 
    startMission, 
    pauseMission, 
    resumeMission, 
    restartMission, 
    retryMission, 
    cancelMission,
    clearMissions
  } = useMissionStore();

  // 3. Accessibility comments
  // role="toolbar" marks this panel as containing keyboard navigable controls
  // aria-disabled handles disabled control triggers when no mission is active

  // 4. Loading placeholder
  if (isLoading) {
    return (
      <div className="flex gap-2.5 p-3.5 bg-black/10 border-b border-matte-border/20 items-center animate-pulse">
        {[1, 2, 3, 4].map((n) => (
          <div key={n} className="h-8 w-20 bg-zinc-800 rounded-lg" />
        ))}
      </div>
    );
  }

  // 5. Error state
  if (hasError) {
    return (
      <div 
        className="p-3.5 bg-red-950/15 border-b border-red-900/30 text-xs font-mono text-red-400"
        role="alert"
      >
        Failed to initialize commands toolbar.
      </div>
    );
  }

  const handleCommand = (label: string) => {
    if (!missionId) return;
    switch (label) {
      case 'Start': startMission(missionId); break;
      case 'Pause': pauseMission(missionId); break;
      case 'Resume': resumeMission(missionId); break;
      case 'Restart': restartMission(missionId); break;
      case 'Retry': retryMission(missionId); break;
      case 'Cancel': cancelMission(missionId); break;
    }
  };

  const buttons = [
    { label: 'Start', icon: Play, statusRequired: ['PENDING'], disabled: !missionId },
    { label: 'Pause', icon: Pause, statusRequired: ['RUNNING'], disabled: !missionId },
    { label: 'Resume', icon: Play, statusRequired: ['PENDING'], disabled: !missionId },
    { label: 'Restart', icon: RotateCcw, statusRequired: ['COMPLETED', 'CANCELLED'], disabled: !missionId },
    { label: 'Retry', icon: RefreshCw, statusRequired: ['FAILED'], disabled: !missionId },
    { label: 'Cancel', icon: Ban, statusRequired: ['RUNNING', 'PENDING'], disabled: !missionId },
  ];

  return (
    <div 
      className="flex items-center justify-between gap-2.5 p-3.5 bg-black/15 border-b border-matte-border/25 w-full"
      role="toolbar"
      aria-label="Mission Actions Controls"
      aria-disabled={!missionId}
    >
      {!missionId ? (
        <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">
          Select a mission to enable controls
        </span>
      ) : (
        <div className="flex items-center gap-2">
          {buttons.map((btn) => {
            const isApplicable = btn.statusRequired.includes(status);
            const Icon = btn.icon;
            
            // Resume action matches PENDING but if it hasn't started yet, we show Start
            const activeMission = useMissionStore.getState().missions.find(m => m.id === missionId);
            const hasStarted = activeMission && activeMission.progress > 0;
            if (btn.label === 'Start' && hasStarted) return null;
            if (btn.label === 'Resume' && !hasStarted) return null;

            return (
              <button
                key={btn.label}
                disabled={btn.disabled || !isApplicable}
                onClick={() => handleCommand(btn.label)}
                className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-[10px] font-mono uppercase tracking-wider transition-all duration-200 border focus:outline-none focus:ring-1 focus:ring-cyan-glow/20
                  ${isApplicable && !btn.disabled
                    ? 'bg-zinc-900 border-cyan-border/30 text-cyan-glow hover:bg-cyan-dim/10 hover:border-cyan-glow/60 cursor-pointer hover:shadow-[0_0_10px_rgba(0,242,254,0.05)]'
                    : 'bg-zinc-950/40 border-matte-border/10 text-zinc-600 cursor-not-allowed'
                  }
                `}
                aria-label={`Command ${btn.label}`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{btn.label}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* Clear Archived Logs Command */}
      <button 
        onClick={clearMissions}
        className="flex items-center gap-1.5 px-3.5 py-1.5 bg-zinc-950/40 border border-matte-border/25 hover:border-matte-border/50 text-zinc-400 hover:text-zinc-200 rounded-lg text-[10px] font-mono uppercase tracking-wider transition-all duration-200 focus:outline-none"
        aria-label="Clear Completed Missions"
      >
        <CheckSquare className="w-3.5 h-3.5 text-zinc-500" />
        <span>Clear Archives</span>
      </button>
    </div>
  );
};

