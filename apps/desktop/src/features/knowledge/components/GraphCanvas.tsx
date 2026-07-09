import React, { useRef, useEffect, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { useKnowledgeStore } from '../store/useKnowledgeStore';
import { NodeTooltip } from './NodeTooltip';
import type { GraphNode, GraphLink } from '../types';
// @ts-ignore
import { forceCollide, forceX, forceY } from 'd3-force-3d';

interface GraphCanvasProps {
  onRefReady?: (instance: any) => void;
}

export const GraphCanvas: React.FC<GraphCanvasProps> = ({ onRefReady }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);

  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  const {
    nodes,
    links,
    selectedNodeId,
    hoveredNodeId,
    searchQuery,
    setSelectedNodeId,
    setHoveredNodeId,
    setDimensions: setStoreDimensions,
    physicsEnabled,
    linkStrength,
    nodeSize,
    rotationSpeed,
    labelVisibility,
    particleDensity,
    glowStrength,
    layoutMode,
    
    // Filters
    departmentFilter,
    showFolders,
    statusFilter,
    languageFilter,
    minImportance,
    nodeTypeFilter,
    tagFilter,

    // Highlights
    highlightMode,

    // Timeline diffs
    diffMode,
    addedNodeIds,
    removedNodeIds,
    modifiedNodeIds,

    // Analytics Metrics
    analytics,

    // Interactive controls
    hiddenNodeIds,
    focusedSubtreeRootId,

    // Actions / Setters
    setLinkStrength,
    setNodeSize,
    setLabelVisibility,
    setShowFolders,
    collapseAllClusters,
    expandAllClusters,
    bakeSettings
  } = useKnowledgeStore();

  const [gridAngle, setGridAngle] = useState(0);
  const hasFittedRef = useRef(false);
  const settleTimerRef = useRef<any>(null);

  // Pre-compute max non-root radius for root size invariant
  const maxNonRootRadius = React.useMemo(() => {
    let max = 0;
    nodes.forEach((node) => {
      if (node.id === 'friday') return;
      const degree = analytics?.nodeMetrics[node.id]?.degreeCentrality.total || 0;
      const baseSize = 6 + 3 * Math.sqrt(degree);
      const size = Math.max(baseSize * nodeSize, 4);
      if (size > max) max = size;
    });
    return max;
  }, [nodes, analytics, nodeSize]);

  // Dynamic Node Radius hierarchy scaling driven by degree centrality
  const getNodeRadius = (node: GraphNode): number => {
    const isHub = node.id === 'friday';
    const degree = analytics?.nodeMetrics[node.id]?.degreeCentrality.total || 0;
    
    if (isHub) {
      const rawRootRadius = Math.max(28 * nodeSize, 4);
      // Invariant: root must be at least 1.15x the largest non-root node
      return Math.max(rawRootRadius, maxNonRootRadius * 1.15);
    }
    
    const baseSize = 6 + 3 * Math.sqrt(degree);
    return Math.max(baseSize * nodeSize, 4);
  };

  // Identify cluster hubs based on degree centrality within each cluster
  const getFolderGroup = (n: GraphNode): string => {
    const path = n.metadata?.path || '';
    if (!path) return 'unknown';
    const parts = path.split('/');
    return parts.length <= 1 ? 'root' : parts.slice(0, -1).join('/');
  };

  const clusterHubs = React.useMemo(() => {
    const hubs = new Set<string>();
    if (!analytics?.nodeMetrics) return hubs;

    // Group nodes by cluster
    const clusters: Record<string, GraphNode[]> = {};
    nodes.forEach((n) => {
      const g = showFolders ? getFolderGroup(n) : n.category;
      if (!clusters[g]) clusters[g] = [];
      clusters[g].push(n);
    });

    // In each cluster, sort by degree centrality and select top 20% (minimum 3)
    Object.keys(clusters).forEach((g) => {
      const list = clusters[g];
      const sorted = [...list].sort((a, b) => {
        const degA = analytics.nodeMetrics[a.id]?.degreeCentrality.total || 0;
        const degB = analytics.nodeMetrics[b.id]?.degreeCentrality.total || 0;
        return degB - degA;
      });

      const limit = Math.max(1, Math.ceil(list.length * 0.1));
      sorted.slice(0, limit).forEach((n) => {
        const deg = analytics.nodeMetrics[n.id]?.degreeCentrality.total || 0;
        if (n.id === 'friday' || deg >= 2) {
          hubs.add(n.id);
        }
      });
    });

    return hubs;
  }, [nodes, analytics, showFolders]);

  useEffect(() => {
    let animId: number;
    const tickRotation = () => {
      if (rotationSpeed > 0) {
        setGridAngle((prev) => (prev + 0.002 * rotationSpeed) % (Math.PI * 2));
      }
      animId = requestAnimationFrame(tickRotation);
    };
    animId = requestAnimationFrame(tickRotation);
    return () => cancelAnimationFrame(animId);
  }, [rotationSpeed]);

  useEffect(() => {
    if (!containerRef.current) return;

    const observer = new ResizeObserver((entries) => {
      if (!entries || entries.length === 0) return;
      const { width, height } = entries[0].contentRect;
      const w = Math.max(width, 400);
      const h = Math.max(height, 300);
      setDimensions({ width: w, height: h });
      setStoreDimensions(w, h);
    });

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [setStoreDimensions]);

  // Auto-fit camera to show all nodes when layout changes
  useEffect(() => {
    if (!graphRef.current) return;
    hasFittedRef.current = false;
    if (settleTimerRef.current) {
      clearTimeout(settleTimerRef.current);
      settleTimerRef.current = null;
    }

    // Non-physics layouts: nodes pre-positioned, fit immediately
    const timer = setTimeout(() => {
      if (graphRef.current && !hasFittedRef.current) {
        hasFittedRef.current = true;
        graphRef.current.zoomToFit(400, 150);
      }
    }, layoutMode === 'force' ? 5000 : 50);
    return () => clearTimeout(timer);
  }, [layoutMode]);

  // Center camera on node selection
  useEffect(() => {
    if (!graphRef.current || !selectedNodeId) return;
    const node = nodes.find((n) => n.id === selectedNodeId);
    if (node && node.x !== undefined && node.y !== undefined) {
      graphRef.current.centerAt(node.x, node.y, 400);
      graphRef.current.zoom(1.25, 400);
    }
  }, [selectedNodeId, nodes]);

  // Configure D3 forces dynamically
  useEffect(() => {
    if (!graphRef.current) return;

    if (physicsEnabled) {
      // 5. Central hub emphasis: pin 'friday' root node to the center of the coordinates in force mode
      const hubNode = nodes.find((n) => n.id === 'friday');
      if (hubNode) {
        hubNode.fx = dimensions.width / 2;
        hubNode.fy = dimensions.height / 2;
      }

      // 3. Repulsion/link balance: Set strong repulsion strength
      const chargeForce = graphRef.current.d3Force('charge');
      if (chargeForce) {
        chargeForce.strength(-1000 * linkStrength);
      }

      // Link Springs distance and strength balance
      // Intra-cluster links (same department): 80 distance
      // Inter-cluster links (different departments): 300 distance
      const linkForce = graphRef.current.d3Force('link');
      if (linkForce) {
        linkForce.distance((link: any) => {
          const sId = typeof link.source === 'string' ? link.source : (link.source as any).id;
          const tId = typeof link.target === 'string' ? link.target : (link.target as any).id;
          const srcNode = nodes.find((n) => n.id === sId);
          const tgtNode = nodes.find((n) => n.id === tId);
          const sameCluster = srcNode && tgtNode && srcNode.category === tgtNode.category;
          return sameCluster ? 80 * linkStrength : 500 * linkStrength;
        });
        linkForce.strength(0.5 * linkStrength);
      }

      // 2. Collision force: forceCollide with iterations so nodes never overlap
      graphRef.current.d3Force('collide', forceCollide((node: any) => getNodeRadius(node) * 1.35).iterations(3));

      // Cluster centroid centering: pull each node toward its category's designated target
      // Using deterministic radial offsets so different departments separate
      const catNames = [...new Set(nodes.map((n) => n.category || 'unknown'))];
      const catCentroidTargets: Record<string, { x: number; y: number }> = {};
      const cx = dimensions.width / 2;
      const cy = dimensions.height / 2;
      catNames.forEach((cat, i) => {
        const angle = (2 * Math.PI * i) / catNames.length - Math.PI / 2;
        catCentroidTargets[cat] = { x: cx + 1200 * Math.cos(angle), y: cy + 1200 * Math.sin(angle) };
      });
      graphRef.current.d3Force('x', forceX().x((node: any) => catCentroidTargets[node.category]?.x || cx).strength(0.15));
      graphRef.current.d3Force('y', forceY().y((node: any) => catCentroidTargets[node.category]?.y || cy).strength(0.15));

      // Disable default center force so cluster targets aren't pulled to canvas center
      const centerForce = graphRef.current.d3Force('center');
      if (centerForce) centerForce.strength(0);

      graphRef.current.d3ReheatSimulation();
    }
  }, [physicsEnabled, linkStrength, nodes, links, dimensions.width, dimensions.height]);

  useEffect(() => {
    if (graphRef.current && onRefReady) {
      onRefReady(graphRef.current);
    }
  }, [onRefReady]);

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    setTooltipPos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    });
  };

  // Perform full visual node filtering based on active states
  const getFilteredNodes = (): GraphNode[] => {
    let result = nodes;

    // 1. Filter hidden nodes
    if (hiddenNodeIds.size > 0) {
      result = result.filter((n) => !hiddenNodeIds.has(n.id));
    }

    // 2. Filter subtree focus (retain root + direct neighbors)
    if (focusedSubtreeRootId) {
      const neighborIds = new Set<string>([focusedSubtreeRootId]);
      links.forEach((l) => {
        const s = typeof l.source === 'string' ? l.source : (l.source as any).id;
        const t = typeof l.target === 'string' ? l.target : (l.target as any).id;
        if (s === focusedSubtreeRootId) neighborIds.add(t);
        if (t === focusedSubtreeRootId) neighborIds.add(s);
      });
      result = result.filter((n) => neighborIds.has(n.id));
    }

    // 3. Regular Filters
    if (departmentFilter) {
      result = result.filter((n) => n.category === departmentFilter || n.id === 'friday');
    }
    if (!showFolders) {
      result = result.filter((n) => n.type !== 'folder');
    }
    if (statusFilter) {
      result = result.filter((n) => n.status === statusFilter);
    }
    if (languageFilter) {
      result = result.filter((n) => n.metadata?.language === languageFilter);
    }
    if (nodeTypeFilter) {
      result = result.filter((n) => n.type === nodeTypeFilter);
    }
    if (minImportance > 0.0) {
      result = result.filter((n) => n.importance >= minImportance || n.id === 'friday');
    }
    if (tagFilter) {
      result = result.filter((n) => n.tags && n.tags.some((t) => t.toLowerCase() === tagFilter.toLowerCase()));
    }

    return result;
  };

  // Filter links connecting ONLY filtered nodes, and filter by Highlight Modes
  const getFilteredLinks = (filteredNodesList: GraphNode[]): GraphLink[] => {
    const ids = new Set(filteredNodesList.map((n) => n.id));
    
    return links.filter((link) => {
      const sId = typeof link.source === 'string' ? link.source : (link.source as any).id;
      const tId = typeof link.target === 'string' ? link.target : (link.target as any).id;
      
      // Conectivity check
      if (!ids.has(sId) || !ids.has(tId)) return false;

      // Filter by Highlight Mode
      if (highlightMode === 'imports' && link.label !== 'dependency') return false;
      if (highlightMode === 'inheritance' && link.label !== 'inheritance' && link.label !== 'implementation') return false;
      if (highlightMode === 'documentation' && link.label !== 'documentation') return false;
      if (highlightMode === 'workflows' && link.label !== 'workflow') return false;
      if (highlightMode === 'memory' && link.label !== 'memory') return false;

      // Direct dependencies highlight mode
      if (highlightMode === 'dependencies' && selectedNodeId) {
        return sId === selectedNodeId || tId === selectedNodeId;
      }

      return true;
    });
  };

  const activeNodes = getFilteredNodes();
  const activeLinks = getFilteredLinks(activeNodes);

  // Styling helpers
  const getLinkColor = (link: any) => {
    const sId = typeof link.source === 'string' ? link.source : link.source.id;
    const tId = typeof link.target === 'string' ? link.target : link.target.id;
    
    const isPrimary = selectedNodeId === sId || selectedNodeId === tId;
    const isHover = hoveredNodeId === sId || hoveredNodeId === tId;

    if (isPrimary) return 'rgba(0, 242, 254, 0.85)';
    if (isHover) return 'rgba(0, 242, 254, 0.45)';
    
    return 'rgba(39, 39, 42, 0.2)'; // Muted Slate
  };

  const getLinkWidth = (link: any) => {
    const sId = typeof link.source === 'string' ? link.source : link.source.id;
    const tId = typeof link.target === 'string' ? link.target : link.target.id;
    
    if (selectedNodeId === sId || selectedNodeId === tId) return 1.8;
    if (hoveredNodeId === sId || hoveredNodeId === tId) return 1.3;
    return 0.7;
  };

  const drawHexBackground = (ctx: CanvasRenderingContext2D, globalScale: number) => {
    ctx.save();
    const orbits = [90, 180, 270, 360];
    orbits.forEach((r) => {
      ctx.beginPath();
      ctx.arc(0, 0, r, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(0, 242, 254, 0.012)';
      ctx.lineWidth = 0.5 / globalScale;
      ctx.stroke();
    });

    if (globalScale > 0.08) {
      ctx.strokeStyle = 'rgba(39, 39, 42, 0.04)';
      ctx.lineWidth = 0.5;
      
      const size = 50;
      const h = size * Math.sqrt(3);
      const minVal = -3000;
      const maxVal = 3000;

      if (rotationSpeed > 0) {
        ctx.rotate(gridAngle);
      }

      for (let x = minVal; x < maxVal; x += size * 1.5) {
        let col = Math.round(x / (size * 1.5));
        for (let y = minVal; y < maxVal; y += h) {
          const cy = y + (col % 2 === 0 ? 0 : h / 2);
          ctx.beginPath();
          for (let i = 0; i < 6; i++) {
            const angle = (Math.PI / 3) * i;
            ctx.lineTo(x + size * Math.cos(angle), cy + size * Math.sin(angle));
          }
          ctx.closePath();
          ctx.stroke();
        }
      }
    }
    ctx.restore();
  };

  return (
    <div 
      ref={containerRef} 
      onMouseMove={handleMouseMove}
      className="relative w-full h-full bg-zinc-950 overflow-hidden select-none"
    >
      <ForceGraph2D
        ref={graphRef}
        graphData={{ nodes: activeNodes, links: activeLinks }}
        width={dimensions.width}
        height={dimensions.height}
        enableNodeDrag={true}
        enableZoomInteraction={true}
        enablePanInteraction={true}
        cooldownTicks={physicsEnabled ? 120 : 0}
        onEngineTick={() => {
          if (hasFittedRef.current || layoutMode !== 'force') return;
          if (settleTimerRef.current) clearTimeout(settleTimerRef.current);
          settleTimerRef.current = setTimeout(() => {
            if (graphRef.current && !hasFittedRef.current) {
              hasFittedRef.current = true;
              graphRef.current.zoomToFit(400, 150);
            }
          }, 200);
        }}

        onNodeClick={(node: any) => {
          setSelectedNodeId(selectedNodeId === node.id ? null : node.id);
        }}
        onNodeHover={(node: any) => {
          setHoveredNodeId(node ? node.id : null);
          setHoveredNode(node as any);
        }}
        onBackgroundClick={() => {
          setSelectedNodeId(null);
        }}

        linkDirectionalParticles={(link: any) => {
          const sId = typeof link.source === 'string' ? link.source : link.source.id;
          const tId = typeof link.target === 'string' ? link.target : link.target.id;
          const isHighlighted = 
            selectedNodeId === sId || 
            selectedNodeId === tId || 
            hoveredNodeId === sId || 
            hoveredNodeId === tId;
          return isHighlighted ? Math.round(3 * particleDensity) : 0;
        }}
        linkDirectionalParticleWidth={1.5}
        linkDirectionalParticleSpeed={0.007}
        linkDirectionalParticleColor={() => '#00f2fe'}
        linkColor={getLinkColor}
        linkWidth={getLinkWidth}
        linkDirectionalArrowLength={3.5}
        linkDirectionalArrowRelPos={0.98}

        onRenderFramePre={(ctx: CanvasRenderingContext2D, globalScale: number) => {
          drawHexBackground(ctx, globalScale);
        }}

        nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
          const label = node.title || node.id;
          // 4. Node size hierarchy based on degree centrality
          const size = getNodeRadius(node);

          // Frustum culling estimation
          const currentCenter = graphRef.current && graphRef.current.getGraphBbox ? graphRef.current.getGraphBbox() : null;
          let inView = true;
          if (currentCenter && node.x !== undefined) {
            if (Math.abs(node.x) > 2800 || Math.abs(node.y) > 2800) {
              inView = false;
            }
          }
          if (!inView) return;

          // Grouping logic for color classification
          const getFolderGroup = (n: GraphNode): string => {
            const path = n.metadata?.path || '';
            if (!path) return 'unknown';
            const parts = path.split('/');
            return parts.length <= 1 ? 'root' : parts.slice(0, -1).join('/');
          };

          const stringToColor = (str: string): string => {
            if (!str) return '#71717a';
            let hash = 0;
            for (let i = 0; i < str.length; i++) {
              hash = str.charCodeAt(i) + ((hash << 5) - hash);
            }
            const h = Math.abs(hash) % 360;
            return `hsl(${h}, 70%, 50%)`;
          };

          const stringToFillColor = (str: string): string => {
            if (!str) return '#18181b';
            let hash = 0;
            for (let i = 0; i < str.length; i++) {
              hash = str.charCodeAt(i) + ((hash << 5) - hash);
            }
            const h = Math.abs(hash) % 360;
            return `hsl(${h}, 40%, 8%)`;
          };

          const activeGroupName = showFolders ? getFolderGroup(node) : node.category;
          let strokeColor = stringToColor(activeGroupName);
          let fillColor = stringToFillColor(activeGroupName);

          // Override color logic when timeline diff mode is active
          if (diffMode) {
            if (addedNodeIds.has(node.id)) {
              strokeColor = '#22c55e'; // Green
              fillColor = '#052e16';
            } else if (removedNodeIds.has(node.id)) {
              strokeColor = '#ef4444'; // Red
              fillColor = '#450a0a';
            } else if (modifiedNodeIds.has(node.id)) {
              strokeColor = '#f97316'; // Orange
              fillColor = '#431407';
            }
          }

          // Override color logic when graph theory analytics view is activated
          if (highlightMode === 'analytics' && analytics?.nodeMetrics[node.id]) {
            const metric = analytics.nodeMetrics[node.id];
            if (metric.isBridge) {
              strokeColor = '#eab308'; // Yellow Bridge
              fillColor = '#3a2b00';
            } else if (metric.inCycle) {
              strokeColor = '#d946ef'; // Magenta Cycle
              fillColor = '#3c003c';
            } else if (metric.isHotspot) {
              strokeColor = '#ef4444'; // Red Hotspot
              fillColor = '#2e0000';
            } else if (metric.isOrphan) {
              strokeColor = '#6b7280'; // Grey Orphan
              fillColor = '#1f2937';
            } else {
              strokeColor = '#00f2fe';
              fillColor = '#001c1e';
            }
          }

          const isSelected = selectedNodeId === node.id;
          const isHovered = hoveredNodeId === node.id;

          let isFaded = false;
          if (searchQuery.trim()) {
            const q = searchQuery.toLowerCase();
            const matches = 
              node.title.toLowerCase().includes(q) || 
              (node.description && node.description.toLowerCase().includes(q)) ||
              (node.type && node.type.toLowerCase().includes(q)) ||
              (node.tags && node.tags.some((t: string) => t.toLowerCase().includes(q))) ||
              (node.metadata?.path && String(node.metadata.path).toLowerCase().includes(q));
            if (!matches) isFaded = true;
          }

          ctx.save();
          ctx.globalAlpha = isFaded ? 0.12 : 1.0;

          const drawDetailed = globalScale >= 0.25;
          // 1. Label visibility logic: default only hub nodes + selected + hovered are shown.
          // Toggled to show all if labelVisibility is true.
          const isHub = node.id === 'friday';
          const isClusterHub = clusterHubs.has(node.id);
          const drawLabel = isSelected || isHovered || labelVisibility || isHub || isClusterHub;

          // 6. Soft glow/bloom on cluster nodes
          if (glowStrength > 0) {
            ctx.shadowColor = strokeColor;
            const baseBlur = isHub ? 24 : (isSelected || isHovered) ? 18 : 10;
            ctx.shadowBlur = baseBlur * glowStrength;
          }

          // Draw central hub anchor node if id is 'friday'
          if (node.id === 'friday') {
            ctx.beginPath();
            ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
            ctx.fillStyle = '#0f172a';
            ctx.fill();

            ctx.lineWidth = isSelected ? 4.5 : 3.0;
            ctx.strokeStyle = '#00f2fe';
            ctx.stroke();

            ctx.beginPath();
            ctx.arc(node.x, node.y, size - 4, 0, 2 * Math.PI, false);
            ctx.strokeStyle = 'rgba(0, 242, 254, 0.4)';
            ctx.lineWidth = 1.0;
            ctx.stroke();

            ctx.font = `800 ${size * 0.7}px monospace`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = '#00f2fe';
            ctx.fillText('⚡', node.x, node.y);
          } else if (layoutMode === 'hex' || node.type === 'application') {
            // Draw hexagon for hex layout mode or application node type
            ctx.beginPath();
            for (let i = 0; i < 6; i++) {
              const angle = (Math.PI / 3) * i;
              ctx.lineTo(node.x + size * Math.cos(angle), node.y + size * Math.sin(angle));
            }
            ctx.closePath();
            ctx.fillStyle = fillColor;
            ctx.fill();
            ctx.lineWidth = isSelected ? 2.5 : 1.0;
            ctx.strokeStyle = strokeColor;
            ctx.stroke();
          } else {
            // Draw circle for standard nodes
            ctx.beginPath();
            ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
            ctx.fillStyle = fillColor;
            ctx.fill();
            ctx.lineWidth = isSelected ? 2.5 : 1.0;
            ctx.strokeStyle = strokeColor;
            ctx.stroke();
          }

          ctx.shadowBlur = 0;

          // Render error or modified pulse glow ring
          if (drawDetailed && (node.status === 'BROKEN' || node.status === 'ERROR' || (diffMode && modifiedNodeIds.has(node.id)))) {
            const pulse = size + 4 + Math.sin(Date.now() / 150) * 1.5;
            ctx.beginPath();
            ctx.arc(node.x, node.y, pulse, 0, 2 * Math.PI, false);
            ctx.lineWidth = 0.5;
            ctx.strokeStyle = node.status === 'BROKEN' || node.status === 'ERROR' ? 'rgba(239, 68, 68, 0.35)' : 'rgba(249, 115, 22, 0.35)';
            ctx.stroke();
          }

          if (drawLabel) {
            const fontSize = Math.max(9 / Math.sqrt(globalScale), 3.5);
            ctx.font = `600 ${fontSize}px monospace`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = isSelected ? '#ffffff' : isHovered ? '#00f2fe' : '#94a3b8';
            ctx.fillText(label, node.x, node.y + size + 7 + fontSize);
          }

          ctx.restore();
        }}
      />
      {hoveredNode && (
        <NodeTooltip node={hoveredNode} x={tooltipPos.x} y={tooltipPos.y} />
      )}

      {/* Floating Controls Panel */}
      <div 
        style={{ position: 'absolute', top: '16px', right: '16px', zIndex: 40 }}
        className="bg-zinc-900/90 border border-zinc-800/80 backdrop-blur-md p-4 rounded-xl shadow-[0_10px_30px_rgba(0,0,0,0.5)] text-zinc-100 font-sans text-xs w-60 space-y-3 select-none text-left"
      >
        <div className="flex justify-between items-center pb-2 border-b border-zinc-850">
          <span className="font-extrabold text-[10px] tracking-wider uppercase text-cyan-400">Graph Settings</span>
          <span className="text-[9px] text-zinc-500 font-mono">v1.2</span>
        </div>

        {/* Grouping Selectors */}
        <div className="space-y-1">
          <span className="text-zinc-400 font-medium block text-[9px] uppercase tracking-wider">Group Clustered By:</span>
          <div className="flex bg-zinc-950 p-0.5 rounded-lg border border-zinc-850">
            <button 
              onClick={() => setShowFolders(false)}
              className={`flex-1 py-1 rounded-md text-[9px] font-extrabold transition-all text-center ${!showFolders ? 'bg-cyan-500 text-black shadow' : 'text-zinc-400 hover:text-zinc-200'}`}
            >
              Departments
            </button>
            <button 
              onClick={() => setShowFolders(true)}
              className={`flex-1 py-1 rounded-md text-[9px] font-extrabold transition-all text-center ${showFolders ? 'bg-cyan-500 text-black shadow' : 'text-zinc-400 hover:text-zinc-200'}`}
            >
              Folders
            </button>
          </div>
        </div>

        {/* Link Springs Strength Slider */}
        <div className="space-y-1">
          <div className="flex justify-between text-zinc-400 text-[10px]">
            <span>Link Springs:</span>
            <span className="font-mono text-cyan-400 font-bold">{linkStrength.toFixed(1)}x</span>
          </div>
          <input 
            type="range" 
            min="0.1" 
            max="3.0" 
            step="0.1" 
            value={linkStrength}
            onChange={(e) => setLinkStrength(parseFloat(e.target.value))}
            className="w-full accent-cyan-400 h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer"
          />
        </div>

        {/* Circle / Hex Node Size Slider */}
        <div className="space-y-1">
          <div className="flex justify-between text-zinc-400 text-[10px]">
            <span>Node Radius:</span>
            <span className="font-mono text-cyan-400 font-bold">{nodeSize.toFixed(1)}x</span>
          </div>
          <input 
            type="range" 
            min="0.2" 
            max="4.0" 
            step="0.1" 
            value={nodeSize}
            onChange={(e) => setNodeSize(parseFloat(e.target.value))}
            className="w-full accent-cyan-400 h-1 bg-zinc-800 rounded-lg appearance-none cursor-pointer"
          />
        </div>

        {/* File name toggle checkbox */}
        <label className="flex items-center justify-between cursor-pointer py-1 text-[10px]">
          <span className="text-zinc-400">Show File Names</span>
          <input 
            type="checkbox" 
            checked={labelVisibility}
            onChange={(e) => setLabelVisibility(e.target.checked)}
            className="rounded bg-zinc-950 border-zinc-800 text-cyan-400 focus:ring-cyan-500/25 h-3.5 w-3.5"
          />
        </label>

        {/* Cluster Collapse/Expand Buttons */}
        <div className="flex gap-2 pt-1">
          <button 
            onClick={expandAllClusters}
            className="flex-1 bg-zinc-805 hover:bg-zinc-700 text-zinc-200 border border-zinc-800 py-1.5 rounded-lg text-[9px] font-extrabold uppercase tracking-wider transition-all text-center"
          >
            Expand All
          </button>
          <button 
            onClick={collapseAllClusters}
            className="flex-1 bg-zinc-805 hover:bg-zinc-700 text-zinc-200 border border-zinc-800 py-1.5 rounded-lg text-[9px] font-extrabold uppercase tracking-wider transition-all text-center"
          >
            Collapse All
          </button>
        </div>

        {/* Freeze/Bake Settings Button */}
        <button 
          onClick={bakeSettings}
          className="w-full bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/20 py-2 rounded-lg text-[10px] font-extrabold uppercase tracking-wider transition-all text-center"
        >
          🔒 Bake positions
        </button>
      </div>
    </div>
  );
};
export default GraphCanvas;
