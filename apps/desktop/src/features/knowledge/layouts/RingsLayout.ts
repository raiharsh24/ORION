import type { GraphNode } from '../types';
import type { GraphLayout } from './types';

export class RingsLayout implements GraphLayout {
  name = 'Rings';

  apply(nodes: GraphNode[], width: number, height: number, links: any[] = []): void {
    const cx = width / 2;
    const cy = height / 2;

    // 1. Find the central hub node ('friday' or highest connection degree)
    let hub = nodes.find(n => n.id === 'friday');
    if (!hub) {
      const degrees: Record<string, number> = {};
      nodes.forEach(n => { degrees[n.id] = 0; });
      links.forEach(l => {
        const s = typeof l.source === 'string' ? l.source : l.source.id;
        const t = typeof l.target === 'string' ? l.target : l.target.id;
        if (degrees[s] !== undefined) degrees[s]++;
        if (degrees[t] !== undefined) degrees[t]++;
      });
      let maxDeg = -1;
      nodes.forEach(n => {
        if (degrees[n.id] > maxDeg) {
          maxDeg = degrees[n.id];
          hub = n;
        }
      });
    }

    if (!hub) {
      hub = nodes[0];
    }

    if (!hub) return;

    // 2. Build adjacency mapping for BFS
    const adj: Record<string, string[]> = {};
    nodes.forEach(n => { adj[n.id] = []; });
    links.forEach(l => {
      const s = typeof l.source === 'string' ? l.source : l.source.id;
      const t = typeof l.target === 'string' ? l.target : l.target.id;
      if (adj[s]) adj[s].push(t);
      if (adj[t]) adj[t].push(s);
    });

    // 3. BFS traversal to compute topological depth from central hub
    const depth: Record<string, number> = {};
    const visited = new Set<string>();
    const queue: [string, number][] = [[hub.id, 0]];
    visited.add(hub.id);

    while (queue.length > 0) {
      const [curr, d] = queue.shift()!;
      depth[curr] = d;
      for (const neighbor of adj[curr] || []) {
        if (!visited.has(neighbor)) {
          visited.add(neighbor);
          queue.push([neighbor, d + 1]);
        }
      }
    }

    // Default depth ring for unvisited/island nodes
    nodes.forEach(n => {
      if (depth[n.id] === undefined) {
        depth[n.id] = 4;
      }
    });

    // Group nodes by depth level
    const ringGroups: Record<number, GraphNode[]> = {};
    nodes.forEach(n => {
      const d = depth[n.id];
      if (!ringGroups[d]) ringGroups[d] = [];
      ringGroups[d].push(n);
    });

    const maxDepth = Math.max(...Object.keys(ringGroups).map(Number), 1);
    const maxRadius = Math.min(width, height) * 0.45;
    const ringSpacing = maxRadius / Math.max(maxDepth, 4);

    // Position each group on its concentric ring
    Object.keys(ringGroups).forEach(dStr => {
      const d = parseInt(dStr, 10);
      const ringList = ringGroups[d];
      const count = ringList.length;

      if (d === 0) {
        ringList.forEach(node => {
          node.fx = cx;
          node.fy = cy;
        });
        return;
      }

      const radius = d * ringSpacing;
      ringList.forEach((node, idx) => {
        const angle = (2 * Math.PI * idx) / count + (d * 0.2);
        node.fx = cx + radius * Math.cos(angle);
        node.fy = cy + radius * Math.sin(angle);
      });
    });
  }
}
