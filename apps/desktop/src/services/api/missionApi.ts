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
    apiFetch<StatusToggleResponse>(`${BASE_URL}/missions/start?mission_id=${id}`, { method: 'POST' }),
    
  pauseMission: (id: string) => 
    apiFetch<StatusToggleResponse>(`${BASE_URL}/missions/pause?mission_id=${id}`, { method: 'POST' }),
    
  resumeMission: (id: string) => 
    apiFetch<StatusToggleResponse>(`${BASE_URL}/missions/resume?mission_id=${id}`, { method: 'POST' }),
    
  cancelMission: (id: string) => 
    apiFetch<StatusToggleResponse>(`${BASE_URL}/missions/cancel?mission_id=${id}`, { method: 'POST' }),
    
  confirmMissionAction: (id: string, approved: boolean) =>
    apiFetch<{ success: boolean }>(`${BASE_URL}/missions/${id}/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved })
    }),
};
