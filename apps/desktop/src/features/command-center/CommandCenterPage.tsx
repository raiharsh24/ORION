import React, { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { Cpu, Wifi, Mic, Volume2, Battery } from 'lucide-react';
import { SystemOverviewPanel } from './components/panels/SystemOverviewPanel';
import { AICoreStatusPanel } from './components/panels/AICoreStatusPanel';
import { ActiveAgentsPanel } from './components/panels/ActiveAgentsPanel';
import { SystemMonitoringPanel } from './components/panels/SystemMonitoringPanel';
import { AtlasGraphPanel } from './components/panels/AtlasGraphPanel';
import { MemoryStreamPanel } from './components/panels/MemoryStreamPanel';
import { CoreSurroundWidgets } from './components/three/CoreSurroundWidgets';
import { ExecutionPipelineOverlay } from './components/three/ExecutionPipelineOverlay';
import { ExecutionReactorOverlay } from './components/three/ExecutionReactorOverlay';
import { NeuralNetworkPaths } from './components/widgets/NeuralNetworkPaths';
import { NavRail } from './components/layout/NavRail';
import { useCommandCenterStore } from './store/useCommandCenterStore';
import { useAiStateStore, startAiDemo } from './sync/useAiStateStore';
import { useExecutionState } from '../../services/realtime/hooks/useExecutionState';
import { eventBus } from './sync/eventBus';
import type { WorkspaceId } from './store/useCommandCenterStore';

// Interactive Bottom Dock Panel Components
import { VoiceInputPanel } from './components/panels/VoiceInputPanel';
import { CurrentTaskPanel } from './components/panels/CurrentTaskPanel';
import { SystemCommandsPanel } from './components/panels/SystemCommandsPanel';
import { EnergyCorePanel } from './components/panels/EnergyCorePanel';

// Heavy 3D core is code-split so the initial route payload stays light.
const AICore3D = lazy(() => import('./components/three/AICore3D'));

const CoreFallback: React.FC = () => (
  <div className="w-[520px] h-[520px] max-w-[60vh] max-h-[60vh] rounded-full border border-cyan-border/30 flex items-center justify-center cc-spin-slow">
    <div className="w-[80%] h-[80%] rounded-full border border-cyan-border/20 cc-spin-rev flex items-center justify-center">
      <div className="w-[55%] h-[55%] rounded-full border border-cyan-border/40 cc-spin-med flex items-center justify-center">
        <Cpu className="w-14 h-14 text-cyan-glow cc-text-glow" />
      </div>
    </div>
  </div>
);

export const CommandCenterPage: React.FC = () => {
  const activeWorkspace = useCommandCenterStore((s) => s.activeWorkspace);
  const setActiveWorkspace = useCommandCenterStore((s) => s.setActiveWorkspace);
  const aiState = useAiStateStore((s) => s.state);
  const tick = useCommandCenterStore((s) => s.tick);
  const stageRef = useRef<HTMLDivElement>(null);

  // Time & Date Clock States
  const [timeStr, setTimeStr] = useState('');
  const [dateStr, setDateStr] = useState('');
  const [uptimeStr, setUptimeStr] = useState('6H 24M');

  // Real-time ticking clock & uptime builder
  useEffect(() => {
    const start = Date.now() - 6.4 * 60 * 60 * 1000;
    const updateTime = () => {
      const now = new Date();
      setTimeStr(now.toLocaleTimeString('en-US', { hour12: true }));
      setDateStr(now.toLocaleDateString('en-US', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' }).toUpperCase());
      
      const diffMs = Date.now() - start;
      const hours = Math.floor(diffMs / (3600 * 1000));
      const mins = Math.floor((diffMs % (3600 * 1000)) / (60 * 1000));
      setUptimeStr(`${hours}H ${mins}M`);
    };

    updateTime();
    const id = setInterval(updateTime, 1000);
    return () => clearInterval(id);
  }, []);

  // Start the ambient synchronization demo (gentle state cycling so the whole
  // interface is visibly alive even without a live backend).
  useEffect(() => startAiDemo(), []);

  // Live-data simulation loop (~1s cadence).
  useEffect(() => {
    const id = setInterval(() => tick(), 1000);
    return () => clearInterval(id);
  }, [tick]);

  // Subtle camera parallax driven by pointer position.
  useEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    let raf = 0;
    const onMove = (e: MouseEvent) => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const x = (e.clientX / window.innerWidth - 0.5) * 2;
        const y = (e.clientY / window.innerHeight - 0.5) * 2;
        el.style.setProperty('--px', x.toFixed(3));
        el.style.setProperty('--py', y.toFixed(3));
      });
    };
    window.addEventListener('mousemove', onMove);
    return () => {
      window.removeEventListener('mousemove', onMove);
      cancelAnimationFrame(raf);
    };
  }, []);

  // ── LIVE MEMORY INJECTION ENGINE ──
  const execState = useExecutionState();
  const prevTool = useRef('');
  const prevTask = useRef('');
  const prevStage = useRef('');
  const prevConfidence = useRef(0);

  const pushMemoryEvent = (label: string, detail: string, kind: 'store' | 'recall' | 'link' | 'index') => {
    const store = useCommandCenterStore.getState();
    const fresh = {
      id: `live-${Date.now()}-${Math.random()}`,
      label,
      detail,
      time: 'now',
      kind,
    };
    const aged = store.memoryStream.map((m, i) => ({ ...m, time: i === 0 ? '6s' : m.time }));
    const nextStream = [fresh, ...aged].slice(0, 6);
    useCommandCenterStore.setState({ memoryStream: nextStream });
    eventBus.emit('MEMORY_UPDATED', { count: nextStream.length });
  };

  // Watch selected tool execution
  useEffect(() => {
    if (execState.selected_tool && execState.selected_tool !== prevTool.current) {
      prevTool.current = execState.selected_tool;
      pushMemoryEvent('Tool Invoked', `Activated ${execState.selected_tool} capability`, 'link');
    }
  }, [execState.selected_tool]);

  // Watch active subtask execution
  useEffect(() => {
    if (execState.active_task && execState.active_task !== prevTask.current) {
      prevTask.current = execState.active_task;
      pushMemoryEvent('Task Processing', `Active subtask: ${execState.active_task.slice(0, 32)}`, 'recall');
    }
  }, [execState.active_task]);

  // Watch kernel stage transition
  useEffect(() => {
    if (execState.execution_stage && execState.execution_stage !== prevStage.current) {
      prevStage.current = execState.execution_stage;
      pushMemoryEvent('Kernel Transition', `OS shifted to stage: ${execState.execution_stage.toUpperCase()}`, 'index');
    }
  }, [execState.execution_stage]);

  // Watch reflections/confidence
  useEffect(() => {
    if (execState.confidence > 0 && Math.abs(execState.confidence - prevConfidence.current) > 5) {
      prevConfidence.current = execState.confidence;
      pushMemoryEvent('Reflection Logged', `Likelihood of goal success: ${execState.confidence}%`, 'store');
    }
  }, [execState.confidence]);

  return (
    <div 
      className="cc-root fixed inset-0 h-screen w-screen overflow-hidden text-zinc-100 font-sans select-none flex flex-col" 
      data-ai-state={aiState}
    >
      {/* Atmospheric background layers */}
      <div className="pointer-events-none absolute inset-0 grid-backdrop opacity-30" />
      <div className="pointer-events-none absolute inset-0 noise-overlay" />
      
      {/* Dynamic neural trace paths */}
      <NeuralNetworkPaths />

      {/* ── TOP HEADER (J.A.R.V.I.S. Protocol HUD header) ── */}
      <header className="h-14 border-b border-cyan-border/15 bg-black/35 backdrop-blur-md flex items-center justify-between px-6 shrink-0 relative z-20">
        <div className="flex items-center gap-1.5">
          <Cpu className="w-4.5 h-4.5 text-cyan-glow cc-text-glow animate-pulse" />
          <span className="text-[10px] font-mono tracking-[0.25em] text-zinc-400">
            FRIDAY <span className="text-cyan-glow">AI OPERATING SYSTEM</span>
          </span>
        </div>

        <div className="text-center">
          <div className="text-xs font-extrabold tracking-[0.28em] text-cyan-glow cc-text-glow">J.A.R.V.I.S. PROTOCOL ACTIVE</div>
          <div className="text-[8px] font-mono uppercase tracking-[0.2em] text-zinc-500 mt-0.5">AI Core Online</div>
        </div>

        {/* HUD stats: clock, uptime, battery status */}
        <div className="flex items-center gap-4 text-zinc-400">
          <div className="text-right font-mono text-[9px] tracking-wider leading-tight border-r border-cyan-border/20 pr-4">
            <div className="text-zinc-200 font-bold">{timeStr}</div>
            <div className="text-zinc-500 text-[8px] mt-0.5">{dateStr}</div>
          </div>
          
          <div className="flex items-center gap-2">
            <Mic className="w-3.5 h-3.5 text-cyan-glow cc-blink" />
            <Wifi className="w-3.5 h-3.5 text-cyan-glow" />
            <Volume2 className="w-3.5 h-3.5 text-zinc-500" />
            <Battery className="w-4 h-4 text-emerald-400" />
          </div>

          <div className="font-mono text-[8px] tracking-wider pl-1">
            <span className="text-zinc-500">UPTIME</span>
            <div className="text-zinc-300 font-bold">{uptimeStr}</div>
          </div>
        </div>
      </header>

      {/* Main dashboard space */}
      <div className="flex-1 flex min-h-0 relative">
        <NavRail active={activeWorkspace} onSelect={(id) => setActiveWorkspace(id as WorkspaceId)} />

        <div ref={stageRef} className="flex-1 flex flex-col min-w-0">
          {/* Layout grid */}
          <div className="flex-1 grid grid-cols-[352px_minmax(0,1fr)_352px] gap-4 p-4 min-h-0">
            
            {/* ── LEFT COLUMN ── */}
            <div className="flex flex-col gap-4 min-h-0">
              <SystemOverviewPanel className="flex-1 min-h-0" />
              <AICoreStatusPanel className="shrink-0" />
              <ActiveAgentsPanel className="flex-1 min-h-0" />
            </div>

            {/* ── CENTER: MISSION CONTROL AI REACTOR ── */}
            <div className="relative flex flex-col items-center min-h-0 bg-gradient-radial from-cyan-glow/5 to-transparent">
              <div className="w-full relative z-25">
                <MissionControlStub />
              </div>
              <div className="relative flex-1 w-full min-h-0">
                <Suspense fallback={<CoreFallback />}>
                  <AICore3D />
                </Suspense>
                
                {/* Orbiting widgets (Thoughts, Tasks, Memories, Tools) */}
                <CoreSurroundWidgets />
                
                {/* 8-Stage circular execution timeline overlay */}
                <ExecutionPipelineOverlay />
                
                {/* Cinematic Mechanical HUD SVG Overlay */}
                <ExecutionReactorOverlay />
              </div>

              {/* Glowing Soundwave below the Core */}
              <div className="absolute bottom-16 flex flex-col items-center gap-1.5 w-[50%] z-20">
                <span className="text-[7.5px] font-mono uppercase tracking-[0.25em] text-zinc-500">
                  {aiState === 'listening' ? 'Listening for input...' : 'Awaiting prompt injection'}
                </span>
                <svg viewBox="0 0 100 12" className="w-full h-4 opacity-75">
                  <path
                    d={`M 0,6 Q 25,${aiState === 'listening' ? -2 : 4} 50,6 T 100,6`}
                    fill="none"
                    stroke="#00f2fe"
                    strokeWidth="1.2"
                    className={aiState === 'listening' ? 'animate-pulse' : ''}
                    style={{ filter: 'drop-shadow(0 0 4px rgba(0, 242, 254, 0.75))' }}
                  />
                </svg>
              </div>

              <div className="absolute bottom-2 text-[9px] font-mono uppercase tracking-[0.2em] text-cyan-glow/45 bg-black/35 px-2.5 py-1 rounded-full border border-cyan-border/10 z-20">
                {activeWorkspace} workspace · click the core to preview states
              </div>
            </div>

            {/* ── RIGHT COLUMN ── */}
            <div className="flex flex-col gap-4 min-h-0">
              <SystemMonitoringPanel className="flex-1 min-h-0" />
              <AtlasGraphPanel className="flex-[1.4] min-h-0" />
              <MemoryStreamPanel className="flex-1 min-h-0" />
            </div>
          </div>

          {/* ── BOTTOM DOCK (Fully Functional Panels) ── */}
          <div className="h-[200px] shrink-0 grid grid-cols-4 gap-4 px-4 pb-4 relative z-10">
            <VoiceInputPanel />
            <CurrentTaskPanel />
            <SystemCommandsPanel />
            <EnergyCorePanel />
          </div>
        </div>
      </div>
    </div>
  );
};

