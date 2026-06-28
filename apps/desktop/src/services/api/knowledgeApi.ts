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
};
