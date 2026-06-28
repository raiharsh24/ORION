import { create } from 'zustand';
import type { Mission, ServiceHealth, HealthStatus } from '../types';
import { missionApi } from '../../../services/api/missionApi';
import { kernelApi } from '../../../services/api/kernelApi';
import { healthApi } from '../../../services/api/healthApi';
import { telemetryApi } from '../../../services/api/telemetryApi';
import { workflowApi } from '../../../services/api/workflowApi';
import type { Workflow } from '../types';

// ==========================================
// 1. Mission Store Implementation
// ==========================================
interface MissionState {
  missions: Mission[];
  activeMissionId: string | null;
  sidebarFilter: 'all' | 'running' | 'completed' | 'failed';
  searchQuery: string;
  pinnedMissions: string[];
  historyMissions: Mission[];
  
  isLoading: boolean;
  isOffline: boolean;
  error: string | null;
  
  loadMissions: () => Promise<void>;
  selectMission: (id: string) => void;
  setFilter: (filter: 'all' | 'running' | 'completed' | 'failed') => void;
  setSearch: (query: string) => void;
  togglePin: (id: string) => void;
  
  // Controls
  startMission: (id: string) => Promise<void>;
  pauseMission: (id: string) => Promise<void>;
  resumeMission: (id: string) => Promise<void>;
  restartMission: (id: string) => Promise<void>;
  retryMission: (id: string) => Promise<void>;
  cancelMission: (id: string) => Promise<void>;
  confirmMissionAction: (id: string, approved: boolean) => Promise<void>;
  clearMissions: () => void;
}

export const useMissionStore = create<MissionState>((set, get) => ({
  missions: [],
  activeMissionId: null,
  sidebarFilter: 'all',
  searchQuery: '',
  pinnedMissions: [],
  historyMissions: [],
  
  isLoading: false,
  isOffline: false,
  error: null,

  loadMissions: async () => {
    set({ isLoading: get().missions.length === 0 });
    try {
      const data = await missionApi.getMissions();
      
      // Separate active and historical missions
      const archived = data.filter((m) => m.status === 'COMPLETED' || m.status === 'FAILED' || m.status === 'CANCELLED');
      
      set({ 
        missions: data, 
        historyMissions: archived,
        isOffline: false, 
        error: null,
        isLoading: false 
      });
      
      // Auto-select first mission if none active
      if (!get().activeMissionId && data.length > 0) {
        set({ activeMissionId: data[0].id });
      }
    } catch (err: any) {
      set({ 
        isOffline: true, 
        error: err.message || 'Failed to fetch missions from live API.', 
        isLoading: false 
      });
    }
  },

  selectMission: (id) => set({ activeMissionId: id }),
  setFilter: (filter) => set({ sidebarFilter: filter }),
  setSearch: (query) => set({ searchQuery: query }),
  togglePin: (id) => set((state) => ({
    pinnedMissions: state.pinnedMissions.includes(id)
      ? state.pinnedMissions.filter((pid) => pid !== id)
      : [...state.pinnedMissions, id]
  })),

  startMission: async (id) => {
    try {
      await missionApi.startMission(id);
      await get().loadMissions();
    } catch (err: any) {
      set({ error: err.message || 'Failed to start mission on backend.' });
    }
  },

  pauseMission: async (id) => {
    try {
      await missionApi.pauseMission(id);
      await get().loadMissions();
    } catch (err: any) {
      set({ error: err.message || 'Failed to pause mission on backend.' });
    }
  },

  resumeMission: async (id) => {
    try {
      await missionApi.resumeMission(id);
      await get().loadMissions();
    } catch (err: any) {
      set({ error: err.message || 'Failed to resume mission on backend.' });
    }
  },

  restartMission: async (id) => {
    try {
      await missionApi.startMission(id);
      await get().loadMissions();
    } catch (err: any) {
      set({ error: err.message || 'Failed to restart mission on backend.' });
    }
  },

  retryMission: async (id) => {
    try {
      await missionApi.startMission(id);
      await get().loadMissions();
    } catch (err: any) {
      set({ error: err.message || 'Failed to retry mission on backend.' });
    }
  },

  cancelMission: async (id) => {
    try {
      await missionApi.cancelMission(id);
      await get().loadMissions();
    } catch (err: any) {
      set({ error: err.message || 'Failed to cancel mission on backend.' });
    }
  },

  confirmMissionAction: async (id, approved) => {
    try {
      await missionApi.confirmMissionAction(id, approved);
      await get().loadMissions();
    } catch (err: any) {
      set({ error: err.message || 'Failed to authorize action.' });
    }
  },

  clearMissions: () => {
    // Local clear for UI representation
    set((state) => {
      const toKeep = state.missions.filter((m) => 
        m.status !== 'COMPLETED' && m.status !== 'FAILED' && m.status !== 'CANCELLED'
      );
      const newActiveId = toKeep.length > 0 ? toKeep[0].id : null;
      return {
        missions: toKeep,
        activeMissionId: newActiveId
      };
    });
  }
}));

