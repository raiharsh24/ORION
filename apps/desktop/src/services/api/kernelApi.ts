import { apiFetch } from './api';
import { API_BASE_URL } from '../../config/api';

const BASE_URL = API_BASE_URL;

export interface KernelStatus {
  kernel_state: string;
  boot_time_ms: number;
  registered_services_count: number;
  uptime: string;
  cpu_utilization: number;
  memory_usage_bytes: number;
  health: {
    kernel_status: string;
    checked_at: string;
  };
}

export const kernelApi = {
  getKernelStatus: () => 
    apiFetch<KernelStatus>(`${BASE_URL}/kernel`),
};
