/**
 * Workflow Engine REST API client.
 * Mirrors the /workflows routes exposed by the FastAPI backend.
 */

import { API_BASE_URL } from '../../config/api';

const BASE_URL = API_BASE_URL;

export interface WorkflowNodeRequest {
  id: string;
  name: string;
  type: string;
  flow_type?: string;
  depends_on?: string[];
  on_success?: string;
  on_failure?: string;
  inputs?: Record<string, any>;
  max_retries?: number;
  delay_seconds?: number;
  loop_max?: number;
  metadata?: Record<string, any>;
}

export interface CreateWorkflowRequest {
  name: string;
  description?: string;
  flow_type?: string;
  template_id?: string;
  tags?: string[];
  timeout_seconds?: number;
  max_retries?: number;
  nodes?: WorkflowNodeRequest[];
  variables?: Record<string, any>;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options?.headers },
  });
  if (!response.ok) {
    const error = await response.text().catch(() => response.statusText);
    throw new Error(`Workflow API error ${response.status}: ${error}`);
  }
  return response.json() as Promise<T>;
}

export const workflowApi = {
  /** List all registered workflows */
  getWorkflows: () =>
    request<any[]>('/workflows'),

  /** Get a single workflow by ID */
  getWorkflow: (id: string) =>
    request<any>(`/workflows/${id}`),

  /** Create a new workflow (from nodes or template) */
  createWorkflow: (body: CreateWorkflowRequest) =>
    request<any>('/workflows', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** Start a workflow execution */
  startWorkflow: (id: string) =>
    request<{ success: boolean; run_id?: string; message: string }>(`/workflows/${id}/start`, {
      method: 'POST',
    }),

  /** Pause a running workflow */
  pauseWorkflow: (id: string) =>
    request<{ success: boolean; message: string }>(`/workflows/${id}/pause`, {
      method: 'POST',
    }),

  /** Resume a paused workflow */
  resumeWorkflow: (id: string) =>
    request<{ success: boolean; message: string }>(`/workflows/${id}/resume`, {
      method: 'POST',
    }),

  /** Cancel an active workflow */
  cancelWorkflow: (id: string) =>
    request<{ success: boolean; message: string }>(`/workflows/${id}/cancel`, {
      method: 'POST',
    }),

  /** Cancel and restart a workflow */
  restartWorkflow: (id: string) =>
    request<{ success: boolean; run_id?: string; message: string }>(`/workflows/${id}/restart`, {
      method: 'POST',
    }),

  /** Retry a specific failed node */
  retryNode: (workflowId: string, nodeId: string) =>
    request<{ success: boolean; message: string }>(`/workflows/${workflowId}/retry/${nodeId}`, {
      method: 'POST',
    }),

  /** Get execution history for a workflow */
  getHistory: (id: string) =>
    request<any[]>(`/workflows/${id}/history`),

  /** List built-in templates */
  getTemplates: () =>
    request<any[]>('/workflows/templates'),

  /** Get all currently active workflows */
  getActiveWorkflows: () =>
    request<any[]>('/workflows/active'),
};