// ==========================================
// 2. Telemetry Store Implementation
// ==========================================
interface TelemetryState {
  executionTimeMs: number;
  eventsCount: number;
  currentTool: string;
  workflow: string;
  latency: number;
  fps: number;
  memory: number;
  isOffline: boolean;
  error: string | null;
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

  loadTelemetry: () => Promise<void>;
  updateTelemetry: (data: Partial<Omit<TelemetryState, 'updateTelemetry' | 'loadTelemetry'>>) => void;
}

export const useTelemetryStore = create<TelemetryState>((set) => ({
  executionTimeMs: 0,
  eventsCount: 0,
  currentTool: '',
  workflow: '',
  latency: 0,
  fps: 60,
  memory: 0,
  isOffline: false,
  error: null,
  current_desktop_task: 'None',
  last_executed_action: 'None',
  average_execution_time_ms: 0,
  failure_count: 0,
  queue_length: 0,
  
  loadTelemetry: async () => {
    try {
      const data = await telemetryApi.getTelemetry();
      set({
        executionTimeMs: data.executionTimeMs,
        eventsCount: data.eventsCount,
        currentTool: data.currentTool,
        workflow: data.workflow,
        latency: data.latency,
        fps: data.fps,
        memory: data.memory,
        isOffline: false,
        error: null,
        current_desktop_task: data.current_desktop_task || 'None',
        last_executed_action: data.last_executed_action || 'None',
        average_execution_time_ms: data.average_execution_time_ms || 0,
        failure_count: data.failure_count || 0,
        queue_length: data.queue_length || 0,
        current_workflow: (data as any).current_workflow || '',
        current_workflow_node: (data as any).current_workflow_node || '',
        workflow_duration_seconds: (data as any).workflow_duration_seconds || 0,
        workflow_branch_decisions: (data as any).workflow_branch_decisions || '',
        workflow_retries: (data as any).workflow_retries || 0,
      });
    } catch (err: any) {
      set({
        isOffline: true,
        error: err.message || 'Failed to fetch telemetry data.'
      });
    }
  },

  updateTelemetry: (data) => set((state) => ({ ...state, ...data }))
}));

// ==========================================
// 3. Kernel Store Implementation
// ==========================================
interface KernelState {
  kernelState: 'BOOTING' | 'INITIALIZING' | 'READY' | 'BUSY' | 'SHUTTING_DOWN' | 'STOPPED' | 'ERROR';
  bootTimeMs: number;
  registeredServicesCount: number;
  cpuUtilization: number;
  memoryUsageBytes: number;
  uptime: string;
  isOffline: boolean;
  error: string | null;
  
  loadKernel: () => Promise<void>;
  updateKernel: (data: Partial<Omit<KernelState, 'updateKernel' | 'loadKernel'>>) => void;
}

export const useKernelStore = create<KernelState>((set) => ({
  kernelState: 'STOPPED',
  bootTimeMs: 0,
  registeredServicesCount: 0,
  cpuUtilization: 0,
  memoryUsageBytes: 0,
  uptime: '--:--:--',
  isOffline: false,
  error: null,
  
  loadKernel: async () => {
    try {
      const data = await kernelApi.getKernelStatus();
      set({
        kernelState: data.kernel_state as any,
        bootTimeMs: data.boot_time_ms,
        registeredServicesCount: data.registered_services_count,
        cpuUtilization: data.cpu_utilization,
        memoryUsageBytes: data.memory_usage_bytes,
        uptime: data.uptime,
        isOffline: false,
        error: null
      });
    } catch (err: any) {
      set({
        isOffline: true,
        kernelState: 'ERROR',
        error: err.message || 'Failed to fetch kernel status.'
      });
    }
  },

  updateKernel: (data) => set((state) => ({ ...state, ...data }))
}));

// ==========================================
// 4. Health Store Implementation
// ==========================================
interface HealthState {
  services: ServiceHealth[];
  isOffline: boolean;
  error: string | null;
  
  loadHealth: () => Promise<void>;
  updateServiceStatus: (name: string, status: HealthStatus, message?: string) => void;
}

