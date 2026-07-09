import type { GraphNode, GraphLink } from '../types';

export interface NodeAnalytics {
  degreeCentrality: {
    in: number;
    out: number;
    total: number;
  };
  inCycle: boolean;
  sccId: number | null;
  componentId: number;
  isOrphan: boolean;
  isBridge: boolean;
  isHotspot: boolean;
  dependencyDepth: number;
}

export class GraphAnalytics {
  /**
   * Computes comprehensive graph intelligence analytics for the active nodes and edges.
   */
  public static compute(
    nodes: GraphNode[],
    links: GraphLink[]
  ): {
    nodeMetrics: Record<string, NodeAnalytics>;
    cyclesCount: number;
    componentsCount: number;
    sccsCount: number;
    orphansCount: number;
  } {
    const nodeMetrics: Record<string, NodeAnalytics> = {};
    const nodeIds = new Set(nodes.map((n) => n.id));

    // Initialize metrics
    nodes.forEach((n) => {
      nodeMetrics[n.id] = {
        degreeCentrality: { in: 0, out: 0, total: 0 },
        inCycle: false,
        sccId: null,
        componentId: 0,
        isOrphan: true,
        isBridge: false,
        isHotspot: false,
        dependencyDepth: 0
      };
    });

    // 1. Degree Centrality
    links.forEach((l) => {
      const srcId = typeof l.source === 'string' ? l.source : (l.source as any).id;
      const tgtId = typeof l.target === 'string' ? l.target : (l.target as any).id;

      if (nodeIds.has(srcId) && nodeIds.has(tgtId)) {
        if (nodeMetrics[srcId]) {
          nodeMetrics[srcId].degreeCentrality.out += 1;
          nodeMetrics[srcId].degreeCentrality.total += 1;
          nodeMetrics[srcId].isOrphan = false;
        }
        if (nodeMetrics[tgtId]) {
          nodeMetrics[tgtId].degreeCentrality.in += 1;
          nodeMetrics[tgtId].degreeCentrality.total += 1;
          nodeMetrics[tgtId].isOrphan = false;
        }
      }
    });

    // Classify hotspots
    nodes.forEach((n) => {
      const metric = nodeMetrics[n.id];
      if (metric) {
        metric.isHotspot = metric.degreeCentrality.total >= 10;
      }
    });

    // Build Adjacency list
    const adj: Record<string, string[]> = {};
    const revAdj: Record<string, string[]> = {};
    const undirectedAdj: Record<string, string[]> = {};

    nodes.forEach((n) => {
      adj[n.id] = [];
      revAdj[n.id] = [];
      undirectedAdj[n.id] = [];
    });

    links.forEach((l) => {
      const src = typeof l.source === 'string' ? l.source : (l.source as any).id;
      const tgt = typeof l.target === 'string' ? l.target : (l.target as any).id;

      if (nodeIds.has(src) && nodeIds.has(tgt)) {
        adj[src].push(tgt);
        revAdj[tgt].push(src);
        undirectedAdj[src].push(tgt);
        undirectedAdj[tgt].push(src);
      }
    });

    // 2. Strongly Connected Components (SCC) using Tarjan's Algorithm
    let index = 0;
    const indices: Record<string, number> = {};
    const lowlink: Record<string, number> = {};
    const onStack: Record<string, boolean> = {};
    const stack: string[] = [];
    let sccCounter = 0;

    function strongConnect(u: string) {
      indices[u] = index;
      lowlink[u] = index;
      index++;
      stack.push(u);
      onStack[u] = true;

      const neighbors = adj[u] || [];
      neighbors.forEach((v) => {
        if (indices[v] === undefined) {
          strongConnect(v);
          lowlink[u] = Math.min(lowlink[u], lowlink[v]);
        } else if (onStack[v]) {
          lowlink[u] = Math.min(lowlink[u], indices[v]);
        }
      });

      if (lowlink[u] === indices[u]) {
        sccCounter++;
        const sccNodes: string[] = [];
        let w: string;
        do {
          w = stack.pop()!;
          onStack[w] = false;
          sccNodes.push(w);
          if (nodeMetrics[w]) {
            nodeMetrics[w].sccId = sccCounter;
          }
        } while (w !== u);

        // Mark cycle loops if SCC has multiple nodes or a self-loop
        if (sccNodes.length > 1 || (sccNodes.length === 1 && (adj[u] || []).includes(u))) {
          sccNodes.forEach((node) => {
            if (nodeMetrics[node]) {
              nodeMetrics[node].inCycle = true;
            }
          });
        }
      }
    }

    nodes.forEach((n) => {
      if (indices[n.id] === undefined) {
        strongConnect(n.id);
      }
    });

    // 3. Weakly Connected Components (BFS on Undirected edges)
    const visitedComponents = new Set<string>();
    let componentCounter = 0;

    nodes.forEach((n) => {
      if (!visitedComponents.has(n.id)) {
        componentCounter++;
        const queue = [n.id];
        visitedComponents.add(n.id);

        while (queue.length > 0) {
          const curr = queue.shift()!;
          if (nodeMetrics[curr]) {
            nodeMetrics[curr].componentId = componentCounter;
          }

          const neighbors = undirectedAdj[curr] || [];
          neighbors.forEach((neigh) => {
            if (!visitedComponents.has(neigh)) {
              visitedComponents.add(neigh);
              queue.push(neigh);
            }
          });
        }
      }
    });

    // 4. Dependency Depth (Max outgoing depth of each node via BFS/DFS memoization)
    const depthCache: Record<string, number> = {};
    function calculateDepth(u: string, visited: Set<string>): number {
      if (depthCache[u] !== undefined) return depthCache[u];
      if (visited.has(u)) return 0; // Avoid circular deadlock loops

      visited.add(u);
      let maxSubDepth = 0;
      const neighbors = adj[u] || [];
      neighbors.forEach((v) => {
        maxSubDepth = Math.max(maxSubDepth, calculateDepth(v, visited));
      });
      visited.delete(u);

      depthCache[u] = 1 + maxSubDepth;
      return depthCache[u];
    }

    nodes.forEach((n) => {
      nodeMetrics[n.id].dependencyDepth = calculateDepth(n.id, new Set()) - 1;
    });

    // 5. Bridge Nodes Detection (Tarjan's articulation points / cut vertices logic on undirected graph)
    let bIndex = 0;
    const bIndices: Record<string, number> = {};
    const bLowlink: Record<string, number> = {};
    const articulationPoints = new Set<string>();

    function findBridges(u: string, p: string | null = null) {
      bIndices[u] = bIndex;
      bLowlink[u] = bIndex;
      bIndex++;
      let childrenCount = 0;
      const neighbors = undirectedAdj[u] || [];

      neighbors.forEach((v) => {
        if (v === p) return;
        if (bIndices[v] !== undefined) {
          bLowlink[u] = Math.min(bLowlink[u], bIndices[v]);
        } else {
          childrenCount++;
          findBridges(v, u);
          bLowlink[u] = Math.min(bLowlink[u], bLowlink[v]);
          
          if (p !== null && bLowlink[v] >= bIndices[u]) {
            articulationPoints.add(u);
          }
        }
      });

      if (p === null && childrenCount > 1) {
        articulationPoints.add(u);
      }
    }

    nodes.forEach((n) => {
      if (bIndices[n.id] === undefined) {
        findBridges(n.id);
      }
    });

    articulationPoints.forEach((node) => {
      if (nodeMetrics[node]) {
        nodeMetrics[node].isBridge = true;
      }
    });

    // Totals counters
    let orphansCount = 0;
    let cyclesCount = 0;
    nodes.forEach((n) => {
      if (nodeMetrics[n.id].isOrphan) orphansCount++;
      if (nodeMetrics[n.id].inCycle) cyclesCount++;
    });

    return {
      nodeMetrics,
      cyclesCount: Math.round(cyclesCount / 2), // estimate cycles grouping count
      componentsCount: componentCounter,
      sccsCount: sccCounter,
      orphansCount
    };
  }

