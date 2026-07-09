import type { GraphNode } from '../types';
import type { GraphLayout } from './types';

export class TimelineLayout implements GraphLayout {
  name = 'Timeline';

  apply(nodes: GraphNode[], width: number, height: number): void {
    const startX = width * 0.1;
    const endX = width * 0.9;
    const cy = height / 2;

    // Sort nodes by creation date
    const sorted = [...nodes].sort(
      (a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
    );

    const count = sorted.length;
    sorted.forEach((node, idx) => {
      // Distribute evenly along the X timeline baseline
      const progress = count > 1 ? idx / (count - 1) : 0.5;
      const x = startX + progress * (endX - startX);

      // Distribute vertically along Y bands by category hash and node weight
      const categoryHash = node.category.split('').reduce((acc: number, char: string) => acc + char.charCodeAt(0), 0);
      const verticalSpread = 160;
      const yOffset = Math.sin(categoryHash + idx) * verticalSpread * (1.1 - node.importance);

      node.fx = x;
      node.fy = cy + yOffset;
    });
  }
}
