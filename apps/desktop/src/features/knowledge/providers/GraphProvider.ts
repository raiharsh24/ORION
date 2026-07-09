import type { GraphData, ProviderType } from '../types';

export interface GraphProvider {
  type: ProviderType;
  name: string;
  fetchGraphData(): Promise<GraphData>;
}
