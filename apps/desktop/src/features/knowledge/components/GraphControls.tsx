import React, { useState } from 'react';
import { useKnowledgeStore } from '../store/useKnowledgeStore';
import type { LayoutMode } from '../types';
import { Network, Circle, Disc, Grid, Sliders, Settings2 } from 'lucide-react';

interface GraphControlsProps {
  onZoomIn?: () => void;
  onZoomOut?: () => void;
  onReset?: () => void;
}

export const GraphControls: React.FC<GraphControlsProps> = ({
  onZoomIn,
  onZoomOut,
  onReset
}) => {
  const {
    layoutMode,
    setLayoutMode,
    nodeSize,
    setNodeSize,
    linkStrength,
    setLinkStrength,
    physicsEnabled,
    setPhysicsEnabled,
    rotationSpeed,
    setRotationSpeed,
    labelVisibility,
    setLabelVisibility,
    particleDensity,
    setParticleDensity,
    glowStrength,
    setGlowStrength
  } = useKnowledgeStore();

  const [panelOpen, setPanelOpen] = useState(false);

  const layoutButtons: { mode: LayoutMode; label: string; icon: React.ComponentType<any> }[] = [
    { mode: 'force', label: 'Force', icon: Network },
    { mode: 'circle', label: 'Circle', icon: Circle },
    { mode: 'rings', label: 'Rings', icon: Disc },
    { mode: 'hex', label: 'Hex', icon: Grid },
    { mode: 'timeline', label: 'Timeline', icon: Sliders },
    { mode: 'architecture', label: 'Architecture', icon: Settings2 }
  ];

  return (
    <div className="flex items-center gap-3 relative select-none">
      {/* Zoom / Recenter controls */}
      <div className="flex items-center gap-1.5 bg-black/40 border border-matte-border/30 backdrop-blur-md px-3 py-1.5 rounded-xl font-mono text-[9px]">
        <button
          onClick={onZoomIn}
          className="px-2 py-1 rounded bg-zinc-900/60 hover:bg-zinc-800 border border-matte-border/40 text-zinc-400 hover:text-zinc-200 cursor-pointer"
        >
          Zoom +
        </button>
        <button
          onClick={onZoomOut}
          className="px-2 py-1 rounded bg-zinc-900/60 hover:bg-zinc-800 border border-matte-border/40 text-zinc-400 hover:text-zinc-200 cursor-pointer"
        >
          Zoom -
        </button>
        <button
          onClick={onReset}
          className="px-2 py-1 rounded bg-zinc-900/60 hover:bg-zinc-800 border border-matte-border/40 text-zinc-400 hover:text-zinc-200 cursor-pointer"
        >
          Center
        </button>
      </div>

      {/* Primary Layout Mode Controls */}
      <div className="flex items-center gap-1 bg-black/40 border border-matte-border/30 backdrop-blur-md p-1 rounded-xl">
        {layoutButtons.map((btn) => {
          const Icon = btn.icon;
          const isActive = layoutMode === btn.mode;
          return (
            <button
              key={btn.mode}
              onClick={() => setLayoutMode(btn.mode)}
              title={`${btn.label} Layout`}
              className={`p-2 rounded-lg border text-xs flex items-center gap-1 font-mono uppercase transition-all duration-150 cursor-pointer
                ${isActive
                  ? 'bg-cyan-dim/15 border-cyan-glow/50 text-cyan-glow font-bold'
                  : 'bg-transparent border-transparent text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/35'
                }
              `}
            >
              <Icon className="w-3.5 h-3.5" />
              <span className="text-[9px] tracking-wider hidden lg:inline">{btn.label}</span>
            </button>
          );
        })}
      </div>

      {/* Collapsible render parameters toggle */}
      <button
        onClick={() => setPanelOpen(!panelOpen)}
        className={`p-2.5 rounded-xl border backdrop-blur-md font-mono text-xs cursor-pointer transition-all duration-150 flex items-center gap-2
          ${panelOpen
            ? 'bg-cyan-dim/15 border-cyan-glow/50 text-cyan-glow'
            : 'bg-black/40 border-matte-border/30 text-zinc-400 hover:text-zinc-200 hover:border-cyan-border/20'
          }
        `}
      >
        <Settings2 className="w-4 h-4" />
        <span className="text-[9px] tracking-wider uppercase font-bold">Parameters</span>
      </button>

      {/* Floating Parameters Menu Box */}
      {panelOpen && (
        <div className="absolute right-0 top-full mt-3 bg-black/95 border border-matte-border/55 backdrop-blur-md p-5 rounded-2xl w-72 space-y-4 shadow-2xl z-40 animate-in fade-in zoom-in-95 duration-150">
          <h3 className="font-mono text-[10px] font-bold text-zinc-300 uppercase tracking-widest border-b border-matte-border/20 pb-2">
            Rendering Parameters
          </h3>

          <div className="space-y-3 font-mono text-[9px]">
            {/* Slide: Node size */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-zinc-500">
                <span>Node Scale</span>
                <span className="text-zinc-300 font-bold">{nodeSize.toFixed(1)}x</span>
              </div>
              <input
                type="range"
                min="0.5"
                max="3.0"
                step="0.1"
                value={nodeSize}
                onChange={(e) => setNodeSize(parseFloat(e.target.value))}
                className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-cyan-glow"
              />
            </div>

            {/* Slide: Link distance */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-zinc-500">
                <span>Link Tension</span>
                <span className="text-zinc-300 font-bold">{linkStrength.toFixed(1)}x</span>
              </div>
              <input
                type="range"
                min="0.1"
                max="2.0"
                step="0.1"
                value={linkStrength}
                onChange={(e) => setLinkStrength(parseFloat(e.target.value))}
                className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-cyan-glow"
              />
            </div>

            {/* Slide: Rotation */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-zinc-500">
                <span>Orbit Speed</span>
                <span className="text-zinc-300 font-bold">{rotationSpeed.toFixed(1)}x</span>
              </div>
              <input
                type="range"
                min="0.0"
                max="2.0"
                step="0.1"
                value={rotationSpeed}
                onChange={(e) => setRotationSpeed(parseFloat(e.target.value))}
                className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-cyan-glow"
              />
            </div>

            {/* Slide: Particle density */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-zinc-500">
                <span>Link Particles</span>
                <span className="text-zinc-300 font-bold">{particleDensity.toFixed(1)}x</span>
              </div>
              <input
                type="range"
                min="0.0"
                max="3.0"
                step="0.1"
                value={particleDensity}
                onChange={(e) => setParticleDensity(parseFloat(e.target.value))}
                className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-cyan-glow"
              />
            </div>

            {/* Slide: Glow shadow */}
            <div className="space-y-1.5">
              <div className="flex justify-between text-zinc-500">
                <span>Bloom Intensity</span>
                <span className="text-zinc-300 font-bold">{glowStrength.toFixed(1)}x</span>
              </div>
              <input
                type="range"
                min="0.0"
                max="3.0"
                step="0.1"
                value={glowStrength}
                onChange={(e) => setGlowStrength(parseFloat(e.target.value))}
                className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-cyan-glow"
              />
            </div>

            {/* Physics Engine Toggle */}
            <div className="flex justify-between items-center py-1.5 border-t border-matte-border/20">
              <span className="text-zinc-500 uppercase tracking-widest">D3 Physics Engine</span>
              <button
                onClick={() => setPhysicsEnabled(!physicsEnabled)}
                className={`px-3 py-1 rounded font-bold transition-all border cursor-pointer
                  ${physicsEnabled
                    ? 'bg-cyan-dim/15 border-cyan-glow/30 text-cyan-glow'
                    : 'bg-zinc-950 border-zinc-800 text-zinc-500'
                  }
                `}
              >
                {physicsEnabled ? 'ACTIVE' : 'STATIC'}
              </button>
            </div>

            {/* Label visibility Toggle */}
            <div className="flex justify-between items-center">
              <span className="text-zinc-500 uppercase tracking-widest">Node Labels</span>
              <button
                onClick={() => setLabelVisibility(!labelVisibility)}
                className={`px-3 py-1 rounded font-bold transition-all border cursor-pointer
                  ${labelVisibility
                    ? 'bg-cyan-dim/15 border-cyan-glow/30 text-cyan-glow'
                    : 'bg-zinc-950 border-zinc-800 text-zinc-500'
                  }
                `}
              >
                {labelVisibility ? 'SHOWN' : 'HIDDEN'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
export default GraphControls;
