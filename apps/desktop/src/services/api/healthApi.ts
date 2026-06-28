import { apiFetch } from './api';
import { API_BASE_URL } from '../../config/api';

const BASE_URL = API_BASE_URL;

export interface HealthServiceResponse {
  name: string;
  status: string;
  message?: string;
}

export interface HealthResponse {
  status: string;
  assistant: string;
  version: string;
  services?: HealthServiceResponse[];
}

export const healthApi = {
  getHealth: () => 
    apiFetch<HealthResponse>(`${BASE_URL}/health`),
};
