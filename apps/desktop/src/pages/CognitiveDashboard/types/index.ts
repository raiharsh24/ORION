export interface CognitiveGoal {
  goal_id: string;
  objective: string;
  status: string;
  progress_pct: number;
  priority: number;
  parent_id: string | null;
  milestones: number;
  created_at: number;
}

export interface CognitiveGoalDetail extends Omit<CognitiveGoal, 'milestones'> {
  description: string;
  milestones: CognitiveMilestone[];
  tags: string[];
  updated_at: number;
  completed_at: number | null;
}

export interface CognitiveMilestone {
  id: string;
  name: string;
  description: string;
  completed: boolean;
  created_at: number;
  completed_at?: number;
}

export interface TimelineEvent {
  id: string;
  topic: string;
  data: Record<string, unknown>;
  timestamp: number;
  category: 'mission' | 'tool' | 'agent' | 'cognitive' | 'system' | 'learning';
}

export interface CognitiveNode {
  goal_id: string;
  objective: string;
  parent_id: string | null;
  children: string[];
  status: string;
  priority: number;
  progress_pct: number;
  depends_on: string[];
  milestones: number;
}

export interface CognitiveTimelineEntry {
  id: string;
  type: 'mission_state' | 'tool_exec' | 'agent_delegation' | 'recovery' | 'learning_update' | 'goal_event' | 'scheduler_event' | 'system';
  summary: string;
  detail: string;
  timestamp: number;
  status: 'success' | 'failure' | 'info' | 'warning';
}

export interface CognitivePanelState {
  reasoningStage: string;
  confidence: number;
  selectedTools: string[];
  activeAgent: string;
  memoryUpdates: number;
  reflectionSummary: string;
}

export interface MissionControl {
  id: string;
  name: string;
  status: string;
  progress: number;
  canPause: boolean;
  canResume: boolean;
  canCancel: boolean;
  canRetry: boolean;
  needsApproval: boolean;
  logs: { time: string; level: string; msg: string }[];
  files: { name: string; path: string; size: number }[];
}
