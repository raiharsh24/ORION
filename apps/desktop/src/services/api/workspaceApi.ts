import { apiFetch } from './api';
import { API_BASE_URL } from '../../config/api';

const BASE_URL = API_BASE_URL;

export interface WorkspaceProject {
  name: string;
  path: string;
  technologies: string[];
  is_git: boolean;
  branch: string | null;
  file_count: number;
  graph_stats: {
    total_files: number;
    total_modules: number;
    total_imports: number;
    entry_points: number;
    files_by_extension: Record<string, number>;
  } | null;
}

export interface WorkspaceContext {
  workspace_root: string;
  projects: WorkspaceProject[];
  project_count: number;
}

export interface ProjectDetail {
  name: string;
  root: string;
  technologies: string[];
  stats: {
    total_files: number;
    total_modules: number;
    total_imports: number;
    entry_points: number;
    files_by_extension: Record<string, number>;
  };
  modules: { name: string; file_count: number; is_package: boolean }[];
  entry_points: string[];
}

export interface ScanResponse {
  success: boolean;
  projects_discovered: number;
  project_names: string[];
}

export interface WorkspaceHealth {
  status: string;
  projects_cached: number;
  graphs_cached: number;
  watcher_running: boolean;
}

export interface WorkspaceInsights {
  insights: string[];
  insight_count: number;
}

export const workspaceApi = {
  getProjects: (rescan = false) => {
    const params = rescan ? '?rescan=true' : '';
    return apiFetch<WorkspaceContext>(`${BASE_URL}/workspace/projects${params}`);
  },

  getProject: (path: string) =>
    apiFetch<ProjectDetail>(`${BASE_URL}/workspace/projects/${encodeURIComponent(path)}`),

  triggerScan: (scanPath?: string) => {
    const params = scanPath ? `?scan_path=${encodeURIComponent(scanPath)}` : '';
    return apiFetch<ScanResponse>(`${BASE_URL}/workspace/scan${params}`, {
      method: 'POST',
    });
  },

  getHealth: () =>
    apiFetch<WorkspaceHealth>(`${BASE_URL}/workspace/health`),

  getInsights: () =>
    apiFetch<WorkspaceInsights>(`${BASE_URL}/workspace/insights`),
};
