import type { Mission } from '../../pages/MissionCenter/types';

export interface TelemetryUpdatedPayload {
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

export interface KernelHealthChangedPayload {
  kernel_state: 'BOOTING' | 'INITIALIZING' | 'READY' | 'BUSY' | 'SHUTTING_DOWN' | 'STOPPED' | 'ERROR';
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

export interface ServiceStatusChangedPayload {
  status: string;
  assistant: string;
  version: string;
  services: {
    name: string;
    status: 'HEALTHY' | 'WARNING' | 'ERROR' | 'OFFLINE';
    message?: string;
  }[];
}

export interface SystemEventMap {
  MissionStarted: Mission;
  MissionUpdated: Mission;
  MissionCompleted: Mission;
  MissionFailed: Mission & { error: string };
  MissionCancelled: Mission;
  TelemetryUpdated: TelemetryUpdatedPayload;
  KernelHealthChanged: KernelHealthChangedPayload;
  ServiceStatusChanged: ServiceStatusChangedPayload;
}

export type SystemEventTopic = keyof SystemEventMap;

export interface SystemEvent<T extends SystemEventTopic = SystemEventTopic> {
  topic: T;
  data: SystemEventMap[T];
  timestamp: number;
}
