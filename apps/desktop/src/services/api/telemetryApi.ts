import { apiFetch } from './api';
import { API_BASE_URL } from '../../config/api';

const BASE_URL = API_BASE_URL;

export interface TelemetryResponse {
  latency: number;
  fps: number;
  memory: number;
  executionTimeMs: number;
  eventsCount: number;
  currentTool: string;
  workflow: string;
  missionId: string;
  current_desktop_task: string;
  last_executed_action: string;
  average_execution_time_ms: number;
  failure_count: number;
  queue_length: number;
}

export const telemetryApi = {
  getTelemetry: () => 
    apiFetch<TelemetryResponse>(`${BASE_URL}/telemetry`),
};
