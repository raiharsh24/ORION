import { create } from 'zustand';
import {
  INITIAL_AGENTS, INITIAL_MEMORY, MEMORY_SAMPLES,
  SUBTASKS_SEED, INITIAL_PROCESSES, clamp, randomWalk, seedSeries,
} from '../data/mock';
import type { Agent, CoreState, MemoryEvent, SystemProcess } from '../data/mock';

const SERIES_LEN = 42;

export type WorkspaceId = 'command' | 'memory' | 'knowledge' | 'agents' | 'workflows' | 'system' | 'settings';

interface Metric {
  value: number;
  series: number[];
}

interface Subtask {
  id: string;
  label: string;
  done: boolean;
}

interface CommandCenterState {
  // Core visual state machine
  coreState: CoreState;
  setCoreState: (s: CoreState) => void;

  // Active center workspace (nav swaps this; the shell persists)
  activeWorkspace: WorkspaceId;
  setActiveWorkspace: (id: WorkspaceId) => void;

  // Mission control
  missionTitle: string;
  missionStatus: string;
  objective: string;

  // Live system metrics (left "System Overview" + right "System Monitoring")
  cpu: Metric;
  memory: Metric;
  gpu: Metric;
  network: Metric;

  // AI core status stats
  model: string;
  contextWindow: number;   // %
  responseSpeed: number;   // tokens/s
  confidence: number;      // %

  // Core surrounding widgets
  thoughtsProcessed: number;
  tasksRunning: number;
  memoriesStored: number;
  toolsAvailable: number;

  // Energy reactor
  powerLevel: number;      // %

  // System telemetry
  runningProcesses: SystemProcess[];
  activeSession: string;
  apiLatency: number;      // ms (fallback when backend telemetry unavailable)

  // Agents
  agents: Agent[];

  // Memory stream
  memoryStream: MemoryEvent[];

  // Voice
  listening: boolean;
  voiceLevel: number;      // 0..1
  toggleListening: () => void;

  // Current task
  currentTask: string;
  taskProgress: number;    // %
  subtasks: Subtask[];
  toggleSubtask: (id: string) => void;

  // Simulation driver
  tick: () => void;
}

const pushSeries = (series: number[], value: number): number[] => {
  const next = series.length >= SERIES_LEN ? series.slice(1) : series.slice();
  next.push(value);
  return next;
};

let memCounter = 0;

export const useCommandCenterStore = create<CommandCenterState>((set, get) => ({
  coreState: 'idle',
  setCoreState: (s) => set({ coreState: s }),

  activeWorkspace: 'command',
  setActiveWorkspace: (id) => set({ activeWorkspace: id }),

  missionTitle: 'Everything is under control',
  missionStatus: 'FRIDAY Protocol Active · AI Core Online',
  objective: 'Awaiting Command',

  cpu: { value: 34, series: seedSeries(SERIES_LEN, 34) },
  memory: { value: 58, series: seedSeries(SERIES_LEN, 58) },
  gpu: { value: 46, series: seedSeries(SERIES_LEN, 46) },
  network: { value: 22, series: seedSeries(SERIES_LEN, 22) },

  model: 'FRIDAY-Core v2',
  contextWindow: 74,
  responseSpeed: 128,
  confidence: 96,

  thoughtsProcessed: 18423,
  tasksRunning: 3,
  memoriesStored: 10485,
  toolsAvailable: 42,

  powerLevel: 87,

  runningProcesses: INITIAL_PROCESSES.map((p) => ({ ...p })),
  activeSession: 'sess_7f3a2b91',
  apiLatency: 64,

  agents: INITIAL_AGENTS.map((a) => ({ ...a })),

  memoryStream: INITIAL_MEMORY.map((m) => ({ ...m })),

  listening: false,
  voiceLevel: 0,
  toggleListening: () => {
    const next = !get().listening;
    set({
      listening: next,
      coreState: next ? 'listening' : 'idle',
      objective: next ? 'Listening…' : 'Awaiting Command',
    });
  },

  currentTask: 'Research & Analysis',
  taskProgress: 62,
  subtasks: SUBTASKS_SEED.map((s) => ({ ...s })),
  toggleSubtask: (id) =>
    set((state) => {
      const subtasks = state.subtasks.map((s) => (s.id === id ? { ...s, done: !s.done } : s));
      const done = subtasks.filter((s) => s.done).length;
      return { subtasks, taskProgress: Math.round((done / subtasks.length) * 100) };
    }),

  tick: () => {
    const s = get();

    // Bias system load upward while the core is actively thinking / executing
    const boost =
      s.coreState === 'thinking' || s.coreState === 'executing' ? 0.18 :
      s.coreState === 'speaking' ? 0.1 : 0;

    const advance = (m: Metric, volatility: number, bias = 0): Metric => {
      const raw = m.value + ((Math.random() - 0.5) + bias) * volatility;
      const value = clamp(raw, 2, 99);
      return { value, series: pushSeries(m.series, value) };
    };

    const cpu = advance(s.cpu, 7, boost * 0.6);
    const memory = advance(s.memory, 3, boost * 0.2);
    const gpu = advance(s.gpu, 9, boost * 0.7);
    const network = advance(s.network, 14, boost * 0.3);

    // Voice level animates only while listening/speaking
    const active = s.listening || s.coreState === 'speaking';
    const voiceLevel = active
      ? clamp(0.35 + Math.random() * 0.65, 0, 1)
      : Math.max(0, s.voiceLevel * 0.7);

    // Occasionally push a new memory event
    let memoryStream = s.memoryStream;
    if (Math.random() < 0.22) {
      const sample = MEMORY_SAMPLES[Math.floor(Math.random() * MEMORY_SAMPLES.length)];
      const fresh: MemoryEvent = { ...sample, id: `live-${memCounter++}`, time: 'now' };
      const aged = s.memoryStream.map((m, i) => ({ ...m, time: i === 0 ? '4s' : m.time }));
      memoryStream = [fresh, ...aged].slice(0, 6);
    }

    // Agents drift their activity a little
    const agents = s.agents.map((a) => ({
      ...a,
      activity: a.status === 'IDLE' ? clamp(randomWalk(a.activity, 4, 2, 20)) : clamp(randomWalk(a.activity, 8, 20, 96)),
    }));

    const runningProcesses = s.runningProcesses.map((p) => ({
      ...p,
      cpu: clamp(randomWalk(p.cpu, 4, 1, 42)),
    }));
    const apiLatency = Math.round(clamp(randomWalk(s.apiLatency, 10, 28, 180), 28, 180));

    set({
      cpu, memory, gpu, network,
      voiceLevel,
      memoryStream,
      agents,
      runningProcesses,
      apiLatency,
      confidence: clamp(randomWalk(s.confidence, 2, 88, 99)),
      responseSpeed: Math.round(clamp(randomWalk(s.responseSpeed, 12, 90, 190), 90, 190)),
      contextWindow: clamp(randomWalk(s.contextWindow, 3, 40, 95)),
      powerLevel: clamp(randomWalk(s.powerLevel, 2, 70, 99)),
      thoughtsProcessed: s.thoughtsProcessed + Math.floor(Math.random() * 24),
    });
  },
}));
