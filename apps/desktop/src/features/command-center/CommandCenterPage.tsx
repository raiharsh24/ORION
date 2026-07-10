import React, { lazy, Suspense, useEffect, useRef } from 'react';
import { Cpu } from 'lucide-react';
import { GlassPanel } from './components/panels/GlassPanel';
import { NavRail } from './components/layout/NavRail';
import { SystemOverviewPanel } from './components/panels/SystemOverviewPanel';
import { AICoreStatusPanel } from './components/panels/AICoreStatusPanel';
import { ActiveAgentsPanel } from './components/panels/ActiveAgentsPanel';
import { SystemMonitoringPanel } from './components/panels/SystemMonitoringPanel';
import { AtlasGraphPanel } from './components/panels/AtlasGraphPanel';
import { MemoryStreamPanel } from './components/panels/MemoryStreamPanel';
import { CoreSurroundWidgets } from './components/three/CoreSurroundWidgets';
import { useCommandCenterStore } from './store/useCommandCenterStore';
import type { WorkspaceId } from './store/useCommandCenterStore';

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

/**
 * FRIDAY Command Center — the immersive full-screen machine interface.
 *
 * The shell (nav rail, side columns, ambient environment, dock) is persistent.
 * Navigation swaps the CENTER workspace only (Command→AI Core, Knowledge→ATLAS,
 * Agents→Agent Control, Memory→Memory Vault, Workflows→Builder, System→Diagnostics,
 * Settings). Center swap + real 3D core arrive in M3; right column M4; dock M5.
 */
export const CommandCenterPage: React.FC = () => {
  const activeWorkspace = useCommandCenterStore((s) => s.activeWorkspace);
  const setActiveWorkspace = useCommandCenterStore((s) => s.setActiveWorkspace);
  const tick = useCommandCenterStore((s) => s.tick);
  const stageRef = useRef<HTMLDivElement>(null);

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

  return (
    <div className="cc-root fixed inset-0 h-screen w-screen overflow-hidden text-zinc-100 font-sans select-none">
      {/* Atmospheric background layers (upgraded to volumetric 3D room in M6) */}
      <div className="pointer-events-none absolute inset-0 grid-backdrop opacity-40" />
      <div className="pointer-events-none absolute inset-0 noise-overlay" />

      <div className="relative z-10 flex h-full">
        <NavRail active={activeWorkspace} onSelect={(id) => setActiveWorkspace(id as WorkspaceId)} />

        <div ref={stageRef} className="flex-1 flex flex-col min-w-0">
          {/* Main region: fixed side columns, dominant flexible center */}
          <div className="flex-1 grid grid-cols-[352px_minmax(0,1fr)_352px] gap-4 p-4 min-h-0">
            {/* ── LEFT COLUMN ── */}
            <div className="flex flex-col gap-4 min-h-0">
              <SystemOverviewPanel className="flex-1 min-h-0" />
              <AICoreStatusPanel className="shrink-0" />
              <ActiveAgentsPanel className="flex-1 min-h-0" />
            </div>

            {/* ── CENTER: AI CORE (living 3D scene + workspace in M3+) ── */}
            <div className="relative flex flex-col items-center min-h-0">
              <div className="w-full">
                <MissionControlStub />
              </div>
              <div className="relative flex-1 w-full min-h-0">
                <Suspense fallback={<CoreFallback />}>
                  <AICore3D />
                </Suspense>
                <CoreSurroundWidgets />
              </div>
              <div className="absolute bottom-2 text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-glow/50">
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

          {/* ── BOTTOM COMMAND DOCK ── */}
          <div className="h-[200px] shrink-0 grid grid-cols-4 gap-4 px-4 pb-4">
            <GlassPanel title="Voice Input">
              <RegionStub label="Waveform · listening · mic" tag="M5" />
            </GlassPanel>
            <GlassPanel title="Current Task">
              <RegionStub label="Research & Analysis · progress · subtasks" tag="M5" />
            </GlassPanel>
            <GlassPanel title="System Commands">
              <RegionStub label="New Task · Scan · Optimize · Report…" tag="M5" />
            </GlassPanel>
            <GlassPanel title="Energy Core">
              <RegionStub label="Reactor · power level" tag="M5" />
            </GlassPanel>
          </div>
        </div>
      </div>
    </div>
  );
};

const RegionStub: React.FC<{ label: string; tag: string }> = ({ label, tag }) => (
  <div className="h-full min-h-[64px] w-full flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-cyan-border/15 text-center">
    <span className="text-[10px] font-mono text-zinc-500 px-3 leading-relaxed">{label}</span>
    <span className="text-[8px] font-mono uppercase tracking-[0.2em] text-cyan-glow/40 border border-cyan-border/20 rounded px-1.5 py-0.5">
      {tag}
    </span>
  </div>
);

const MissionControlStub: React.FC = () => {
  const { missionStatus, missionTitle, objective } = useCommandCenterStore();
  return (
    <div className="text-center space-y-1.5 pt-1">
      <div className="text-[9px] font-mono uppercase tracking-[0.25em] text-cyan-glow/80 cc-text-glow">{missionStatus}</div>
      <div className="text-lg font-bold tracking-tight text-zinc-100">{missionTitle}</div>
      <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-400">{objective}</div>
    </div>
  );
};
