import { apiFetch } from './api';
import { API_BASE_URL } from '../../config/api';

const BASE = API_BASE_URL;

export interface CognitiveHealth {
  status: string;
  goal_memory: Record<string, number>;
  adaptive_learning: Record<string, unknown>;
  confidence_v2: Record<string, unknown>;
  reflection_v2: Record<string, unknown>;
  goal_manager: Record<string, unknown>;
  autonomous_scheduler: Record<string, unknown>;
  consolidation: Record<string, unknown>;
  orchestrator: Record<string, unknown>;
}

export interface CognitiveContext {
  goals: {
    total_goals: number;
    active_goals: number;
    completed_goals: number;
    failed_goals: number;
    projects: number;
    top_priorities: { goal_id: string; objective: string; priority: number }[];
    unfinished: { goal_id: string; objective: string; progress: number }[];
  };
  learning: Record<string, unknown>;
  scheduler: Record<string, unknown>;
}

export interface GoalSummary {
  goal_id: string;
  objective: string;
  status: string;
  progress_pct: number;
  priority: number;
  parent_id: string | null;
  milestones: number;
  created_at: number;
}

export interface GoalDetail {
  goal_id: string;
  objective: string;
  description: string;
  status: string;
  progress_pct: number;
  priority: number;
  parent_id: string | null;
  milestones: {
    id: string;
    name: string;
    description: string;
    completed: boolean;
    created_at: number;
    completed_at?: number;
  }[];
  tags: string[];
  created_at: number;
  updated_at: number;
  completed_at: number | null;
}

export interface ReflectionStats {
  total_reflections: number;
  avg_stage_success_rate: number;
  total_failures_recorded: number;
  total_strategies_recorded: number;
}

export interface SchedulerData {
  stats: {
    total_scheduled: number;
    total_executed: number;
    pending_count: number;
    completed_count: number;
    failed_count: number;
    cancelled_count: number;
  };
  pending: {
    mission_id: string;
    objective: string;
    type: string;
    priority: number;
    status: string;
    next_run: number | null;
    run_count: number;
  }[];
}

export interface LearningSummary {
  agent_reliability: Record<string, number>;
  tool_success_rates: Record<string, number>;
  strategy_scores: Record<string, number>;
}

export interface ConfidenceScore {
  capability: string;
  strategy: string;
  overall_confidence: number;
  overall_risk: number;
  warnings: string[];
  should_proceed: boolean;
}

export interface HierarchyDetail {
  root_id: string;
  depth: number;
  nodes: {
    goal_id: string;
    objective: string;
    parent_id: string | null;
    children: string[];
    status: string;
    priority: number;
    progress_pct: number;
    depends_on: string[];
    milestones: number;
  }[];
}

export const cognitiveApi = {
  getHealth: () =>
    apiFetch<CognitiveHealth>(`${BASE}/cognitive/health`),

  getContext: () =>
    apiFetch<CognitiveContext>(`${BASE}/cognitive/context`),

  listGoals: (status?: string) => {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    return apiFetch<{ total: number; goals: GoalSummary[] }>(
      `${BASE}/cognitive/goals?${params.toString()}`
    );
  },

  getGoal: (goalId: string) =>
    apiFetch<GoalDetail>(`${BASE}/cognitive/goals/${goalId}`),

  getHierarchy: (hierarchyId: string) =>
    apiFetch<HierarchyDetail>(`${BASE}/cognitive/hierarchy/${hierarchyId}`),

  getReflections: () =>
    apiFetch<ReflectionStats>(`${BASE}/cognitive/reflections`),

  getScheduler: () =>
    apiFetch<SchedulerData>(`${BASE}/cognitive/scheduler`),

  getLearning: () =>
    apiFetch<LearningSummary>(`${BASE}/cognitive/learning`),

  evaluateConfidence: (capability: string, strategy: string = 'direct') =>
    apiFetch<ConfidenceScore>(
      `${BASE}/cognitive/confidence/evaluate?capability=${encodeURIComponent(capability)}&strategy=${encodeURIComponent(strategy)}`,
      { method: 'POST' }
    ),

  submitMission: (objective: string, description: string = '') =>
    apiFetch<Record<string, unknown>>(
      `${BASE}/cognitive/mission?objective=${encodeURIComponent(objective)}&description=${encodeURIComponent(description)}`,
      { method: 'POST' }
    ),

  startScheduler: () =>
    apiFetch<{ status: string }>(`${BASE}/cognitive/scheduler/start`, { method: 'POST' }),

  stopScheduler: () =>
    apiFetch<{ status: string }>(`${BASE}/cognitive/scheduler/stop`, { method: 'POST' }),

  executeDue: () =>
    apiFetch<{ executed: string[]; count: number }>(
      `${BASE}/cognitive/scheduler/execute-due`,
      { method: 'POST' }
    ),

  startConsolidation: () =>
    apiFetch<{ status: string }>(`${BASE}/cognitive/consolidation/start`, { method: 'POST' }),

  runConsolidation: () =>
    apiFetch<Record<string, unknown>>(`${BASE}/cognitive/consolidation/run`, { method: 'POST' }),
};
