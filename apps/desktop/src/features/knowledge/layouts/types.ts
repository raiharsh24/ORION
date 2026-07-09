import type { GraphNode } from '../types';

export interface GraphLayout {
  name: string;
  apply(nodes: GraphNode[], width: number, height: number): void;
}
