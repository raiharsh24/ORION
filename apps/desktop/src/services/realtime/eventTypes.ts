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

// ── Cognitive / Phase 10 event payloads ──
export interface CognitiveGoalEventPayload {
  goal_id: string;
  objective: string;
  status?: string;
  progress_pct?: number;
  parent_id?: string | null;
  priority?: number;
}

export interface CognitiveMilestoneEventPayload {
  goal_id: string;
  milestone_id: string;
  milestone_name: string;
  progress_pct: number;
}

export interface CognitiveSchedulerEventPayload {
  [key: string]: unknown;
}

export interface CognitiveMissionEventPayload {
  mission_id: string;
  objective: string;
  workflow_type?: string;
  agent_ids?: string[];
  strategy?: string;
}

export interface CognitiveLearningEventPayload {
  learning_type: string;
  summary: string;
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

  // Cognitive / Phase 10 events
  'cognitive.goal.created': CognitiveGoalEventPayload;
  'cognitive.goal.updated': CognitiveGoalEventPayload;
  'cognitive.goal.milestone_completed': CognitiveMilestoneEventPayload;
  'cognitive.scheduler.started': CognitiveSchedulerEventPayload;
  'cognitive.scheduler.stopped': CognitiveSchedulerEventPayload;
  'cognitive.mission.delegated': CognitiveMissionEventPayload;
  'cognitive.mission.recovered': CognitiveMissionEventPayload;
  'cognitive.learning.updated': CognitiveLearningEventPayload;
}

export type SystemEventTopic = keyof SystemEventMap;

export interface SystemEvent<T extends SystemEventTopic = SystemEventTopic> {
  topic: T;
  data: SystemEventMap[T];
  timestamp: number;
}

