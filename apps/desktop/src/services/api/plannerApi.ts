import { apiFetch } from './api';
import { API_BASE_URL } from '../../config/api';

const BASE_URL = API_BASE_URL;

export interface AskRequest {
  prompt: string;
  confirmed?: boolean;
  confirmation_token?: string;
}

export interface AskResponse {
  success: boolean;
  intent: string;
  response: string;
  tool_used?: string;
  tool_output?: string;
  session_id: string;
  execution_time_ms: number;
  telemetry?: {
    model: string;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    error?: string;
  };
  confirmation_required?: boolean;
  confirmation_token?: string;
}

export interface ChatRequest {
  prompt: string;
  session_id?: string;
  stream?: boolean;
  confirmed?: boolean;
  confirmation_token?: string;
}

export const plannerApi = {
  ask: (req: AskRequest) => 
    apiFetch<AskResponse>(`${BASE_URL}/ask`, {
      method: 'POST',
      body: JSON.stringify(req),
    }),
    
  chat: (req: ChatRequest) => 
    apiFetch<AskResponse | Response>(`${BASE_URL}/chat`, {
      method: 'POST',
      body: JSON.stringify(req),
    }),
};
