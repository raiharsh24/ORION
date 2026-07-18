import React, { lazy, Suspense, useEffect, useRef } from 'react';
import { Network, Search, Loader2, ArrowRight } from 'lucide-react';
import { GlassPanel } from './GlassPanel';
import { useKnowledgeStore } from '../../../knowledge/store/useKnowledgeStore';
import { useAiStateStore } from '../../sync/useAiStateStore';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';

const GraphCanvas = lazy(() => import('../../../knowledge/components/GraphCanvas'));

const GraphLoader: React.FC = () => (
  <div className="h-full w-full flex items-center justify-center text-cyan-glow/60">
    <Loader2 className="w-5 h-5 animate-spin" />
  </div>
);

export const AtlasGraphPanel: React.FC<{ className?: string }> = ({ className }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const nodes = useKnowledgeStore((s) => s.nodes);
  const searchQuery = useKnowledgeStore((s) => s.searchQuery);
  const setSearchQuery = useKnowledgeStore((s) => s.setSearchQuery);
  const aiState = useAiStateStore((s) => s.state);
  const setActiveWorkspace = useCommandCenterStore((s) => s.setActiveWorkspace);

  // The graph particles and parameters dynamically adapt
  useEffect(() => {
    const ks = useKnowledgeStore.getState();
    const active = aiState === 'thinking' || aiState === 'memory' || aiState === 'knowledge';
    ks.setParticleDensity(active ? 2.4 : 1.0);
    ks.setGlowStrength(active ? 1.6 : 1.0);
  }, [aiState]);

  useEffect(() => {
    useKnowledgeStore.getState().setActiveProvider('knowledge').catch(() => undefined);
  }, []);

  const handleExploreClick = () => {
    setActiveWorkspace('knowledge');
  };

  return (
    <GlassPanel
      title="Knowledge Graph (ATLAS)"
      icon={<Network className="w-3.5 h-3.5" />}
      live
      liveColor="green"
      className={className}
      bodyClassName="relative h-[calc(100%-2.75rem)] overflow-hidden"
    >
      {/* Search overlay bar */}
      <div className="absolute top-2 left-2 right-2 z-20">
        <div className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg border border-cyan-border/25 bg-black/65 backdrop-blur-sm shadow-[0_0_8px_rgba(0,242,254,0.06)]">
          <Search className="w-3 h-3 text-cyan-glow/70" />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search nodes…"
            className="flex-1 bg-transparent outline-none text-[9px] font-mono text-zinc-200 placeholder:text-zinc-600"
          />
        </div>
      </div>

      {/* R3F Canvas region */}
      <div ref={containerRef} className="absolute inset-0">
        <Suspense fallback={<GraphLoader />}>
          <GraphCanvas showControls={false} />
        </Suspense>
      </div>

      {/* Holographic tint overlay */}
      <div className="pointer-events-none absolute inset-0 z-10 cc-holo-tint" />

      {/* Graph Legend Overlay (Right Side) */}
      <div className="absolute right-2 top-14 z-20 flex flex-col gap-1.5 p-2 rounded-lg border border-cyan-border/10 bg-black/75 backdrop-blur-sm text-[7.5px] font-mono text-zinc-400">
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-500 shadow-[0_0_4px_#3b82f6]" />
          <span>CONCEPT</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-glow shadow-[0_0_4px_#00f2fe]" />
          <span>ENTITY</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-purple-400 shadow-[0_0_4px_#c084fc]" />
          <span>RELATION</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-orange-glow shadow-[0_0_4px_#f97316]" />
          <span>YOU</span>
        </div>
      </div>

      {/* Statistics Overlay (Bottom Left) */}
      <div className="absolute left-2.5 bottom-2.5 z-20 flex flex-col font-mono text-[7px] text-zinc-500 leading-none pointer-events-none">
        <div>
          NODES:{' '}
          <span className="text-zinc-300 font-bold">
            {nodes.length ? nodes.length.toLocaleString() : '10,248'}
          </span>{' '}
          <span className="text-emerald-400 font-semibold">(+126)</span>
        </div>
        <div className="mt-1">
          RELATIONS:{' '}
          <span className="text-zinc-300 font-bold">24,531</span>{' '}
          <span className="text-emerald-400 font-semibold">(+256)</span>
        </div>
      </div>

      {/* Explore Graph Trigger Button (Bottom Right) */}
      <button
        onClick={handleExploreClick}
        className="absolute right-2.5 bottom-2.5 z-20 flex items-center gap-1 px-2.5 py-1 rounded-md border border-cyan-border/30 bg-black/65 hover:border-cyan-glow text-[7.5px] font-mono text-zinc-300 hover:text-cyan-glow transition-all duration-300 shadow-[0_0_8px_rgba(0,242,254,0.05)] cursor-pointer"
      >
        EXPLORE GRAPH <ArrowRight className="w-2.5 h-2.5" />
      </button>

      {nodes.length === 0 && (
        <div className="absolute inset-0 z-30 flex flex-col items-center justify-center gap-1 text-center px-6 bg-black/30 backdrop-blur-[1px]">
          <Network className="w-6 h-6 text-cyan-glow/40" />
          <span className="text-[10px] font-mono text-zinc-500">No graph data</span>
          <span className="text-[8px] font-mono text-zinc-600">Run an ATLAS index to populate</span>
        </div>
      )}
    </GlassPanel>
  );
};
