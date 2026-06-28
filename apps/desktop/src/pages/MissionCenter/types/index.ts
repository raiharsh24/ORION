export interface LogEntry {
  time: string;
  level: 'INFO' | 'DEBUG' | 'WARN' | 'ERROR' | 'SUCCESS';
  msg: string;
}

export interface Mission {
  id: string;
  name: string;
  description: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  progress: number;
  currentStep: string;
  steps: string[];
  durationMs: number;
  startedAt?: string;
  finishedAt?: string;
  createdAt?: string;
  error?: string;
  currentTool?: string;
  workflowName?: string;
  logs?: LogEntry[];
  metadata?: any;
}

export type HealthStatus = 'HEALTHY' | 'WARNING' | 'ERROR' | 'OFFLINE';

export interface ServiceHealth {
  name: string;
  status: HealthStatus;
  message?: string;
}

export interface TelemetryData {
  executionTimeMs: number;
  eventsCount: number;
  currentTool: string;
  missionId: string;
  workflow: string;
  latency: number;
  fps: number;
  memory: number;
  current_desktop_task?: string;
  last_executed_action?: string;
  average_execution_time_ms?: number;
  failure_count?: number;
  queue_length?: number;
  // Workflow Engine telemetry
  current_workflow?: string;
  current_workflow_node?: string;
  workflow_duration_seconds?: number;
  workflow_branch_decisions?: string;
  workflow_retries?: number;
}

// ============================================================
// Workflow Engine Types
// ============================================================

export type WorkflowNodeStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'
  | 'SKIPPED'
  | 'PAUSED'
  | 'WAITING'
  | 'RETRYING';

export type WorkflowStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'PAUSED'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED';

export type WorkflowFlowType =
  | 'SEQUENTIAL'
  | 'PARALLEL'
  | 'CONDITIONAL'
  | 'LOOP'
  | 'DELAY'
  | 'RETRY'
  | 'APPROVAL'
  | 'FAILURE'
  | 'COMPLETION';

export interface WorkflowNode {
  id: string;
  name: string;
  type: string;
  status: WorkflowNodeStatus;
  flow_type: WorkflowFlowType;
  depends_on: string[];
  on_success?: string;
  on_failure?: string;
  inputs: Record<string, any>;
  outputs: Record<string, any>;
  error?: string;
  started_at?: string;
  finished_at?: string;
  retry_count: number;
  max_retries?: number;
  loop_count: number;
  metadata: Record<string, any>;
}

export interface Workflow {
  id: string;
  name: string;
  description: string;
  status: WorkflowStatus;
  flow_type: WorkflowFlowType;
  template_id?: string;
  tags: string[];
  nodes: Record<string, WorkflowNode>;
  variables: Record<string, any>;
  created_at: string;
  updated_at: string;
  error?: string;
  metadata: Record<string, any>;
}

export interface BranchDecision {
  node_id: string;
  condition_result: boolean;
  branch_taken: string;
  next_node_id?: string;
  timestamp: string;
}

export interface WorkflowRun {
  run_id: string;
  workflow_id: string;
  workflow_name: string;
  status: WorkflowStatus;
  current_node_id?: string;
  completed_nodes: string[];
  failed_nodes: string[];
  total_retries: number;
  duration_seconds: number;
  error?: string;
  branch_decisions: BranchDecision[];
}

export interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  tags: string[];
  flow_type: WorkflowFlowType;
}
