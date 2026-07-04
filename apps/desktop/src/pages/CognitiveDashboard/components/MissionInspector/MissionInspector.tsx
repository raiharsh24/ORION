import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../../../../components/ui/Card';
import { Button } from '../../../../components/ui/Button';
import { useMissionStore } from '../../../MissionCenter/store';
import {
  Play, Pause, RotateCcw, XCircle, RefreshCw,
  CheckCircle, FileText, AlertTriangle,
} from 'lucide-react';

export const MissionInspector: React.FC = () => {
  const {
    missions, activeMissionId, selectMission,
    startMission, pauseMission, resumeMission,
    cancelMission, retryMission, confirmMissionAction,
  } = useMissionStore();

  const [activeTab, setActiveTab] = useState<'controls' | 'logs' | 'files'>('controls');

  const mission = missions.find((m) => m.id === activeMissionId) || null;
  const logs = mission?.logs || [];
  const generatedFiles = mission?.metadata?.generated_files || [];

  const handleStart = () => { if (mission) startMission(mission.id); };
  const handlePause = () => { if (mission) pauseMission(mission.id); };
  const handleResume = () => { if (mission) resumeMission(mission.id); };
  const handleCancel = () => { if (mission) cancelMission(mission.id); };
  const handleRetry = () => { if (mission) retryMission(mission.id); };
  const handleApprove = () => { if (mission) confirmMissionAction(mission.id, true); };
  const handleDeny = () => { if (mission) confirmMissionAction(mission.id, false); };

  const activeStatus = mission?.status as any;
  const isRunning = activeStatus === 'RUNNING';
  const isPaused = activeStatus === 'PAUSED';
  const isPending = activeStatus === 'PENDING';
  const isFailed = activeStatus === 'FAILED';
  const isCancelled = activeStatus === 'CANCELLED';
  const isCompleted = activeStatus === 'COMPLETED';
  const needsApproval = mission?.metadata?.pending_confirmation != null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Mission Inspector</CardTitle>
      </CardHeader>
      <CardContent>
        {/* Mission selector */}
        <div className="mb-4">
          {missions.length === 0 ? (
            <div className="text-xs text-zinc-600 font-mono py-4 text-center">
              No missions available. Start a mission to inspect it.
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {missions.map((m) => (
                <button
                  key={m.id}
                  onClick={() => selectMission(m.id)}
                  className={`px-3 py-1.5 rounded-lg text-[9px] font-mono uppercase tracking-widest border transition-colors ${
                    m.id === activeMissionId
                      ? 'bg-cyan-dim/20 border-cyan-border/50 text-cyan-glow'
                      : 'bg-black/20 border-matte-border/20 text-zinc-500 hover:text-zinc-300'
                  }`}
                >
                  {m.name.slice(0, 20)}
                </button>
              ))}
            </div>
          )}
        </div>

        {mission && (
          <>
            {/* Mission status bar */}
            <div className="flex items-center justify-between mb-4 p-3 rounded-xl bg-black/20 border border-matte-border/20">
              <div className="flex items-center gap-3">
                <span
                  className={`w-2.5 h-2.5 rounded-full animate-pulse ${
                    isRunning ? 'bg-cyan-glow' :
                    isCompleted ? 'bg-emerald-400' :
                    isFailed ? 'bg-red-400' :
                    isPaused ? 'bg-amber-400' :
                    'bg-zinc-600'
                  }`}
                />
                <div>
                  <span className="text-sm font-mono font-bold text-zinc-200">{mission.name}</span>
                  <span className="text-[9px] font-mono text-zinc-600 ml-3 uppercase tracking-wider">
                    {activeStatus}
                  </span>
                </div>
              </div>
              <span className="text-[10px] font-mono text-zinc-500">
                {mission.progress.toFixed(0)}%
              </span>
            </div>

            {/* Tab bar */}
            <div className="flex border-b border-matte-border/20 mb-4">
              {(['controls', 'logs', 'files'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 text-[9px] font-mono uppercase tracking-widest border-b-2 transition-colors ${
                    activeTab === tab
                      ? 'border-cyan-glow text-cyan-glow'
                      : 'border-transparent text-zinc-500 hover:text-zinc-300'
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Controls tab */}
            {activeTab === 'controls' && (
              <div className="space-y-4">
                {/* Action buttons */}
                <div className="grid grid-cols-2 gap-2">
                  {(isPending || isFailed || isCancelled) && (
                    <Button variant="primary" size="sm" onClick={handleStart}>
                      <Play className="w-3 h-3" /> Start
                    </Button>
                  )}
                  {isRunning && (
                    <Button variant="secondary" size="sm" onClick={handlePause}>
                      <Pause className="w-3 h-3" /> Pause
                    </Button>
                  )}
                  {isPaused && (
                    <Button variant="primary" size="sm" onClick={handleResume}>
                      <Play className="w-3 h-3" /> Resume
                    </Button>
                  )}
                  {isRunning && (
                    <Button variant="danger" size="sm" onClick={handleCancel}>
                      <XCircle className="w-3 h-3" /> Cancel
                    </Button>
                  )}
                  {isFailed && (
                    <Button variant="outline" size="sm" onClick={handleRetry}>
                      <RefreshCw className="w-3 h-3" /> Retry
                    </Button>
                  )}
                  {(isCompleted || isCancelled) && (
                    <Button variant="outline" size="sm" onClick={() => selectMission(mission.id)}>
                      <RotateCcw className="w-3 h-3" /> Restart
                    </Button>
                  )}
                </div>

                {/* Progress bar */}
                <div>
                  <div className="flex justify-between text-[9px] font-mono text-zinc-600 mb-1">
                    <span>Progress</span>
                    <span>{mission.progress.toFixed(0)}%</span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-zinc-800 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        isRunning ? 'bg-cyan-glow' :
                        isCompleted ? 'bg-emerald-400' :
                        isFailed ? 'bg-red-400' :
                        'bg-zinc-600'
                      }`}
                      style={{ width: `${mission.progress}%` }}
                    />
                  </div>
                </div>

                {/* Step info */}
                {mission.steps && mission.steps.length > 0 && (
                  <div className="space-y-1">
                    {mission.steps.map((step, i) => (
                      <div
                        key={i}
                        className={`flex items-center gap-2 px-2 py-1 rounded text-[10px] font-mono ${
                          i === mission.steps.indexOf(mission.currentStep)
                            ? 'bg-cyan-dim/10 text-cyan-glow'
                            : 'text-zinc-600'
                        }`}
                      >
                        {i < mission.steps.indexOf(mission.currentStep) ? (
                          <CheckCircle className="w-3 h-3 text-emerald-400" />
                        ) : i === mission.steps.indexOf(mission.currentStep) ? (
                          <div className="w-3 h-3 rounded-full border-2 border-cyan-glow border-t-transparent animate-spin" />
                        ) : (
                          <div className="w-3 h-3 rounded-full border border-zinc-700" />
                        )}
                        <span>{step}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Approval dialog */}
                {needsApproval && (
                  <div className="p-3 rounded-xl bg-amber-500/5 border border-amber-500/20">
                    <div className="flex items-center gap-2 mb-2">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                      <span className="text-[9px] font-mono uppercase tracking-widest text-amber-400">
                        Approval Required
                      </span>
                    </div>
                    <p className="text-[9px] font-mono text-zinc-400 mb-3">
                      {mission.metadata.pending_confirmation?.prompt}
                    </p>
                    <div className="flex gap-2">
                      <Button variant="danger" size="sm" onClick={handleDeny}>
                        <XCircle className="w-3 h-3" /> Deny
                      </Button>
                      <Button variant="primary" size="sm" onClick={handleApprove}>
                        <CheckCircle className="w-3 h-3" /> Approve
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Logs tab */}
            {activeTab === 'logs' && (
              <div className="space-y-1 max-h-64 overflow-y-auto scrollbar-thin">
                {logs.length === 0 ? (
                  <div className="text-[10px] text-zinc-600 font-mono py-4 text-center">
                    No logs for this mission.
                  </div>
                ) : (
                  logs.map((log, i) => (
                    <div key={i} className="flex items-start gap-2 px-2 py-1 hover:bg-white/5 rounded">
                      <span className="text-[8px] font-mono text-zinc-600 flex-shrink-0 w-14">
                        {log.time}
                      </span>
                      <span className={`text-[9px] font-mono flex-shrink-0 w-10 ${
                        log.level === 'ERROR' ? 'text-red-400' :
                        log.level === 'WARN' ? 'text-amber-400' :
                        log.level === 'SUCCESS' ? 'text-emerald-400' :
                        log.level === 'INFO' ? 'text-cyan-glow' :
                        'text-zinc-600'
                      }`}>
                        {log.level}
                      </span>
                      <span className="text-[9px] font-mono text-zinc-400 truncate">{log.msg}</span>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Files tab */}
            {activeTab === 'files' && (
              <div className="space-y-1">
                {generatedFiles.length === 0 ? (
                  <div className="text-[10px] text-zinc-600 font-mono py-4 text-center">
                    No files generated for this mission.
                  </div>
                ) : (
                  generatedFiles.map((file: any, i: number) => (
                    <div
                      key={i}
                      className="flex items-center gap-3 px-3 py-2 rounded-xl bg-black/20 border border-matte-border/20 hover:bg-white/5 transition-colors cursor-pointer"
                    >
                      <FileText className="w-4 h-4 text-cyan-glow flex-shrink-0" />
                      <div className="min-w-0 flex-1">
                        <div className="text-xs font-mono text-zinc-300 truncate">{file.name}</div>
                        <div className="text-[8px] font-mono text-zinc-600 truncate">{file.path}</div>
                      </div>
                      <span className="text-[9px] font-mono text-zinc-600 flex-shrink-0">
                        {file.size ? `${(file.size / 1024).toFixed(1)}KB` : ''}
                      </span>
                    </div>
                  ))
                )}
              </div>
            )}
          </>
        )}

        {/* Empty state when no goal selected */}
        {!mission && missions.length > 0 && (
          <div className="text-xs text-zinc-600 font-mono text-center py-8">
            Select a mission above to inspect its details and controls.
          </div>
        )}
      </CardContent>
    </Card>
  );
};