export const useHealthStore = create<HealthState>((set, get) => ({
  services: [
    { name: 'Planner', status: 'OFFLINE' },
    { name: 'Knowledge', status: 'OFFLINE' },
    { name: 'Memory', status: 'OFFLINE' },
    { name: 'Mission', status: 'OFFLINE' },
    { name: 'Desktop', status: 'OFFLINE' },
    { name: 'Workflow', status: 'OFFLINE' },
    { name: 'Scheduler', status: 'OFFLINE' },
    { name: 'Telemetry', status: 'OFFLINE' },
    { name: 'LLM', status: 'OFFLINE' },
  ],
  isOffline: false,
  error: null,
  
  loadHealth: async () => {
    try {
      const data = await healthApi.getHealth();
      if (data.services) {
        set({
          services: data.services.map((s) => ({
            name: s.name,
            status: s.status as HealthStatus,
            message: s.message
          })),
          isOffline: false,
          error: null
        });
      }
    } catch (err: any) {
      set({
        isOffline: true,
        error: err.message || 'Failed to fetch subsystem health checks.',
        services: get().services.map((s) => ({ ...s, status: 'OFFLINE', message: 'API connection offline' }))
      });
    }
  },
  
  updateServiceStatus: (name, status, message) => set((state) => ({
    services: state.services.map((s) =>
      s.name === name ? { ...s, status, message } : s
    )
  }))
}));

// ==========================================
// 5. Workflow Store Implementation
// ==========================================
interface WorkflowState {
  workflows: Workflow[];
  activeWorkflowId: string | null;
  templates: any[];
  isLoading: boolean;
  error: string | null;

  loadWorkflows: () => Promise<void>;
  loadTemplates: () => Promise<void>;
  selectWorkflow: (id: string) => void;
  createFromTemplate: (templateId: string, name: string) => Promise<void>;
  startWorkflow: (id: string) => Promise<string | undefined>;
  pauseWorkflow: (id: string) => Promise<void>;
  resumeWorkflow: (id: string) => Promise<void>;
  cancelWorkflow: (id: string) => Promise<void>;
  restartWorkflow: (id: string) => Promise<void>;
  retryNode: (workflowId: string, nodeId: string) => Promise<void>;
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  workflows: [],
  activeWorkflowId: null,
  templates: [],
  isLoading: false,
  error: null,

  loadWorkflows: async () => {
    set({ isLoading: true });
    try {
      const data = await workflowApi.getWorkflows();
      set({ workflows: data as Workflow[], isLoading: false, error: null });
      if (!get().activeWorkflowId && data.length > 0) {
        set({ activeWorkflowId: data[0].id });
      }
    } catch (err: any) {
      set({ isLoading: false, error: err.message || 'Failed to load workflows.' });
    }
  },

  loadTemplates: async () => {
    try {
      const data = await workflowApi.getTemplates();
      set({ templates: data });
    } catch (err: any) {
      set({ error: err.message || 'Failed to load templates.' });
    }
  },

  selectWorkflow: (id) => set({ activeWorkflowId: id }),

  createFromTemplate: async (templateId, name) => {
    try {
      await workflowApi.createWorkflow({ template_id: templateId, name });
      await get().loadWorkflows();
    } catch (err: any) {
      set({ error: err.message || 'Failed to create workflow from template.' });
    }
  },

  startWorkflow: async (id) => {
    try {
      const res = await workflowApi.startWorkflow(id);
      await get().loadWorkflows();
      return res.run_id;
    } catch (err: any) {
      set({ error: err.message || 'Failed to start workflow.' });
    }
  },

  pauseWorkflow: async (id) => {
    try {
      await workflowApi.pauseWorkflow(id);
      await get().loadWorkflows();
    } catch (err: any) {
      set({ error: err.message || 'Failed to pause workflow.' });
    }
  },

  resumeWorkflow: async (id) => {
    try {
      await workflowApi.resumeWorkflow(id);
      await get().loadWorkflows();
    } catch (err: any) {
      set({ error: err.message || 'Failed to resume workflow.' });
    }
  },

  cancelWorkflow: async (id) => {
    try {
      await workflowApi.cancelWorkflow(id);
      await get().loadWorkflows();
    } catch (err: any) {
      set({ error: err.message || 'Failed to cancel workflow.' });
    }
  },

  restartWorkflow: async (id) => {
    try {
      await workflowApi.restartWorkflow(id);
      await get().loadWorkflows();
    } catch (err: any) {
      set({ error: err.message || 'Failed to restart workflow.' });
    }
  },

  retryNode: async (workflowId, nodeId) => {
    try {
      await workflowApi.retryNode(workflowId, nodeId);
      await get().loadWorkflows();
    } catch (err: any) {
      set({ error: err.message || 'Failed to retry node.' });
    }
  },
}));
