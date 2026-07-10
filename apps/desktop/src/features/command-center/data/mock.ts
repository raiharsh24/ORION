import type { LucideIcon } from 'lucide-react';
import {
  Cpu, Database, BarChart3, Radar,
  FilePlus2, FolderOpen, ScanLine, Zap, FileText, Settings,
} from 'lucide-react';

export type CoreState = 'idle' | 'thinking' | 'listening' | 'speaking' | 'executing';

export type AgentStatus = 'ACTIVE' | 'IDLE' | 'BUSY' | 'ERROR';

export interface Agent {
  id: string;
  name: string;
  role: string;
  status: AgentStatus;
  icon: LucideIcon;
  health: number;      // 0..100
  activity: number;    // 0..100 current load
  task: string;
}

export interface MemoryEvent {
  id: string;
  label: string;
  detail: string;
  time: string;        // display timestamp
  kind: 'store' | 'recall' | 'link' | 'index';
}

export interface SystemCommand {
  id: string;
  label: string;
  icon: LucideIcon;
  accent?: 'cyan' | 'orange';
}

export const INITIAL_AGENTS: Agent[] = [
  { id: 'orion', name: 'Orion', role: 'Task Executor', status: 'ACTIVE', icon: Radar, health: 98, activity: 72, task: 'Executing plan step 3/5' },
  { id: 'atlas', name: 'Atlas', role: 'Knowledge Engine', status: 'ACTIVE', icon: Database, health: 95, activity: 64, task: 'Indexing workspace graph' },
  { id: 'nova', name: 'Nova', role: 'Data Analyst', status: 'IDLE', icon: BarChart3, health: 100, activity: 8, task: 'Awaiting dataset' },
  { id: 'echo', name: 'Echo', role: 'System Monitor', status: 'ACTIVE', icon: Cpu, health: 91, activity: 41, task: 'Watching subsystems' },
];

export const INITIAL_MEMORY: MemoryEvent[] = [
  { id: 'm1', label: 'Context checkpoint saved', detail: 'session · command-center', time: 'now', kind: 'store' },
  { id: 'm2', label: 'Recalled project blueprint', detail: 'ORION / desktop', time: '12s', kind: 'recall' },
  { id: 'm3', label: 'Linked knowledge nodes', detail: '4 relationships', time: '48s', kind: 'link' },
  { id: 'm4', label: 'Indexed 128 documents', detail: 'workspace scan', time: '2m', kind: 'index' },
  { id: 'm5', label: 'Stored user preference', detail: 'theme · dark', time: '5m', kind: 'store' },
];

export const MEMORY_SAMPLES: Omit<MemoryEvent, 'id' | 'time'>[] = [
  { label: 'Embedded new note', detail: 'vector store', kind: 'store' },
  { label: 'Recalled prior decision', detail: 'planner cache', kind: 'recall' },
  { label: 'Linked entity graph', detail: 'ATLAS', kind: 'link' },
  { label: 'Indexed source file', detail: 'workspace watcher', kind: 'index' },
  { label: 'Context window trimmed', detail: 'memory manager', kind: 'store' },
  { label: 'Recalled agent state', detail: 'Orion', kind: 'recall' },
];

export const SYSTEM_COMMANDS: SystemCommand[] = [
  { id: 'new-task', label: 'New Task', icon: FilePlus2, accent: 'cyan' },
  { id: 'open-file', label: 'Open File', icon: FolderOpen },
  { id: 'system-scan', label: 'System Scan', icon: ScanLine },
  { id: 'optimize', label: 'Optimize', icon: Zap, accent: 'orange' },
  { id: 'report', label: 'Generate Report', icon: FileText },
  { id: 'settings', label: 'Settings', icon: Settings },
];

export const SUBTASKS_SEED = [
  { id: 's1', label: 'Gather source material', done: true },
  { id: 's2', label: 'Analyze dependencies', done: true },
  { id: 's3', label: 'Synthesize findings', done: false },
  { id: 's4', label: 'Draft report', done: false },
];

// ── small numeric helpers for live-data simulation ──
export const clamp = (v: number, min = 0, max = 100) => Math.min(max, Math.max(min, v));

export const randomWalk = (value: number, volatility = 6, min = 4, max = 98): number =>
  clamp(value + (Math.random() - 0.5) * volatility, min, max);

export const seedSeries = (length: number, base: number, spread = 14): number[] =>
  Array.from({ length }, (_, i) =>
    clamp(base + Math.sin(i / 3) * (spread / 2) + (Math.random() - 0.5) * spread),
  );
