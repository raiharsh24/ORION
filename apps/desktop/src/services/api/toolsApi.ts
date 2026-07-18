import { apiFetch } from './api';
import { API_BASE_URL } from '../../config/api';

export interface ToolParameter {
  name: string;
  type: string;
  description: string;
  required: boolean;
  default: any;
  enum_values: string[] | null;
}

export interface ToolExample {
  prompt: string;
  args: Record<string, unknown>;
  description: string;
}

export interface ToolHealth {
  status: string;
  last_checked: string;
  message: string;
  error_count: number;
  success_count: number;
  average_latency_ms: number;
}

export interface ToolDependency {
  tool_id: string;
  optional: boolean;
  version_requirement: string | null;
}

export interface ToolInfo {
  id: string;
  name: string;
  description: string;
  category: string;
  version: string;
  author: string;
  tags: string[];
  permission_level: string;
  enabled: boolean;
  estimated_cost: number;
  estimated_latency_ms: number;
  supports_streaming: boolean;
  supports_cancellation: boolean;
  supports_parallel_execution: boolean;
  parameters: ToolParameter[];
  examples: ToolExample[];
  health: ToolHealth | null;
  dependencies: ToolDependency[];
}

export interface ListToolsResponse {
  count: number;
  tools: ToolInfo[];
}

const BASE_URL = `${API_BASE_URL}/tools`;

export const toolsApi = {
  listTools: (params?: { category?: string; q?: string; enabled_only?: boolean }) => {
    const query = new URLSearchParams();
    if (params?.category) query.set('category', params.category);
    if (params?.q) query.set('q', params.q);
    if (params?.enabled_only !== undefined) query.set('enabled_only', String(params.enabled_only));
    const qs = query.toString();
    return apiFetch<ListToolsResponse>(`${BASE_URL}${qs ? `?${qs}` : ''}`);
  },

  getTool: (toolId: string) =>
    apiFetch<ToolInfo>(`${BASE_URL}/${encodeURIComponent(toolId)}`),

  enableTool: (toolId: string) =>
    apiFetch<{ id: string; enabled: boolean }>(`${BASE_URL}/${encodeURIComponent(toolId)}/enable`, { method: 'POST' }),

  disableTool: (toolId: string) =>
    apiFetch<{ id: string; enabled: boolean }>(`${BASE_URL}/${encodeURIComponent(toolId)}/disable`, { method: 'POST' }),

  getCapabilities: () =>
    apiFetch<{
      total_tools: number;
      enabled_tools: number;
      disabled_tools: number;
      categories: string[];
      tool_ids: string[];
    }>(`${BASE_URL}/capabilities`),

  getHealth: () =>
    apiFetch<{
      status: string;
      registered_tools: number;
      healthy_tools: number;
      unavailable_tools: number;
    }>(`${BASE_URL}/health`),
};