  /**
   * BFS helper to calculate the shortest path sequence from start to end node.
   */
  public static findShortestPath(
    nodes: GraphNode[],
    links: GraphLink[],
    startId: string,
    endId: string
  ): string[] | null {
    if (startId === endId) return [startId];
    const nodeIds = new Set(nodes.map((n) => n.id));
    if (!nodeIds.has(startId) || !nodeIds.has(endId)) return null;

    const adj: Record<string, string[]> = {};
    nodes.forEach((n) => { adj[n.id] = []; });
    
    links.forEach((l) => {
      const src = typeof l.source === 'string' ? l.source : (l.source as any).id;
      const tgt = typeof l.target === 'string' ? l.target : (l.target as any).id;
      if (nodeIds.has(src) && nodeIds.has(tgt)) {
        adj[src].push(tgt);
      }
    });

    const queue: string[] = [startId];
    const parent: Record<string, string | null> = { [startId]: null };
    const visited = new Set<string>([startId]);

    while (queue.length > 0) {
      const curr = queue.shift()!;
      if (curr === endId) {
        const path: string[] = [];
        let step: string | null = endId;
        while (step !== null) {
          path.unshift(step);
          step = parent[step];
        }
        return path;
      }

      const neighbors = adj[curr] || [];
      neighbors.forEach((v) => {
        if (!visited.has(v)) {
          visited.add(v);
          parent[v] = curr;
          queue.push(v);
        }
      });
    }

    return null;
  }
}
