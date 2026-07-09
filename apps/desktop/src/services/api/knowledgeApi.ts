import { apiFetch } from './api';
import { API_BASE_URL } from '../../config/api';

const BASE_URL = API_BASE_URL;

export interface IndexRequest {
  path: string;
}

export interface IndexResponse {
  success: boolean;
  indexed_documents_count: number;
  message?: string;
}

export interface SearchRequest {
  query: string;
  limit?: number;
}

export interface SearchResponse {
  success: boolean;
  results: {
    document_id: string;
    content: string;
    score: number;
    metadata?: Record<string, any>;
  }[];
}

export interface AtlasGraphResponse {
  nodes: any[];
  links: any[];
}

export interface AtlasTriggerResponse {
  status: string;
  message: string;
}

export interface AtlasHealthResponse {
  node_count: number;
  edge_count: number;
  active_snapshot_id: string | null;
  last_indexing_duration: number;
  cache_status: string;
  recent_errors: any[];
}

export const knowledgeApi = {
  index: (req: IndexRequest) => 
    apiFetch<IndexResponse>(`${BASE_URL}/knowledge/index`, {
      method: 'POST',
      body: JSON.stringify(req),
    }),
    
  search: (req: SearchRequest) => 
    apiFetch<SearchResponse>(`${BASE_URL}/knowledge/search`, {
      method: 'POST',
      body: JSON.stringify(req),
    }),

  // ATLAS Live Engine Connectors
  getGraph: (provider: string, snapshotId?: string) => {
    const url = snapshotId 
      ? `${BASE_URL}/atlas/graph?provider=${provider}&snapshot_id=${snapshotId}`
      : `${BASE_URL}/atlas/graph?provider=${provider}`;
    return apiFetch<AtlasGraphResponse>(url, {
      method: 'GET'
    });
  },

  triggerIndex: () =>
    apiFetch<AtlasTriggerResponse>(`${BASE_URL}/atlas/index/trigger`, {
      method: 'POST'
    }),

  cancelIndex: () =>
    apiFetch<AtlasTriggerResponse>(`${BASE_URL}/atlas/index/cancel`, {
      method: 'POST'
    }),

  getHealth: () =>
    apiFetch<AtlasHealthResponse>(`${BASE_URL}/atlas/health`, {
      method: 'GET'
    }),

  getSnapshots: () =>
    apiFetch<any[]>(`${BASE_URL}/atlas/snapshots`, {
      method: 'GET'
    })
};
