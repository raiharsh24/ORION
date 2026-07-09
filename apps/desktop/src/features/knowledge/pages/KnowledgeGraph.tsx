import React, { useEffect, useRef, useState } from 'react';
import { useKnowledgeStore } from '../store/useKnowledgeStore';
import type { HighlightMode } from '../store/useKnowledgeStore';
import type { ProviderType } from '../types';
import { GraphCanvas } from '../components/GraphCanvas';
import { GraphControls } from '../components/GraphControls';
import { InspectorPanel } from '../components/InspectorPanel';
import { SearchBar } from '../components/SearchBar';
import { Legend } from '../components/Legend';
import { MiniMap } from '../components/MiniMap';
import { 
  Database, GitFork, BookOpen, Layers, Cpu, Bookmark, Filter, RotateCcw, 
  Play, Pause, BarChart3, Clock, Milestone
} from 'lucide-react';

export const KnowledgeGraph: React.FC = () => {
  const {
    nodes,
    links,
    activeProvider,
    setActiveProvider,
    indexingStatus,
    indexingProgress,
    indexingMessage,
    triggerIndex,
    cancelIndex,
    fetchHealth,
    connectProgressStream,

    // Filters
    statusFilter,
    languageFilter,
    minImportance,
    nodeTypeFilter,
    tagFilter,
    setFilters,
    resetFilters,

    // Highlight
    highlightMode,
    setHighlightMode,

    // Timeline/Snapshots
    snapshots,
    selectedSnapshotId,
    diffMode,
    setSelectedSnapshotId,
    setDiffMode,
    fetchSnapshots,
    lastIndexDuration,

    // Analytics
    analytics
  } = useKnowledgeStore();

  const graphRef = useRef<any>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const playTimerRef = useRef<any>(null);

  // Initialize data on mount
  useEffect(() => {
    setActiveProvider('knowledge');
    fetchHealth();
    fetchSnapshots();
    const disconnect = connectProgressStream();
    return () => {
      disconnect();
      if (playTimerRef.current) clearInterval(playTimerRef.current);
    };
  }, [setActiveProvider, fetchHealth, fetchSnapshots, connectProgressStream]);

  // Autoplay timeline snapshot progression
  useEffect(() => {
    if (isPlaying) {
      if (snapshots.length === 0) return;
      playTimerRef.current = setInterval(() => {
        const currIdx = snapshots.findIndex((s) => s.snapshot_id === selectedSnapshotId);
        let nextIdx = currIdx - 1; // snapshots list is sorted DESC
        if (nextIdx < 0) nextIdx = snapshots.length - 1;
        setSelectedSnapshotId(snapshots[nextIdx].snapshot_id);
      }, 3000);
    } else {
      if (playTimerRef.current) {
        clearInterval(playTimerRef.current);
        playTimerRef.current = null;
      }
    }
    return () => {
      if (playTimerRef.current) clearInterval(playTimerRef.current);
    };
  }, [isPlaying, snapshots, selectedSnapshotId, setSelectedSnapshotId]);

  const providerTabs: { type: ProviderType; label: string; icon: React.ComponentType<any> }[] = [
    { type: 'knowledge', label: 'Atlas Workspace', icon: GitFork },
    { type: 'memory', label: 'AI Memory', icon: Cpu },
    { type: 'code', label: 'Source Architecture', icon: Database },
    { type: 'workflow', label: 'Workflows Flow', icon: Layers },
    { type: 'agent', label: 'Active Agents', icon: Cpu },
    { type: 'document', label: 'Markdown Vault', icon: BookOpen },
    { type: 'research', label: 'Research Papers', icon: BookOpen },
    { type: 'timeline', label: 'Timeline Index', icon: Bookmark }
  ];

  const highlightModesList: { mode: HighlightMode; label: string }[] = [
    { mode: 'normal', label: 'Normal' },
    { mode: 'dependencies', label: 'Dependencies' },
    { mode: 'imports', label: 'Imports' },
    { mode: 'inheritance', label: 'Inheritance' },
    { mode: 'documentation', label: 'Docs Links' },
    { mode: 'workflows', label: 'Workflows' },
    { mode: 'memory', label: 'Cognitive' },
    { mode: 'analytics', label: 'Analytics' }
  ];

  const handleZoomIn = () => {
    if (graphRef.current) {
      const scale = graphRef.current.zoom();
      graphRef.current.zoom(scale * 1.25, 300);
    }
  };

  const handleZoomOut = () => {
    if (graphRef.current) {
      const scale = graphRef.current.zoom();
      graphRef.current.zoom(scale / 1.25, 300);
    }
  };

  const handleReset = () => {
    if (graphRef.current) {
      graphRef.current.zoomToFit(400, 50);
    }
  };

  const isIndexingActive = 
    indexingStatus !== 'IDLE' && 
    indexingStatus !== 'COMPLETED' && 
    indexingStatus !== 'FAILED' && 
    indexingStatus !== 'CANCELLED';

  // Find slider position
  const sliderValue = snapshots.length > 0 && selectedSnapshotId
    ? snapshots.length - 1 - snapshots.findIndex((s) => s.snapshot_id === selectedSnapshotId)
    : 0;

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseInt(e.target.value);
    const snapIdx = snapshots.length - 1 - val;
    if (snapshots[snapIdx]) {
      setSelectedSnapshotId(snapshots[snapIdx].snapshot_id);
    }
  };

  return (
    <div className="flex h-[760px] border border-matte-border/30 rounded-2xl overflow-hidden bg-zinc-950 select-none relative font-mono">
      {/* Side Tab Provider & Filters Panel */}
      <div className="w-[220px] bg-black/60 border-r border-matte-border/25 flex flex-col justify-between py-4 pr-1 pl-2 overflow-y-auto scrollbar-none">
        <div className="space-y-5">
          {/* Data Providers */}
          <div className="space-y-1">
            <div className="px-3 pb-1 border-b border-matte-border/10">
              <span className="text-[8px] text-zinc-500 font-bold uppercase tracking-widest">
                Data Providers
              </span>
            </div>
            <div className="space-y-0.5">
              {providerTabs.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeProvider === tab.type;
                return (
                  <button
                    key={tab.type}
                    onClick={() => setActiveProvider(tab.type)}
                    className={`w-full flex items-center gap-2 px-2.5 py-2 rounded-xl font-mono text-[9px] uppercase tracking-wider text-left transition-all duration-150 cursor-pointer
                      ${isActive
                        ? 'bg-cyan-dim/15 text-cyan-glow border-l-2 border-cyan-glow font-bold'
                        : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900/30'
                      }
                    `}
                  >
                    <Icon className="w-3.5 h-3.5 flex-shrink-0" />
                    <span className="truncate">{tab.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Highlight Mode selectors */}
          <div className="space-y-1">
            <div className="px-3 pb-1 border-b border-matte-border/10">
              <span className="text-[8px] text-zinc-500 font-bold uppercase tracking-widest">
                Highlight Mode
              </span>
            </div>
            <div className="grid grid-cols-2 gap-1 p-1">
              {highlightModesList.map((hl) => {
                const isActive = highlightMode === hl.mode;
                return (
                  <button
                    key={hl.mode}
                    onClick={() => setHighlightMode(hl.mode)}
                    className={`px-1.5 py-1.5 rounded-lg border text-[8.5px] font-mono text-center truncate tracking-tight transition-all cursor-pointer
                      ${isActive
                        ? 'bg-cyan-dim/15 border-cyan-glow/40 text-cyan-glow font-extrabold'
                        : 'bg-transparent border-transparent text-zinc-500 hover:text-zinc-300'
                      }
                    `}
                  >
                    {hl.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Advanced Graph Filters */}
          <div className="space-y-2.5 px-1.5">
            <div className="flex justify-between items-center pb-1 border-b border-matte-border/10">
              <span className="text-[8px] text-zinc-500 font-bold uppercase tracking-widest flex items-center gap-1">
                <Filter className="w-2.5 h-2.5" /> Graph Filters
              </span>
              <button 
                onClick={resetFilters} 
                className="text-[7.5px] text-cyan-glow hover:underline cursor-pointer flex items-center gap-0.5"
              >
                <RotateCcw className="w-2 h-2" /> RESET
              </button>
            </div>

            <div className="space-y-2 text-[9px] font-mono">
              {/* Type selection */}
              <div className="space-y-1">
                <span className="text-zinc-500 block uppercase">Node Type</span>
                <select
                  value={nodeTypeFilter || ''}
                  onChange={(e) => setFilters({ nodeTypeFilter: e.target.value || null })}
                  className="w-full bg-zinc-900 border border-matte-border/20 text-zinc-300 rounded px-2 py-1 outline-none"
                >
                  <option value="">ALL TYPES</option>
                  <option value="code">CODE FILE</option>
                  <option value="class">CLASS</option>
                  <option value="interface">INTERFACE</option>
                  <option value="function">FUNCTION</option>
                  <option value="route">API ROUTE</option>
                  <option value="workflow">WORKFLOW</option>
                  <option value="document">DOCUMENT</option>
                  <option value="manifest">MANIFEST</option>
                </select>
              </div>

              {/* Status selection */}
              <div className="space-y-1">
                <span className="text-zinc-500 block uppercase">Health Diagnostics</span>
                <select
                  value={statusFilter || ''}
                  onChange={(e) => setFilters({ statusFilter: e.target.value || null })}
                  className="w-full bg-zinc-900 border border-matte-border/20 text-zinc-300 rounded px-2 py-1 outline-none"
                >
                  <option value="">ALL DIAGNOSTICS</option>
                  <option value="HEALTHY">HEALTHY</option>
                  <option value="WARNING">WARNING</option>
                  <option value="DEPRECATED">DEPRECATED</option>
                  <option value="EXPERIMENTAL">EXPERIMENTAL</option>
                  <option value="BROKEN">BROKEN</option>
                  <option value="DISCONNECTED">DISCONNECTED</option>
                </select>
              </div>

              {/* Language selection */}
              <div className="space-y-1">
                <span className="text-zinc-500 block uppercase">Language</span>
                <select
                  value={languageFilter || ''}
                  onChange={(e) => setFilters({ languageFilter: e.target.value || null })}
                  className="w-full bg-zinc-900 border border-matte-border/20 text-zinc-300 rounded px-2 py-1 outline-none"
                >
                  <option value="">ALL LANGUAGES</option>
                  <option value="python">PYTHON</option>
                  <option value="typescript">TYPESCRIPT</option>
                  <option value="markdown">MARKDOWN</option>
                </select>
              </div>

              {/* Slider minImportance */}
              <div className="space-y-1">
                <div className="flex justify-between text-zinc-500">
                  <span>IMPORTANCE</span>
                  <span className="text-zinc-300 font-bold">{(minImportance * 100).toFixed(0)}%</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.1"
                  value={minImportance}
                  onChange={(e) => setFilters({ minImportance: parseFloat(e.target.value) })}
                  className="w-full h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-cyan-glow"
                />
              </div>

              {/* Tag filtering text box */}
              <div className="space-y-1">
                <span className="text-zinc-500 block uppercase">Filter By Tag</span>
                <input
                  type="text"
                  placeholder="e.g. backend..."
                  value={tagFilter || ''}
                  onChange={(e) => setFilters({ tagFilter: e.target.value || null })}
                  className="w-full bg-zinc-900 border border-matte-border/20 text-zinc-300 rounded px-2 py-1 outline-none"
                />
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-3 pt-3">
          {/* Re-indexing trigger button */}
          <div className="px-1.5">
            {isIndexingActive ? (
              <button
                onClick={cancelIndex}
                className="w-full h-8 font-mono text-[9px] uppercase tracking-wider bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 rounded-xl cursor-pointer transition-all"
              >
                CANCEL INDEX
              </button>
            ) : (
              <button
                onClick={triggerIndex}
                className="w-full h-8 font-mono text-[9px] uppercase tracking-wider bg-cyan-dim/15 hover:bg-cyan-glow hover:text-black text-cyan-glow border border-cyan-border/20 rounded-xl cursor-pointer transition-all"
              >
                RE-INDEX REPO
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Main Canvas Area */}
      <div className="flex-1 h-full relative overflow-hidden bg-zinc-950">
        {/* SSE Indexing Progress Bar Overlay */}
        {isIndexingActive && (
          <div className="absolute top-20 left-6 right-6 bg-black/90 border border-cyan-border/25 rounded-xl p-4 z-30 font-mono text-[10px] space-y-2.5 text-zinc-300 backdrop-blur-md shadow-2xl">
            <div className="flex justify-between items-center">
              <span className="text-cyan-glow font-bold uppercase tracking-widest animate-pulse">
                INDEXING PIPELINE RUNNING [{indexingStatus}]
              </span>
              <span className="font-bold text-cyan-glow">{indexingProgress}%</span>
            </div>
            <div className="w-full h-1.5 bg-zinc-900 rounded-full overflow-hidden">
              <div 
                className="h-full bg-cyan-glow transition-all duration-300"
                style={{ width: `${indexingProgress}%` }}
              />
            </div>
            <div className="text-[9px] text-zinc-500 truncate uppercase tracking-wider">
              {indexingMessage}
            </div>
          </div>
        )}

        {/* Floating Headers */}
        <div className="absolute top-5 left-6 right-5 flex items-center justify-between pointer-events-none z-20 gap-4">
          <div className="pointer-events-auto">
            <SearchBar />
          </div>
          <div className="pointer-events-auto">
            <GraphControls
              onZoomIn={handleZoomIn}
              onZoomOut={handleZoomOut}
              onReset={handleReset}
            />
          </div>
        </div>

        {/* Legend Panel overlay */}
        <Legend />

        {/* Mini Analytics Dashboard Panel overlay */}
        <div className="absolute top-64 left-5 bg-black/55 border border-matte-border/30 backdrop-blur-md px-4 py-4 rounded-2xl w-60 select-none space-y-3 pointer-events-auto z-20">
          <h4 className="font-mono text-[9px] text-zinc-500 uppercase tracking-widest flex items-center gap-1.5">
            <BarChart3 className="w-3.5 h-3.5 text-cyan-glow" /> Analytics Dashboard
          </h4>
          
          <div className="space-y-1.5 text-[8.5px] font-mono text-zinc-400">
            <div className="flex justify-between">
              <span>Nodes / Edges:</span>
              <span className="font-bold text-zinc-200">{nodes.length} / {links.length}</span>
            </div>
            <div className="flex justify-between">
              <span>Weakly Components:</span>
              <span className="font-bold text-zinc-200">{analytics?.componentsCount || 0}</span>
            </div>
            <div className="flex justify-between">
              <span>Circular Cycles:</span>
              <span className={`font-bold ${analytics && analytics.cyclesCount > 0 ? 'text-red-400 animate-pulse' : 'text-zinc-200'}`}>
                {analytics?.cyclesCount || 0}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Orphan Node Count:</span>
              <span className="font-bold text-zinc-200">{analytics?.orphansCount || 0}</span>
            </div>
            <div className="flex justify-between border-t border-matte-border/15 pt-1.5">
              <span className="flex items-center gap-0.5"><Clock className="w-2.5 h-2.5 text-zinc-500" /> INDEX DURATION:</span>
              <span className="font-bold text-zinc-200">{(lastIndexDuration || 0).toFixed(1)}s</span>
            </div>
            {selectedSnapshotId && (
              <div className="flex justify-between text-[8px] text-zinc-500 truncate">
                <span className="flex items-center gap-0.5"><Milestone className="w-2.5 h-2.5 text-zinc-600" /> ACTIVE SNAPSHOT:</span>
                <span className="font-bold text-zinc-400 uppercase tracking-tight">{selectedSnapshotId.split('_').pop() || selectedSnapshotId}</span>
              </div>
            )}
          </div>
        </div>

        {/* MiniMap locator overlay */}
        <MiniMap />

        {/* Main interactive force canvas */}
        <GraphCanvas onRefReady={(instance) => { graphRef.current = instance; }} />

        {/* Bottom Timeline snapshot comparisons slider */}
        {snapshots.length > 0 && (
          <div className="absolute bottom-5 left-6 right-5 bg-black/55 border border-matte-border/30 backdrop-blur-md px-5 py-3 rounded-2xl pointer-events-auto z-20 flex items-center justify-between gap-5 font-mono text-[9px]">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className={`p-1.5 rounded-lg border cursor-pointer hover:bg-zinc-800 transition-colors flex items-center justify-center
                  ${isPlaying ? 'border-cyan-glow text-cyan-glow' : 'border-matte-border/30 text-zinc-400'}
                `}
                title={isPlaying ? "Pause Timeline Autoplay" : "Play Timeline Autoplay"}
              >
                {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
              </button>

              <button
                onClick={() => setDiffMode(!diffMode)}
                className={`px-3 py-1.5 rounded-lg border font-bold cursor-pointer transition-colors text-[8.5px] uppercase tracking-wider
                  ${diffMode 
                    ? 'bg-cyan-dim/15 border-cyan-glow/50 text-cyan-glow shadow-[0_0_10px_rgba(0,242,254,0.03)]'
                    : 'bg-zinc-950 border-matte-border/30 text-zinc-500 hover:text-zinc-300'
                  }
                `}
                title="Highlight added/removed/modified nodes between snapshots"
              >
                Snapshot Diff Mode
              </button>
            </div>

            {/* Slider track bar */}
            <div className="flex-1 flex items-center gap-3">
              <span className="text-zinc-500 uppercase text-[8px]">Older</span>
              <input
                type="range"
                min="0"
                max={snapshots.length - 1}
                value={sliderValue}
                onChange={handleSliderChange}
                className="flex-1 h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-cyan-glow"
              />
              <span className="text-cyan-glow font-bold uppercase text-[8px]">Newest</span>
            </div>

            {/* Date Details stamp */}
            <div className="text-right flex flex-col justify-center max-w-[20%] text-[8px]">
              <span className="text-zinc-300 font-bold uppercase truncate max-w-[150px]" title={selectedSnapshotId || ''}>
                {selectedSnapshotId?.split('_').pop() || selectedSnapshotId}
              </span>
              <span className="text-zinc-500 font-medium">
                {selectedSnapshotId ? new Date(snapshots.find(s => s.snapshot_id === selectedSnapshotId)?.created_at || '').toLocaleString() : ''}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Side Inspector Panel Dock */}
      <InspectorPanel />
    </div>
  );
};
export default KnowledgeGraph;
