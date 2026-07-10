import React, { lazy, Suspense, useEffect, useRef } from 'react';
import { Network, Search, Loader2 } from 'lucide-react';
import { GlassPanel } from './GlassPanel';
import { useKnowledgeStore } from '../../../knowledge/store/useKnowledgeStore';
import { useAiStateStore } from '../../sync/useAiStateStore';

const GraphCanvas = lazy(() => import('../../../knowledge/components/GraphCanvas'));

const GraphLoader: React.FC = () => (
  <div className="h-full w-full flex items-center justify-center text-cyan-glow/60">
    <Loader2 className="w-5 h-5 animate-spin" />
  </div>
);

/**
 * Embeds the real ATLAS knowledge graph (existing engine + store) into the
 * Command Center. Triggers the live fetch, exposes the existing search for
 * node highlighting, and layers a holographic tint on top. No graph logic is
 * duplicated or faked here.
 */
export const AtlasGraphPanel: React.FC<{ className?: string }> = ({ className }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const nodes = useKnowledgeStore((s) => s.nodes);
  const searchQuery = useKnowledgeStore((s) => s.searchQuery);
  const setSearchQuery = useKnowledgeStore((s) => s.setSearchQuery);
  const aiState = useAiStateStore((s) => s.state);

  // The graph "comes alive" while FRIDAY is reasoning / retrieving / expanding.
  useEffect(() => {
    const ks = useKnowledgeStore.getState();
    const active = aiState === 'thinking' || aiState === 'memory' || aiState === 'knowledge';
    ks.setParticleDensity(active ? 2.4 : 1.0);
    ks.setGlowStrength(active ? 1.6 : 1.0);
  }, [aiState]);

  useEffect(() => {
    // Load the real graph from the ATLAS engine (no-op / empty if backend absent).
    useKnowledgeStore.getState().setActiveProvider('knowledge').catch(() => undefined);
  }, []);

  return (
    <GlassPanel
      title="Knowledge Graph · ATLAS"
      icon={<Network className="w-3.5 h-3.5" />}
      className={className}
      bodyClassName="relative h-[calc(100%-2.75rem)] overflow-hidden"
      action={
        <span className="text-[8px] font-mono text-zinc-500">{nodes.length} nodes</span>
      }
    >
      <div className="absolute top-2 left-2 right-2 z-20">
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg border border-cyan-border/25 bg-black/50 backdrop-blur-sm">
          <Search className="w-3 h-3 text-cyan-glow/70" />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search nodes…"
            className="flex-1 bg-transparent outline-none text-[10px] font-mono text-zinc-200 placeholder:text-zinc-600"
          />
        </div>
      </div>

      <div ref={containerRef} className="absolute inset-0">
        <Suspense fallback={<GraphLoader />}>
          <GraphCanvas showControls={false} />
        </Suspense>
      </div>

      {/* Holographic tint — purely decorative, does not touch graph logic */}
      <div className="pointer-events-none absolute inset-0 z-10 cc-holo-tint" />

      {nodes.length === 0 && (
        <div className="absolute inset-0 z-30 flex flex-col items-center justify-center gap-1 text-center px-6">
          <Network className="w-6 h-6 text-cyan-glow/40" />
          <span className="text-[10px] font-mono text-zinc-500">No graph data</span>
          <span className="text-[8px] font-mono text-zinc-600">Run an ATLAS index to populate</span>
        </div>
      )}
    </GlassPanel>
  );
};
