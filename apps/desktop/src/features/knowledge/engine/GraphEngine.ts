import type { GraphNode, LayoutMode } from '../types';
import { ForceLayout } from '../layouts/ForceLayout';
import { CircleLayout } from '../layouts/CircleLayout';
import { RingsLayout } from '../layouts/RingsLayout';
import { HexLayout } from '../layouts/HexLayout';
import { TimelineLayout } from '../layouts/TimelineLayout';
import { ArchitectureLayout } from '../layouts/ArchitectureLayout';
import type { GraphLayout } from '../layouts/types';

export class GraphEngine {
  private static layouts: Record<LayoutMode, GraphLayout> = {
    force: new ForceLayout(),
    circle: new CircleLayout(),
    rings: new RingsLayout(),
    hex: new HexLayout(),
    timeline: new TimelineLayout(),
    architecture: new ArchitectureLayout()
  };

  /**
   * Applies layout mathematics to set fixed fx/fy targets on nodes.
   */
  public static applyLayout(
    nodes: GraphNode[],
    mode: LayoutMode,
    width: number,
    height: number,
    links: any[] = [],
    showFolders: boolean = false
  ): void {
    const layout = this.layouts[mode] || this.layouts.force;
    if (mode === 'rings') {
      (layout as any).apply(nodes, width, height, links);
    } else if (mode === 'circle') {
      (layout as any).apply(nodes, width, height, showFolders);
    } else {
      layout.apply(nodes, width, height);
    }
  }

  /**
   * Fuzzy matches nodes based on text query across title, description, tags, and category.
   */
  public static search(nodes: GraphNode[], query: string): GraphNode[] {
    if (!query.trim()) return [];
    
    const q = query.toLowerCase().trim();
    return nodes.filter((node) => {
      const matchTitle = node.title.toLowerCase().includes(q);
      const matchDesc = node.description.toLowerCase().includes(q);
      const matchCat = node.category.toLowerCase().includes(q);
      const matchTags = node.tags.some((tag) => tag.toLowerCase().includes(q));

      // Match path and properties in metadata
      const meta = node.metadata || {};
      const matchPath = meta.path && String(meta.path).toLowerCase().includes(q);
      const matchLang = meta.language && String(meta.language).toLowerCase().includes(q);
      const matchInherits = meta.inherits && Array.isArray(meta.inherits) && meta.inherits.some(i => String(i).toLowerCase().includes(q));
      const matchImplements = meta.implements && Array.isArray(meta.implements) && meta.implements.some(i => String(i).toLowerCase().includes(q));

      return matchTitle || matchDesc || matchCat || matchTags || matchPath || matchLang || matchInherits || matchImplements;
    });
  }

  /**
   * Evaluates Level-Of-Detail culling bounds.
   * Returns nodes that should be actively drawn, and determines if labels should render.
   */
  public static evaluateCulling(
    nodes: GraphNode[],
    scale: number,
    viewport: { xMin: number; xMax: number; yMin: number; yMax: number }
  ): { visibleNodes: GraphNode[]; drawLabels: boolean } {
    
    // Frustum culling margin
    const margin = 100;
    
    // Frustum culling filter
    const visibleInViewport = nodes.filter((node) => {
      const x = node.x ?? 0;
      const y = node.y ?? 0;
      return (
        x >= viewport.xMin - margin &&
        x <= viewport.xMax + margin &&
        y >= viewport.yMin - margin &&
        y <= viewport.yMax + margin
      );
    });

    // Level-Of-Detail culling:
    // If scale is extremely zoomed out, skip rendering low-importance nodes to protect FPS.
    let visibleNodes = visibleInViewport;
    let drawLabels = true;

    if (scale < 0.15) {
      // Zoomed way out: only draw major nodes (importance >= 0.5)
      visibleNodes = visibleInViewport.filter((n) => n.importance >= 0.5);
      drawLabels = false;
    } else if (scale < 0.5) {
      // Zoomed medium: draw all nodes, but hide names on low importance nodes
      drawLabels = false;
    }

    return { visibleNodes, drawLabels };
  }
}
