import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useMissionStore, useTelemetryStore, useKernelStore, useHealthStore, useWorkflowStore } from './store';
import { useRealtime } from '../../services/realtime/hooks/useRealtime';
import { useMissionEvents } from '../../services/realtime/hooks/useMissionEvents';
import { useTelemetry } from '../../services/realtime/hooks/useTelemetry';
import { useKernelEvents } from '../../services/realtime/hooks/useKernelEvents';
import type { ConnectionState } from '../../services/realtime/streamManager';

// Core Subcomponents Imports
import { MissionSidebar } from './components/MissionSidebar/MissionSidebar';
import { MissionToolbar } from './components/MissionToolbar/MissionToolbar';
import { MissionProgress } from './components/MissionProgress/MissionProgress';
import { MissionTimeline } from './components/MissionTimeline/MissionTimeline';
import { MissionLogs } from './components/MissionLogs/MissionLogs';
import { MissionHistory } from './components/MissionHistory/MissionHistory';
import { MissionStatistics } from './components/MissionStatistics/MissionStatistics';
import { MissionDetails } from './components/MissionDetails/MissionDetails';
import { KernelHealthPanel } from './components/KernelHealthPanel/KernelHealthPanel';
import { ServiceStatusGrid } from './components/ServiceStatusGrid/ServiceStatusGrid';
import { TelemetryPanel } from './components/TelemetryPanel/TelemetryPanel';
import { WorkflowGraph } from './components/WorkflowGraph/WorkflowGraph';
import { WorkflowPanel } from './components/WorkflowPanel/WorkflowPanel';

// 1. TypeScript interface for Props
export interface MissionCenterPageProps {
  isLoading?: boolean;
  hasError?: boolean;
}

