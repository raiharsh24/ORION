import React from 'react';
import { useKnowledgeStore } from '../store/useKnowledgeStore';
import { GraphAnalytics } from '../engine/GraphAnalytics';
import { X, HardDrive, ArrowRight, Star, Anchor, FileJson, MessageSquare, Bookmark, EyeOff, Target, AlertTriangle } from 'lucide-react';

export const InspectorPanel: React.FC = () => {
  const { 
    nodes, 
    links, 
    selectedNodeId, 
    setSelectedNodeId, 
    analytics,
    bookmarks,
    addBookmark,
    removeBookmark,
    hiddenNodeIds,
    toggleHideNode,
    focusedSubtreeRootId,
    focusSubtree
  } = useKnowledgeStore();

  const selectedNode = nodes.find((n) => n.id === selectedNodeId) || null;

  if (!selectedNode) {
    return (
      <div className="w-[320px] bg-black/45 border-l border-matte-border/30 p-6 flex flex-col justify-center items-center text-center text-zinc-500 font-mono text-xs select-none">
        <Star className="w-8 h-8 text-zinc-700 mb-3 animate-pulse" />
        <span>SELECT A GRAPH NODE TO AUDIT LIVE DIAGNOSTICS & RELATIONSHIPS</span>
      </div>
    );
  }

  // Filter linked connections
  const connectedRelations = links.filter((link) => {
    const sId = typeof link.source === 'string' ? link.source : (link.source as any).id;
    const tId = typeof link.target === 'string' ? link.target : (link.target as any).id;
    return sId === selectedNode.id || tId === selectedNode.id;
  });

  const incomingDeps = connectedRelations.filter((link) => {
    const tId = typeof link.target === 'string' ? link.target : (link.target as any).id;
    return tId === selectedNode.id;
  });

  const outgoingDeps = connectedRelations.filter((link) => {
    const sId = typeof link.source === 'string' ? link.source : (link.source as any).id;
    return sId === selectedNode.id;
  });

  const getStatusStyle = (status: string) => {
    switch (status) {
      case 'HEALTHY':
        return 'text-cyan-glow border-cyan-border/25 bg-cyan-dim/5';
      case 'WARNING':
        return 'text-amber-400 border-amber-500/20 bg-amber-500/5';
      case 'DEPRECATED':
        return 'text-purple-400 border-purple-500/20 bg-purple-500/5';
      case 'EXPERIMENTAL':
        return 'text-blue-400 border-blue-500/20 bg-blue-500/5';
      case 'BROKEN':
      case 'ERROR':
        return 'text-red-400 border-red-500/20 bg-red-500/5 animate-pulse';
      case 'OFFLINE':
      default:
        return 'text-zinc-500 border-zinc-800 bg-zinc-950';
    }
  };

  const handleTogglePin = () => {
    if (selectedNode.fx === null || selectedNode.fx === undefined) {
      selectedNode.fx = selectedNode.x;
      selectedNode.fy = selectedNode.y;
    } else {
      selectedNode.fx = null;
      selectedNode.fy = null;
    }
    useKnowledgeStore.setState({ nodes: [...nodes] });
  };

  const isBookmarked = bookmarks.includes(selectedNode.id);
  const handleToggleBookmark = () => {
    if (isBookmarked) {
      removeBookmark(selectedNode.id);
    } else {
      addBookmark(selectedNode.id);
    }
  };

  const isHidden = hiddenNodeIds.has(selectedNode.id);
  const isFocusedRoot = focusedSubtreeRootId === selectedNode.id;

  const nodeMetric = analytics?.nodeMetrics[selectedNode.id];

  // Calculate Shortest Path to Root Subsystem anchor
  const rootNode = nodes.find(
    (n) => n.id === 'friday' || n.id === 'agent_memory' || n.id === 'agent_timeline' || n.id === 'agent_coordinator'
  );
  const shortestPath = rootNode && selectedNode.id !== rootNode.id
    ? GraphAnalytics.findShortestPath(nodes, links, selectedNode.id, rootNode.id)
    : null;

  const handleExportJSON = () => {
    console.log('ATLAS NODE EXPORT:', JSON.stringify(selectedNode, null, 2));
    alert(`Node ${selectedNode.title} exported to console logs!`);
  };

  const renderCustomMetadata = () => {
    const meta = selectedNode.metadata || {};
    const type = selectedNode.type;

    if (type === 'code' || type === 'class' || type === 'interface' || type === 'function' || type === 'route') {
      return (
        <div className="space-y-2">
          <h4 className="font-mono text-[9px] text-zinc-500 uppercase tracking-widest">
            Code Declarations
          </h4>
          <div className="space-y-1.5 text-[9px] font-mono">
            {meta.path && (
              <div className="flex justify-between p-2.5 bg-black/40 border border-matte-border/30 rounded-xl">
                <span className="text-zinc-500">Path</span>
                <span className="text-zinc-300 font-bold truncate max-w-[65%]" title={meta.path}>
                  {meta.path}
                </span>
              </div>
            )}
            {meta.language && (
              <div className="flex justify-between p-2.5 bg-black/40 border border-matte-border/30 rounded-xl">
                <span className="text-zinc-500">Language</span>
                <span className="text-cyan-glow font-bold uppercase">{meta.language}</span>
              </div>
            )}
            {meta.inherits && Array.isArray(meta.inherits) && meta.inherits.length > 0 && (
              <div className="flex justify-between p-2.5 bg-black/40 border border-matte-border/30 rounded-xl">
                <span className="text-zinc-500">Inherits</span>
                <span className="text-zinc-300 font-bold">{meta.inherits.join(', ')}</span>
              </div>
            )}
          </div>
        </div>
      );
    }

    if (type === 'document' || type === 'research' || type === 'manifest') {
      return (
        <div className="space-y-2">
          <h4 className="font-mono text-[9px] text-zinc-500 uppercase tracking-widest">
            Document Vault
          </h4>
          <div className="space-y-1.5 text-[9px] font-mono">
            {selectedNode.tags && selectedNode.tags.length > 0 && (
              <div className="flex flex-wrap gap-1 p-2.5 bg-black/40 border border-matte-border/30 rounded-xl">
                <span className="text-zinc-500 w-full mb-1">Tags</span>
                {selectedNode.tags.map((tag: string) => (
                  <span key={tag} className="px-2 py-0.5 bg-cyan-dim/10 border border-cyan-border/20 text-cyan-glow rounded text-[8px]">
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="w-[320px] bg-black/45 border-l border-matte-border/30 flex flex-col h-full select-none overflow-hidden backdrop-blur-md">
      {/* Panel Header */}
      <div className="p-5 border-b border-matte-border/25 flex items-center justify-between bg-black/10">
        <div className="flex items-center gap-2">
          <HardDrive className="w-4 h-4 animate-pulse text-cyan-glow" />
          <h3 className="font-mono text-xs font-bold uppercase tracking-widest text-zinc-200">
            Node Inspector
          </h3>
        </div>
        <button
          onClick={() => setSelectedNodeId(null)}
          className="p-1 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-900 border border-transparent hover:border-matte-border/30 transition-all cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto p-5 space-y-6 scrollbar-thin">
        {/* Circular Dependency Alert Warning */}
        {nodeMetric?.inCycle && (
          <div className="p-3 bg-red-500/10 border border-red-500/35 rounded-xl flex items-start gap-2.5 font-mono text-[9px] text-red-400">
            <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <span className="font-extrabold uppercase block mb-0.5">Circular Warning</span>
              This node resides inside an active circular dependency cycle loop!
            </div>
          </div>
        )}

        {/* Title Details */}
        <div className="space-y-3.5">
          <div className="flex justify-between items-start">
            <div className="max-w-[70%]">
              <h2 className="text-base font-extrabold text-zinc-100 font-mono tracking-tight truncate" title={selectedNode.title}>
                {selectedNode.title}
              </h2>
              <span className="font-mono text-[8px] bg-zinc-900 border border-zinc-800 text-zinc-500 px-1.5 py-0.5 rounded uppercase tracking-wider mt-1 inline-block">
                Type: {selectedNode.type}
              </span>
            </div>
            <span className={`font-mono text-[8.5px] border px-2 py-0.5 rounded font-extrabold uppercase tracking-widest ${getStatusStyle(selectedNode.status)}`}>
              {selectedNode.status}
            </span>
          </div>

          <p className="text-[10px] leading-relaxed text-zinc-400 font-mono">
            {selectedNode.description}
          </p>
        </div>

        {/* Action Panel Macros */}
        <div className="space-y-2">
          <h4 className="font-mono text-[9px] text-zinc-500 uppercase tracking-widest">
            Atlas Actions
          </h4>
          <div className="grid grid-cols-2 gap-2 text-[9px] font-mono">
            <button
              onClick={handleTogglePin}
              className={`flex items-center gap-1.5 p-2 bg-zinc-900/30 border border-matte-border/25 rounded-lg text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer
                ${(selectedNode.fx !== null && selectedNode.fx !== undefined) ? 'border-cyan-glow/40 text-cyan-glow' : ''}
              `}
            >
              <Anchor className="w-3.5 h-3.5" />
              <span>{selectedNode.fx !== null && selectedNode.fx !== undefined ? 'UNPIN' : 'PIN POSITION'}</span>
            </button>
            <button
              onClick={handleToggleBookmark}
              className={`flex items-center gap-1.5 p-2 bg-zinc-900/30 border border-matte-border/25 rounded-lg text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer
                ${isBookmarked ? 'border-cyan-glow/40 text-cyan-glow' : ''}
              `}
            >
              <Bookmark className="w-3.5 h-3.5" />
              <span>{isBookmarked ? 'BOOKMARKED' : 'BOOKMARK'}</span>
            </button>
            <button
              onClick={() => toggleHideNode(selectedNode.id)}
              className={`flex items-center gap-1.5 p-2 bg-zinc-900/30 border border-matte-border/25 rounded-lg text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer
                ${isHidden ? 'border-cyan-glow/40 text-cyan-glow' : ''}
              `}
            >
              <EyeOff className="w-3.5 h-3.5" />
              <span>{isHidden ? 'HIDDEN' : 'HIDE NODE'}</span>
            </button>
            <button
              onClick={() => focusSubtree(isFocusedRoot ? null : selectedNode.id)}
              className={`flex items-center gap-1.5 p-2 bg-zinc-900/30 border border-matte-border/25 rounded-lg text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer
                ${isFocusedRoot ? 'border-cyan-glow/40 text-cyan-glow' : ''}
              `}
            >
              <Target className="w-3.5 h-3.5" />
              <span>{isFocusedRoot ? 'CLEAR FOCUS' : 'FOCUS SUBTREE'}</span>
            </button>
            <button
              onClick={() => handleExportJSON()}
              className="flex items-center gap-1.5 p-2 bg-zinc-900/30 border border-matte-border/25 rounded-lg text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer"
            >
              <FileJson className="w-3.5 h-3.5" />
              <span>EXPORT JSON</span>
            </button>
            <button
              onClick={() => alert(`Context prompt generated: "Tell me about the ${selectedNode.title} subsystem."`)}
              className="flex items-center gap-1.5 p-2 bg-zinc-900/30 border border-matte-border/25 rounded-lg text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer justify-center border-cyan-glow/20"
            >
              <MessageSquare className="w-3.5 h-3.5 text-cyan-glow" />
              <span>QUERY COGNITIVE</span>
            </button>
          </div>
        </div>

        {/* Shortest path mapping details */}
        {shortestPath && (
          <div className="space-y-2">
            <h4 className="font-mono text-[9px] text-zinc-500 uppercase tracking-widest">
              Shortest Path To Root
            </h4>
            <div className="p-3 bg-black/40 border border-matte-border/30 rounded-xl font-mono text-[8.5px] text-zinc-400 flex flex-wrap items-center gap-1.5">
              {shortestPath.map((step, idx) => {
                const nodeObj = nodes.find((n) => n.id === step);
                const name = nodeObj?.title || step.split('#').pop() || step;
                return (
                  <React.Fragment key={step}>
                    <span 
                      onClick={() => setSelectedNodeId(step)}
                      className="cursor-pointer hover:text-cyan-glow truncate max-w-[100px] font-bold"
                    >
                      {name}
                    </span>
                    {idx < shortestPath.length - 1 && <ArrowRight className="w-2.5 h-2.5 text-zinc-600 flex-shrink-0" />}
                  </React.Fragment>
                );
              })}
            </div>
          </div>
        )}

        {/* Node metrics detail parameters */}
        {nodeMetric && (
          <div className="space-y-2">
            <h4 className="font-mono text-[9px] text-zinc-500 uppercase tracking-widest">
              Dependency Depth Analysis
            </h4>
            <div className="grid grid-cols-2 gap-2 font-mono text-[9px]">
              <div className="p-2.5 bg-black/40 border border-matte-border/30 rounded-xl text-center">
                <span className="text-zinc-500 block uppercase mb-0.5">Depth</span>
                <span className="text-zinc-200 font-bold text-xs">{nodeMetric.dependencyDepth}</span>
              </div>
              <div className="p-2.5 bg-black/40 border border-matte-border/30 rounded-xl text-center">
                <span className="text-zinc-500 block uppercase mb-0.5">Centrality</span>
                <span className="text-zinc-200 font-bold text-xs">{nodeMetric.degreeCentrality.total}</span>
              </div>
            </div>
          </div>
        )}

        {/* Render Custom metadata block */}
        {renderCustomMetadata()}

        {/* Connected relationships list */}
        <div className="space-y-2">
          <h4 className="font-mono text-[9px] text-zinc-500 uppercase tracking-widest">
            Dependencies ({connectedRelations.length})
          </h4>
          <div className="space-y-3">
            {/* Incoming list */}
            {incomingDeps.length > 0 && (
              <div>
                <span className="text-[8px] text-zinc-500 block uppercase font-bold tracking-wider mb-1">Incoming ({incomingDeps.length})</span>
                <div className="space-y-1">
                  {incomingDeps.slice(0, 15).map((l, i) => {
                    const sId = typeof l.source === 'string' ? l.source : (l.source as any).id;
                    const otherNode = nodes.find((n) => n.id === sId);
                    return (
                      <div 
                        key={i}
                        onClick={() => setSelectedNodeId(sId)}
                        className="px-2.5 py-1.5 bg-zinc-950 border border-matte-border/15 hover:border-cyan-border/20 rounded-lg flex items-center justify-between text-[9px] cursor-pointer group"
                      >
                        <span className="text-zinc-400 group-hover:text-cyan-glow font-bold truncate max-w-[80%]">
                          {otherNode?.title || sId}
                        </span>
                        <ArrowRight className="w-2.5 h-2.5 text-zinc-600 group-hover:text-cyan-glow" />
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Outgoing list */}
            {outgoingDeps.length > 0 && (
              <div>
                <span className="text-[8px] text-zinc-500 block uppercase font-bold tracking-wider mb-1">Outgoing ({outgoingDeps.length})</span>
                <div className="space-y-1">
                  {outgoingDeps.slice(0, 15).map((l, i) => {
                    const tId = typeof l.target === 'string' ? l.target : (l.target as any).id;
                    const otherNode = nodes.find((n) => n.id === tId);
                    return (
                      <div 
                        key={i}
                        onClick={() => setSelectedNodeId(tId)}
                        className="px-2.5 py-1.5 bg-zinc-950 border border-matte-border/15 hover:border-cyan-border/20 rounded-lg flex items-center justify-between text-[9px] cursor-pointer group"
                      >
                        <span className="text-zinc-400 group-hover:text-cyan-glow font-bold truncate max-w-[80%]">
                          {otherNode?.title || tId}
                        </span>
                        <ArrowRight className="w-2.5 h-2.5 text-zinc-600 group-hover:text-cyan-glow" />
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {connectedRelations.length === 0 && (
              <div className="text-center py-4 border border-dashed border-matte-border/30 rounded-xl font-mono text-[9px] text-zinc-600">
                NO SUBBOUND PATHS FOUND
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
export default InspectorPanel;