const MissionControlStub: React.FC = () => {
  const { missionTitle, objective } = useCommandCenterStore();
  const execState = useExecutionState();
  const aiState = useAiStateStore((s) => s.state);

  // Live metrics bindings
  const displayGoal = execState.goal || missionTitle;
  const displayTask = execState.active_task || objective;
  const displayTool = execState.selected_tool || 'None (AI Core)';
  const displayConfidence = execState.confidence || 98.7;
  const displayStage = execState.execution_stage || aiState;

  return (
    <div className="text-center space-y-1.5 pt-2 select-none w-full max-w-lg mx-auto">
      <span className="text-[9px] font-mono tracking-[0.3em] text-cyan-glow/85 cc-text-glow font-bold uppercase">
        MISSION CONTROL
      </span>
      <h2 className="text-sm font-black tracking-tight text-zinc-100 px-6 truncate leading-tight mt-0.5">
        {displayGoal}
      </h2>
      
      {/* 3-Column live telemetry board */}
      <div className="grid grid-cols-3 gap-2 px-6 mt-2 border-y border-cyan-border/10 py-2 text-[8px] font-mono text-zinc-400 bg-black/15">
        <div className="text-left">
          <span className="text-zinc-600 block text-[6.5px] uppercase tracking-wider">Planner Stage</span>
          <span className="text-cyan-glow font-bold uppercase tracking-wider leading-none block mt-1">{displayStage}</span>
        </div>
        <div className="text-center">
          <span className="text-zinc-600 block text-[6.5px] uppercase tracking-wider">Selected Tool</span>
          <span className="text-zinc-200 font-bold truncate block leading-none mt-1">{displayTool}</span>
        </div>
        <div className="text-right">
          <span className="text-zinc-600 block text-[6.5px] uppercase tracking-wider">Confidence</span>
          <span className="text-emerald-400 font-bold block leading-none mt-1">{displayConfidence.toFixed(1)}%</span>
        </div>
      </div>

      <div className="text-[7.5px] font-mono uppercase tracking-[0.2em] text-zinc-500 mt-1 max-w-xs mx-auto truncate">
        Task: {displayTask}
      </div>
    </div>
  );
};
