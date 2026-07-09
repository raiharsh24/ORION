import type { GraphNode } from '../types';
import type { GraphLayout } from './types';

export class ForceLayout implements GraphLayout {
  name = 'Force';

  apply(nodes: GraphNode[]): void {
    nodes.forEach((node) => {
      node.fx = null;
      node.fy = null;
    });
  }
}
