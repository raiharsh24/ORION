import { create } from 'zustand';
import { cognitiveApi } from '../../../services/api/cognitiveApi';
import type {
  CognitiveGoal, CognitiveGoalDetail, CognitiveNode,
  CognitiveTimelineEntry, CognitivePanelState, MissionControl,
} from '../types';

interface CognitiveStoreState {
  health: Record<string, unknown> | null;
  context: Record<string, unknown> | null;
  goals: CognitiveGoal[];
  activeGoal: CognitiveGoalDetail | null;
  hierarchyNodes: CognitiveNode[];
  timeline: CognitiveTimelineEntry[];
  panel: CognitivePanelState;
  missions: MissionControl[];
  activeMissionId: string | null;
  schedulerStats: Record<string, unknown> | null;
  learningData: Record<string, unknown> | null;
  reflectionStats: Record<string, unknown> | null;

  isLoading: boolean;
  error: string | null;

  loadHealth: () => Promise<void>;
  loadContext: () => Promise<void>;
  loadGoals: (status?: string) => Promise<void>;
  loadActiveGoal: (goalId: string) => Promise<void>;
  loadHierarchy: (hierarchyId: string) => Promise<void>;
  loadReflections: () => Promise<void>;
  loadScheduler: () => Promise<void>;
  loadLearning: () => Promise<void>;

  addTimelineEvent: (event: CognitiveTimelineEntry) => void;
  updatePanel: (partial: Partial<CognitivePanelState>) => void;
  selectMission: (id: string | null) => void;
  setError: (error: string | null) => void;
}

const defaultPanel: CognitivePanelState = {
  reasoningStage: 'idle',
  confidence: 0,
  selectedTools: [],
  activeAgent: 'none',
  memoryUpdates: 0,
  reflectionSummary: 'No reflections yet',
};

export const useCognitiveStore = create<CognitiveStoreState>((set, get) => ({
  health: null,
  context: null,
  goals: [],
  activeGoal: null,
  hierarchyNodes: [],
  timeline: [],
  panel: { ...defaultPanel },
  missions: [],
  activeMissionId: null,
  schedulerStats: null,
  learningData: null,
  reflectionStats: null,

  isLoading: false,
  error: null,

  loadHealth: async () => {
    try {
      const data = await cognitiveApi.getHealth();
      set({ health: data as unknown as Record<string, unknown>, error: null });
    } catch (err: any) {
      set({ error: err.message || 'Failed to load cognitive health' });
    }
  },

  loadContext: async () => {
    try {
      const data = await cognitiveApi.getContext();
      set({ context: data as unknown as Record<string, unknown>, error: null });
    } catch (err: any) {
      set({ error: err.message || 'Failed to load cognitive context' });
    }
  },

  loadGoals: async (status?: string) => {
    set({ isLoading: get().goals.length === 0 });
    try {
      const data = await cognitiveApi.listGoals(status);
      set({ goals: data.goals, isLoading: false, error: null });
    } catch (err: any) {
      set({ isLoading: false, error: err.message || 'Failed to load goals' });
    }
  },

  loadActiveGoal: async (goalId: string) => {
    try {
      const data = await cognitiveApi.getGoal(goalId);
      set({ activeGoal: data, error: null });
    } catch (err: any) {
      set({ error: err.message || 'Failed to load goal detail' });
    }
  },

  loadHierarchy: async (hierarchyId: string) => {
    try {
      const data = await cognitiveApi.getHierarchy(hierarchyId);
      set({ hierarchyNodes: data.nodes, error: null });
    } catch (err: any) {
      set({ error: err.message || 'Failed to load hierarchy' });
    }
  },

  loadReflections: async () => {
    try {
      const data = await cognitiveApi.getReflections();
      set({ reflectionStats: data as unknown as Record<string, unknown>, error: null });
    } catch (err: any) {
      set({ error: err.message || 'Failed to load reflections' });
    }
  },

  loadScheduler: async () => {
    try {
      const data = await cognitiveApi.getScheduler();
      set({ schedulerStats: data as unknown as Record<string, unknown>, error: null });
    } catch (err: any) {
      set({ error: err.message || 'Failed to load scheduler' });
    }
  },

  loadLearning: async () => {
    try {
      const data = await cognitiveApi.getLearning();
      set({ learningData: data as unknown as Record<string, unknown>, error: null });
    } catch (err: any) {
      set({ error: err.message || 'Failed to load learning data' });
    }
  },

  addTimelineEvent: (event) => {
    set((state) => ({
      timeline: [event, ...state.timeline].slice(0, 200),
    }));
  },

  updatePanel: (partial) => {
    set((state) => ({
      panel: { ...state.panel, ...partial },
    }));
  },

  selectMission: (id) => set({ activeMissionId: id }),

  setError: (error) => set({ error }),
}));
