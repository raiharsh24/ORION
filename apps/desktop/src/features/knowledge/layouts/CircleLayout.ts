import type { GraphNode } from '../types';
import type { GraphLayout } from './types';

export class CircleLayout implements GraphLayout {
  name = 'Circle';

  apply(nodes: GraphNode[], width: number, height: number, showFolders: boolean = false): void {
    const cx = width / 2;
    const cy = height / 2;
    const radius = Math.min(width, height) * 0.35;
    const count = nodes.length;

    const getFolderGroup = (node: GraphNode): string => {
      const path = node.metadata?.path || '';
      if (!path) return 'unknown';
      const parts = path.split('/');
      return parts.length <= 1 ? 'root' : parts.slice(0, -1).join('/');
    };

    // Sort nodes by grouping to cluster them adjacently on the circle
    const sortedNodes = [...nodes].sort((a, b) => {
      const groupA = showFolders ? getFolderGroup(a) : a.category;
      const groupB = showFolders ? getFolderGroup(b) : b.category;
      return (groupA || '').localeCompare(groupB || '');
    });

    sortedNodes.forEach((node, idx) => {
      const angle = (2 * Math.PI * idx) / count;
      node.fx = cx + radius * Math.cos(angle);
      node.fy = cy + radius * Math.sin(angle);
    });
  }
}
