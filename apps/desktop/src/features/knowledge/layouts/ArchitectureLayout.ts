import type { GraphNode } from '../types';
import type { GraphLayout } from './types';

export class ArchitectureLayout implements GraphLayout {
  name = 'Architecture';

  apply(nodes: GraphNode[], width: number, height: number): void {
    const cx = width / 2;
    
    // Define 5 tier layers
    const tiers: Record<number, GraphNode[]> = {
      0: [], // UI Client / Apps
      1: [], // Gateway Proxy / Docs
      2: [], // Core Kernel / Agents
      3: [], // Memory / Workflow logics
      4: []  // DB / Storage
    };

    nodes.forEach((node) => {
      if (node.id === 'ui' || node.type === 'application') {
        tiers[0].push(node);
      } else if (node.id === 'gateway' || node.type === 'document') {
        tiers[1].push(node);
      } else if (node.id === 'kernel' || node.type === 'agent' || node.id === 'friday') {
        tiers[2].push(node);
      } else if (node.type === 'memory' || node.type === 'workflow' || node.type === 'skill' || node.type === 'research') {
        tiers[3].push(node);
      } else {
        tiers[4].push(node);
      }
    });

    const tierCount = 5;
    const tierStepY = height / (tierCount + 1);

    for (let tier = 0; tier < tierCount; tier++) {
      const tierNodes = tiers[tier];
      const count = tierNodes.length;
      const y = (tier + 1) * tierStepY;

      tierNodes.forEach((node, idx) => {
        // Distribute horizontally centered
        const progress = count > 1 ? idx / (count - 1) : 0.5;
        const x = cx + (progress - 0.5) * (width * 0.85);

        // Add subtle coordinate noise
        const noise = (Math.random() - 0.5) * 4;

        node.fx = x + noise;
        node.fy = y;
      });
    }
  }
}
