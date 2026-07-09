import { apiFetch } from './api';
import type { Mission } from '../../pages/MissionCenter/types';
import { API_BASE_URL } from '../../config/api';

const BASE_URL = API_BASE_URL;

export interface StatusToggleResponse {
  success: boolean;
  mission_id: string;
  status: string;
}

export const missionApi = {
  getMissions: () => 
    apiFetch<Mission[]>(`${BASE_URL}/missions`),
    
  getMission: (id: string) => 
    apiFetch<Mission>(`${BASE_URL}/missions/${id}`),
    
  startMission: (id: string) => 
    apiFetch<StatusToggleResponse>(`${BASE_URL}/missions/${id}/start`, { method: 'POST' }),
    
  pauseMission: (id: string) => 
    apiFetch<StatusToggleResponse>(`${BASE_URL}/missions/${id}/pause`, { method: 'POST' }),
    
  resumeMission: (id: string) => 
    apiFetch<StatusToggleResponse>(`${BASE_URL}/missions/${id}/resume`, { method: 'POST' }),
    
  cancelMission: (id: string) => 
    apiFetch<StatusToggleResponse>(`${BASE_URL}/missions/${id}/cancel`, { method: 'POST' }),
    
  confirmMissionAction: (id: string, approved: boolean) =>
    apiFetch<{ success: boolean }>(`${BASE_URL}/missions/${id}/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved })
    }),
};
