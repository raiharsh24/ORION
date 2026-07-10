import React, { useEffect, useRef, useState } from 'react';
import { GlassPanel } from './components/panels/GlassPanel';
import { NavRail } from './components/layout/NavRail';
import { useCommandCenterStore } from './store/useCommandCenterStore';
import {
  Activity, Gauge, Users, MonitorDot, Network, Waves, Cpu,
} from 'lucide-react';

/**
 * FRIDAY Command Center — the immersive full-screen machine interface.
 *
 * Milestone 1 establishes the 5-region composition, the navigation rail, the
 * reusable glass-panel system, mouse-parallax and the live-data simulation loop.
 * Region bodies marked "M2–M5" are wired with real widgets in later milestones.
 */
export const CommandCenterPage: React.FC = () => {
  const [nav, setNav] = useState('command');
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
        <NavRail active={nav} onSelect={setNav} />

        <div ref={stageRef} className="flex-1 flex flex-col min-w-0">
          {/* Main 3-column region */}
          <div className="flex-1 grid grid-cols-[minmax(300px,340px)_1fr_minmax(300px,340px)] gap-4 p-4 min-h-0">
            {/* ── LEFT COLUMN ── */}
            <div className="flex flex-col gap-4 min-h-0">
              <GlassPanel title="System Overview" icon={<Activity className="w-3.5 h-3.5" />} live className="flex-1 min-h-0">
                <RegionStub label="CPU · Memory · GPU · Network sparklines" tag="M2" />
              </GlassPanel>
              <GlassPanel title="AI Core Status" icon={<Gauge className="w-3.5 h-3.5" />} className="flex-1 min-h-0">
                <RegionStub label="Circular HUD + model / context / speed / confidence" tag="M2" />
              </GlassPanel>
              <GlassPanel title="Active Agents" icon={<Users className="w-3.5 h-3.5" />} className="flex-1 min-h-0">
                <RegionStub label="Orion · Atlas · Nova · Echo" tag="M2" />
              </GlassPanel>
            </div>

            {/* ── CENTER: AI CORE ── */}
            <div
              className="relative flex flex-col items-center min-h-0"
              style={{ transform: 'translate3d(calc(var(--px,0)*-10px), calc(var(--py,0)*-8px), 0)' }}
            >
              <div className="w-full">
                <MissionControlStub />
              </div>
              <div className="flex-1 w-full flex items-center justify-center">
                <div className="relative flex items-center justify-center">
                  <div className="w-[520px] h-[520px] max-w-[60vh] max-h-[60vh] rounded-full border border-cyan-border/30 flex items-center justify-center cc-spin-slow">
                    <div className="w-[80%] h-[80%] rounded-full border border-cyan-border/20 cc-spin-rev flex items-center justify-center">
                      <div className="w-[55%] h-[55%] rounded-full border border-cyan-border/40 cc-spin-med flex items-center justify-center">
                        <div className="w-28 h-28 rounded-full bg-cyan-glow/20 blur-xl absolute" />
                        <Cpu className="w-14 h-14 text-cyan-glow relative z-10 cc-text-glow" />
                      </div>
                    </div>
                  </div>
                  <div className="absolute -bottom-6 w-[420px] h-16 cc-floor-emitter" />
                </div>
              </div>
              <div className="absolute bottom-2 text-[10px] font-mono uppercase tracking-[0.2em] text-cyan-glow/50">
                Real 3D core lands in M3
              </div>
            </div>

            {/* ── RIGHT COLUMN ── */}
            <div className="flex flex-col gap-4 min-h-0">
              <GlassPanel title="System Monitoring" icon={<MonitorDot className="w-3.5 h-3.5" />} live className="flex-1 min-h-0">
                <RegionStub label="CPU · Memory · GPU radial gauges" tag="M4" />
              </GlassPanel>
              <GlassPanel title="Knowledge Graph — ATLAS" icon={<Network className="w-3.5 h-3.5" />} className="flex-1 min-h-0">
                <RegionStub label="Embedded interactive ATLAS graph" tag="M4" />
              </GlassPanel>
              <GlassPanel title="Memory Stream" icon={<Waves className="w-3.5 h-3.5" />} live liveColor="green" className="flex-1 min-h-0">
                <RegionStub label="Recent memory events timeline" tag="M4" />
              </GlassPanel>
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
