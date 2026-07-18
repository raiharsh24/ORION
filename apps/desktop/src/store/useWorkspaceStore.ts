import { create } from 'zustand';
import { workspaceApi } from '../services/api/workspaceApi';
import type { WorkspaceProject, WorkspaceInsights } from '../services/api/workspaceApi';

interface WorkspaceState {
  projects: WorkspaceProject[];
  insights: WorkspaceInsights | null;
  projectCount: number;
  workspaceRoot: string;

  // Daily-driver context: the project/file the user is currently focused on.
  currentProjectPath: string | null;
  activeFilePath: string | null;

  isLoading: boolean;
  isOffline: boolean;
  error: string | null;

  loadProjects: (rescan?: boolean) => Promise<void>;
  loadInsights: () => Promise<void>;
  refreshAll: () => Promise<void>;

  setCurrentProject: (path: string | null) => void;
  setActiveFile: (path: string | null) => void;
  getCurrentProject: () => WorkspaceProject | null;
}

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  projects: [],
  insights: null,
  projectCount: 0,
  workspaceRoot: '',

  currentProjectPath: null,
  activeFilePath: null,

  isLoading: false,
  isOffline: false,
  error: null,

  loadProjects: async (rescan = false) => {
    set({ isLoading: get().projects.length === 0 });
    try {
      const data = await workspaceApi.getProjects(rescan);
      // Default the "current project" to the first git-tracked project once known.
      const current = get().currentProjectPath;
      const defaultCurrent =
        current ??
        (data.projects.find((p) => p.is_git)?.path ?? data.projects[0]?.path ?? null);
      set({
        projects: data.projects,
        projectCount: data.project_count,
        workspaceRoot: data.workspace_root,
        currentProjectPath: defaultCurrent,
        isOffline: false,
        error: null,
        isLoading: false,
      });
    } catch (err: any) {
      set({
        isOffline: true,
        error: err.message || 'Failed to fetch workspace projects.',
        isLoading: false,
      });
    }
  },

  loadInsights: async () => {
    try {
      const data = await workspaceApi.getInsights();
      set({ insights: data, isOffline: false, error: null });
    } catch (err: any) {
      set({ error: err.message || 'Failed to fetch workspace insights.' });
    }
  },

  refreshAll: async () => {
    set({ isLoading: true });
    await Promise.all([get().loadProjects(true), get().loadInsights()]);
    set({ isLoading: false });
  },

  setCurrentProject: (path) => set({ currentProjectPath: path }),
  setActiveFile: (path) => set({ activeFilePath: path }),
  getCurrentProject: () => {
    const { projects, currentProjectPath } = get();
    if (!projects.length) return null;
    return projects.find((p) => p.path === currentProjectPath) ?? projects[0];
  },
}));
