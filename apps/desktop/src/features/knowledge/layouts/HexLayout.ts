import type { GraphNode } from '../types';
import type { GraphLayout } from './types';

export class HexLayout implements GraphLayout {
  name = 'Hex';

  apply(nodes: GraphNode[], width: number, height: number): void {
    const cx = width / 2;
    const cy = height / 2;
    const size = 45; // Spacing/radius of hex cells

    nodes.forEach((node) => {
      // Find current position relative to center
      const px = (node.x ?? cx) - cx;
      const py = (node.y ?? cy) - cy;

      // Axial hex coordinates math
      const q = (2 / 3 * px) / size;
      const r = (-1 / 3 * px + Math.sqrt(3) / 3 * py) / size;

      // Round to nearest hex cell
      let qi = Math.round(q);
      let ri = Math.round(r);
      let si = Math.round(-q - r);

      const q_diff = Math.abs(qi - q);
      const r_diff = Math.abs(ri - r);
      const s_diff = Math.abs(si - (-q - r));

      if (q_diff > r_diff && q_diff > s_diff) {
        qi = -ri - si;
      } else if (r_diff > s_diff) {
        ri = -qi - si;
      }

      // Convert rounded axial coordinates back to Cartesian
      const rx = size * (3 / 2 * qi);
      const ry = size * ((Math.sqrt(3) / 2) * qi + Math.sqrt(3) * ri);

      node.fx = cx + rx;
      node.fy = cy + ry;
    });
  }
}
