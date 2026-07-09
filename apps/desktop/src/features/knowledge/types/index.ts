export type NodeStatus = 'HEALTHY' | 'WARNING' | 'ERROR' | 'OFFLINE' | 'DEPRECATED' | 'EXPERIMENTAL' | 'BROKEN' | 'DISCONNECTED';

export type ProviderType = 
  | 'knowledge' 
  | 'memory' 
  | 'code' 
  | 'workflow' 
  | 'agent' 
  | 'document' 
  | 'research' 
  | 'timeline';

export type LayoutMode = 
  | 'force' 
  | 'circle' 
  | 'rings' 
  | 'hex' 
  | 'timeline' 
  | 'architecture';

export interface GraphNode {
  id: string;
  title: string;
  description: string;
  type: string;        // e.g. 'manifest', 'skill', 'memory', 'routine', 'application', 'code', 'workflow', 'agent', 'project', 'research', 'document'
  category: string;    // Department cluster e.g. 'Personal', 'Business', 'Product', 'Development', 'Research', 'Community', 'Content', 'Memory', 'Documents'
  tags: string[];
  metadata: Record<string, any>;
  createdAt: string;
  updatedAt: string;
  importance: number;  // Visual node size / scaling weight (0.0 to 1.0)
  status: NodeStatus;
  color?: string;
  icon?: string;
  parent?: string;
  children?: string[];

  // D3 force coordinate properties
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
}

export interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  label: string;
  value?: number;
  color?: string;
  width?: number;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}
