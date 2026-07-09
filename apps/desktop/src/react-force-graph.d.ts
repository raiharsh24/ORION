declare module 'react-force-graph-2d' {
  import { ComponentType } from 'react';

  export interface ForceGraphProps {
    graphData?: {
      nodes: any[];
      links: any[];
    };
    width?: number;
    height?: number;
    nodeId?: string;
    nodeLabel?: string | ((node: any) => string);
    nodeVal?: number | string | ((node: any) => number);
    nodeColor?: string | ((node: any) => string);
    nodeAutoColorBy?: string | ((node: any) => string);
    nodeCanvasObject?: (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => void;
    nodeCanvasObjectMode?: string | ((node: any) => 'replace' | 'before' | 'after');
    linkLabel?: string | ((link: any) => string);
    linkVisibility?: boolean | string | ((link: any) => boolean);
    linkColor?: string | ((link: any) => string);
    linkWidth?: number | string | ((link: any) => number);
    linkDirectionalArrowLength?: number | string | ((link: any) => number);
    linkDirectionalArrowColor?: string | ((link: any) => string);
    linkDirectionalArrowRelPos?: number | string | ((link: any) => number);
    linkDirectionalParticles?: number | string | ((link: any) => number);
    linkDirectionalParticleSpeed?: number | string | ((link: any) => number);
    linkDirectionalParticleWidth?: number | string | ((link: any) => number);
    linkDirectionalParticleColor?: string | ((link: any) => string);
    onNodeClick?: (node: any, event: MouseEvent) => void;
    onNodeRightClick?: (node: any, event: MouseEvent) => void;
    onNodeHover?: (node: any, prevNode: any) => void;
    onNodeDrag?: (node: any, translate: { x: number; y: number }) => void;
    onNodeDragEnd?: (node: any, translate: { x: number; y: number }) => void;
    onLinkClick?: (link: any, event: MouseEvent) => void;
    onLinkHover?: (link: any, prevLink: any) => void;
    onBackgroundClick?: (event: MouseEvent) => void;
    enableNodeDrag?: boolean;
    enableNavigationControls?: boolean;
    showNavInfo?: boolean;
    enableZoomInteraction?: boolean;
    enablePanInteraction?: boolean;
    cooldownTicks?: number;
    cooldownTime?: number;
    onEngineTick?: () => void;
    onEngineStop?: () => void;
    ref?: any;
    [key: string]: any;
  }

  const ForceGraph2D: ComponentType<ForceGraphProps>;
  export default ForceGraph2D;
}