// 2. Export component
export const MissionCenterPage: React.FC<MissionCenterPageProps> = ({
  isLoading = false,
  hasError = false,
}) => {
  const { missions, activeMissionId, isOffline, loadMissions, confirmMissionAction } = useMissionStore();
  const loadKernel = useKernelStore((s) => s.loadKernel);
  const loadTelemetry = useTelemetryStore((s) => s.loadTelemetry);
  const loadHealth = useHealthStore((s) => s.loadHealth);
  const telemetry = useTelemetryStore();
  const { workflows, activeWorkflowId, loadWorkflows } = useWorkflowStore();

  const [activeTab, setActiveTab] = useState<'details' | 'stats' | 'workflow'>('details');
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [isDiagOpen, setIsDiagOpen] = useState(false);
  const [isDesktopDiagOpen, setIsDesktopDiagOpen] = useState(false);

  // Initialize real-time streams connection & hooks
  const realtime = useRealtime();
  useMissionEvents();
  useTelemetry();
  useKernelEvents();

  // Load/reload state on mount or upon reconnection
  const [prevConnectionState, setPrevConnectionState] = useState<ConnectionState>('DISCONNECTED');

  useEffect(() => {
    if (realtime.connectionState === 'CONNECTED' && prevConnectionState !== 'CONNECTED') {
      loadMissions();
      loadKernel();
      loadTelemetry();
      loadHealth();
      loadWorkflows();
    }
    setPrevConnectionState(realtime.connectionState);
  }, [realtime.connectionState, prevConnectionState, loadMissions, loadKernel, loadTelemetry, loadHealth, loadWorkflows]);

  // Baseline load on mount
  useEffect(() => {
    loadMissions();
    loadKernel();
    loadTelemetry();
    loadHealth();
    loadWorkflows();
  }, [loadMissions, loadKernel, loadTelemetry, loadHealth, loadWorkflows]);

  // Fallback Polling interval triggered ONLY if transport falls back to POLLING
  useEffect(() => {
    if (realtime.transportType === 'POLLING') {
      const interval = setInterval(() => {
        loadMissions();
        loadKernel();
        loadTelemetry();
        loadHealth();
      }, 1000);

      return () => clearInterval(interval);
    }
  }, [realtime.transportType, loadMissions, loadKernel, loadTelemetry, loadHealth]);

  // 3. Accessibility comments
  // main role signifies the primary dashboard view area for accessibility
  // aria-label outlines page scope

  // 4. Loading state
  if (isLoading) {
    return (
      <div 
        className="h-screen bg-zinc-950 flex items-center justify-center text-zinc-400 font-mono text-xs gap-3 animate-pulse"
        aria-busy="true"
        aria-label="Loading Mission Center Page"
      >
        <span className="w-2.5 h-2.5 rounded-full bg-cyan-glow animate-ping" />
        <span>Loading Mission Center Page Layout...</span>
      </div>
    );
  }

  // 5. Error state
  if (hasError) {
    return (
      <div 
        className="h-screen bg-zinc-950 flex flex-col items-center justify-center text-center p-6 gap-3"
        role="alert"
      >
        <span className="text-sm font-extrabold text-red-500 uppercase tracking-widest">
          Mission Center Error
        </span>
        <p className="text-xs text-zinc-500 font-mono">
          Fatal crash loading Mission Center shell boundaries.
        </p>
      </div>
    );
  }

  const activeMission = missions.find((m) => m.id === activeMissionId) || null;
  const activeWorkflow = workflows.find(w => w.id === activeWorkflowId) || null;

  return (
    <motion.main 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="flex h-[calc(100vh-5rem)] overflow-hidden bg-matte-card text-zinc-100 select-none"
      role="main"
      aria-label="FRIDAY Mission Center Dashboard"
    >
      {/* 6. Empty state: Rendered inside subcomponents when no items found */}
      
      {/* Col 1: Mission navigation lists sidebar */}
      <MissionSidebar />

      {/* Col 2: Main Area overview & details */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Toolbar commands */}
        <MissionToolbar 
          missionId={activeMissionId} 
          status={activeMission?.status} 
        />

        {isOffline && (
          <div className="bg-red-950/20 border-y border-red-900/35 px-6 py-2 flex items-center gap-3 text-[10px] font-mono text-red-400 animate-pulse">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
            <span>Connection offline. Reconnecting to central FRIDAY Kernel API server...</span>
          </div>
        )}

        {/* Dynamic workspace wrapper grid */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-thin">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
            {/* Steps timeline & progression status */}
            <div className="lg:col-span-2 space-y-6">
              <MissionTimeline 
                steps={activeMission?.steps} 
                currentStep={activeMission?.currentStep} 
                status={activeMission?.status}
              />
              
              {/* Tabs Panel Selection */}
              <div className="border border-matte-border/20 rounded-xl overflow-hidden bg-matte-card/30">
                <div className="flex bg-black/10 border-b border-matte-border/25">
                  {(['details', 'stats', 'workflow'] as const).map((tab) => (
                    <button
                      key={tab}
                      id={`tab-${tab}`}
                      onClick={() => setActiveTab(tab)}
                      className={`px-5 py-3 text-[10px] font-mono uppercase tracking-widest border-r border-matte-border/20 focus:outline-none transition-colors
                        ${activeTab === tab 
                          ? 'bg-cyan-dim/15 text-cyan-glow font-bold' 
                          : 'text-zinc-500 hover:text-zinc-300'
                        }
                      `}
                      aria-pressed={activeTab === tab}
                    >
                      {tab}
                    </button>
                  ))}
                  
                  {/* View History Trigger */}
                  <button
                    onClick={() => setIsHistoryOpen(true)}
                    className="ml-auto px-5 py-3 text-[10px] font-mono uppercase tracking-widest text-zinc-500 hover:text-cyan-glow focus:outline-none transition-colors border-l border-matte-border/20"
                    aria-label="Open History Log Drawer"
                  >
                    History Log
                  </button>
                </div>

                {/* Render Tabs content */}
                <div>
                  {activeTab === 'details' ? (
                    <MissionDetails mission={activeMission} />
                  ) : activeTab === 'stats' ? (
                    <MissionStatistics missionId={activeMissionId} />
                  ) : (
                    /* Workflow tab */
                    <div className="p-4">
                      <WorkflowGraph workflow={activeWorkflow} className="w-full" />
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Overall progress status circle */}
            <div className="flex justify-center lg:justify-start">
              <MissionProgress 
                progress={activeMission?.progress} 
                status={activeMission?.status} 
                durationMs={activeMission?.durationMs}
              />
            </div>
          </div>

          {/* Console logging events streams */}
          <div className="w-full">
            <MissionLogs missionId={activeMissionId} />
          </div>
        </div>

        {/* Execution telemetry summary footer */}
        <TelemetryPanel />
      </div>

      {/* Col 3: Side control panel checks (Kernel & heartbeats grid) */}
      <div 
        className="w-[280px] border-l border-matte-border/30 bg-black/10 p-4.5 space-y-4.5 overflow-y-auto scrollbar-none flex flex-col justify-between"
        role="complementary"
        aria-label="Kernel diagnostic sidebar"
      >
        <div className="space-y-4.5">
          <KernelHealthPanel />
          <ServiceStatusGrid />
        </div>

        {/* Collapsible Workflow Engine Widget */}
        <WorkflowPanel />

        {/* Collapsible Stream Diagnostics Widget */}
        <div className="space-y-3">
          {/* Collapsible Stream Diagnostics Widget */}
          <div className="border border-matte-border/20 rounded-xl bg-matte-card/30 overflow-hidden">
            <button
              onClick={() => setIsDiagOpen(!isDiagOpen)}
              className="w-full flex justify-between items-center px-4 py-2.5 bg-black/10 hover:bg-black/20 focus:outline-none transition-colors text-[9px] font-mono uppercase tracking-widest text-zinc-500 font-bold"
            >
              <span>Stream Diagnostics</span>
              <span className="text-[8px]">{isDiagOpen ? '▼' : '▲'}</span>
            </button>
            {isDiagOpen && (
              <div className="p-3.5 space-y-2 text-[9px] font-mono uppercase tracking-wider text-zinc-400 border-t border-matte-border/10 bg-zinc-950/20">
                <div className="flex justify-between items-center">
                  <span>State:</span>
                  <span className={`font-bold ${realtime.connectionState === 'CONNECTED' ? 'text-emerald-400' : realtime.connectionState === 'CONNECTING' ? 'text-orange-400 animate-pulse' : 'text-red-400'}`}>
                    {realtime.connectionState}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span>Transport:</span>
                  <span className="text-cyan-glow font-bold">{realtime.transportType}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span>Attempts:</span>
                  <span className="text-zinc-300">{realtime.reconnectAttempts}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span>Last Event:</span>
                  <span className="text-zinc-500 text-[8px] lowercase tracking-normal">
                    {realtime.lastEventTimestamp ? new Date(realtime.lastEventTimestamp).toLocaleTimeString() : 'none'}
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Collapsible Desktop Diagnostics Widget */}
          <div className="border border-matte-border/20 rounded-xl bg-matte-card/30 overflow-hidden">
            <button
              onClick={() => setIsDesktopDiagOpen(!isDesktopDiagOpen)}
              className="w-full flex justify-between items-center px-4 py-2.5 bg-black/10 hover:bg-black/20 focus:outline-none transition-colors text-[9px] font-mono uppercase tracking-widest text-zinc-500 font-bold"
            >
              <span>Desktop Diagnostics</span>
              <span className="text-[8px]">{isDesktopDiagOpen ? '▼' : '▲'}</span>
            </button>
            {isDesktopDiagOpen && (
              <div className="p-3.5 space-y-2 text-[9px] font-mono uppercase tracking-wider text-zinc-400 border-t border-matte-border/10 bg-zinc-950/20">
                <div className="flex justify-between items-center">
                  <span>Active Task:</span>
                  <span className="text-zinc-300 truncate max-w-[120px] font-bold" title={telemetry.current_desktop_task}>
                    {telemetry.current_desktop_task || 'None'}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span>Last Action:</span>
                  <span className="text-purple-400 font-bold">{telemetry.last_executed_action || 'None'}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span>Queue Len:</span>
                  <span className="text-zinc-300">{telemetry.queue_length || 0}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span>Avg Exec:</span>
                  <span className="text-cyan-glow font-bold">
                    {telemetry.average_execution_time_ms ? `${telemetry.average_execution_time_ms}ms` : '0ms'}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span>Fail Count:</span>
                  <span className={`font-bold ${telemetry.failure_count && telemetry.failure_count > 0 ? 'text-red-400 animate-pulse' : 'text-zinc-500'}`}>
                    {telemetry.failure_count || 0}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Drawer Dialog: Mission history archives logs */}
      <MissionHistory 
        isOpen={isHistoryOpen} 
        onClose={() => setIsHistoryOpen(false)} 
      />

      {/* Sensitive Action Approval Dialog */}
      {activeMission?.metadata?.pending_confirmation && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <motion.div 
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="bg-zinc-900 border border-amber-500/30 rounded-xl p-6 max-w-md w-full space-y-4 shadow-[0_0_50px_rgba(245,158,11,0.15)] text-left"
          >
            <div className="flex items-center gap-3">
              <span className="w-2 h-2 rounded-full bg-amber-500 animate-ping" />
              <h3 className="text-xs font-mono uppercase tracking-widest text-amber-500 font-bold">
                Sensitive Action Confirmation
              </h3>
            </div>
            
            <p className="text-xs text-zinc-300 font-mono leading-relaxed bg-zinc-950/40 p-3.5 rounded-lg border border-matte-border/10">
              {activeMission.metadata.pending_confirmation.prompt}
            </p>

            {activeMission.metadata.pending_confirmation.args && (
              <pre className="p-3 bg-black/35 rounded-lg text-[9px] text-zinc-400 overflow-x-auto font-mono max-h-24 scrollbar-thin leading-normal">
                {JSON.stringify(activeMission.metadata.pending_confirmation.args, null, 2)}
              </pre>
            )}

            <div className="flex gap-3 justify-end text-[10px] font-mono uppercase tracking-wider pt-2">
              <button
                onClick={() => confirmMissionAction(activeMission.id, false)}
                className="px-4 py-2 rounded-lg bg-zinc-950 border border-red-500/20 text-red-400 hover:bg-red-500/10 hover:border-red-500/50 transition-colors cursor-pointer"
              >
                Deny
              </button>
              <button
                onClick={() => confirmMissionAction(activeMission.id, true)}
                className="px-4 py-2 rounded-lg bg-amber-500 text-zinc-950 font-bold hover:bg-amber-400 hover:shadow-[0_0_15px_rgba(245,158,11,0.3)] transition-all cursor-pointer"
              >
                Approve
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </motion.main>
  );
};
