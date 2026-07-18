import React, { useEffect, useCallback, useState } from 'react';
import { Hero } from '../../../components/Hero';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '../../../components/ui/Card';
import { Button } from '../../../components/ui/Button';
import { WorkspaceMiniGraph } from '../../../components/ui/WorkspaceMiniGraph';
import type { FileEntry } from '../../../components/ui/WorkspaceMiniGraph';
import { ExplainPanel } from '../../../components/ui/ExplainPanel';
import type { ExplainSubject } from '../../../components/ui/ExplainPanel';
import { CardSkeleton } from '../../../components/ui/Skeleton';
import type { WorkspaceProject } from '../../../services/api/workspaceApi';
import type { ToolInfo } from '../../../services/api/toolsApi';
import { toolsApi } from '../../../services/api/toolsApi';
import type { LucideIcon } from 'lucide-react';
import {
  Cpu, Database, Blocks, Activity, GitBranch,
  FolderOpen, FileCode, Box, RefreshCw, Terminal, Zap,
  AlertCircle, Clock, ChevronRight, Globe,
  ListTree, Monitor, FolderTree, Search,
} from 'lucide-react';
import { useKernelStore } from '../../../pages/MissionCenter/store';
import { useHealthStore } from '../../../pages/MissionCenter/store';
import { useTelemetryStore } from '../../../pages/MissionCenter/store';
import { useMissionStore } from '../../../pages/MissionCenter/store';
import { useWorkspaceStore } from '../../../store/useWorkspaceStore';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

function formatUptime(uptime: string): string {
  if (!uptime || uptime === '--:--:--') return '--:--:--';
  return uptime;
}

const statusColor: Record<string, string> = {
  ONLINE: 'text-emerald-400',
  HEALTHY: 'text-emerald-400',
  OK: 'text-emerald-400',
  NOMINAL: 'text-emerald-400',
  DEGRADED: 'text-amber-400',
  OFFLINE: 'text-rose-400',
  ERROR: 'text-rose-400',
};

const categoryToIcon: Record<string, LucideIcon> = {
  filesystem: FolderOpen,
  terminal: Terminal,
  desktop: Monitor,
  browser: Globe,
  clipboard: FileCode,
  knowledge: Database,
  memory: Database,
  workflow: Blocks,
  mission: ListTree,
  git: GitBranch,
  docker: Box,
  llm: Cpu,
  ocr: Search,
  custom_plugins: Blocks,
};

const TechIcon: Record<string, LucideIcon> = {
  python: FileCode,
  javascript: FileCode,
  typescript: FileCode,
  go: Terminal,
  rust: Terminal,
  docker: Box,
  shell: Terminal,
  makefile: ListTree,
  java: FileCode,
  kotlin: FileCode,
  ruby: FileCode,
  swift: FileCode,
};

function ProjectCard({ project }: { project: any }) {
  const Icon = TechIcon[project.technologies?.[0]?.toLowerCase()] || FolderOpen;
  const stats = project.graph_stats;
  const hasStats = stats && stats.total_files > 0;

  return (
    <Card variant="default" hoverable>
      <CardHeader>
        <div className="flex justify-between items-start">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-zinc-950 border border-matte-border">
              <Icon className="w-4 h-4 text-cyan-glow/85" />
            </div>
            <div>
              <CardTitle>{project.name}</CardTitle>
              <CardDescription>
                {project.is_git ? (
                  <span className="flex items-center gap-1">
                    <GitBranch className="w-3 h-3" />
                    {project.branch || 'main'}
                  </span>
                ) : 'No git'}
              </CardDescription>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-1.5 mb-3">
          {project.technologies?.map((t: string) => (
            <span
              key={t}
              className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full
                         bg-cyan-glow/5 border border-cyan-border/20 text-cyan-glow/80"
            >
              {t}
            </span>
          ))}
        </div>
        {hasStats ? (
          <div className="grid grid-cols-2 gap-3 text-xs font-mono">
            <div className="flex items-center gap-1.5 text-zinc-400">
              <FileCode className="w-3 h-3" />
              <span>{stats.total_files} files</span>
            </div>
            <div className="flex items-center gap-1.5 text-zinc-400">
              <Box className="w-3 h-3" />
              <span>{stats.total_modules} modules</span>
            </div>
            <div className="flex items-center gap-1.5 text-zinc-400">
              <Zap className="w-3 h-3" />
              <span>{stats.total_imports} imports</span>
            </div>
            <div className="flex items-center gap-1.5 text-zinc-400">
              <ChevronRight className="w-3 h-3" />
              <span>{stats.entry_points} entry pts</span>
            </div>
          </div>
        ) : (
          <p className="text-xs text-zinc-500 font-mono">Not yet scanned</p>
        )}
      </CardContent>
      <CardFooter>
        <span className="text-[10px] text-zinc-600 font-mono">{project.path}</span>
      </CardFooter>
    </Card>
  );
}

function ProjectFileTree({ project, onExplain }: { project: WorkspaceProject; onExplain?: (entry: FileEntry, project: WorkspaceProject) => void }) {
  const stats = project.graph_stats;
  const extChildren: FileEntry[] = stats?.files_by_extension
    ? Object.entries(stats.files_by_extension).map(([ext, count]) => ({
        name: `${ext} (${count})`,
        path: `${project.path}/ext${ext}`,
        type: 'file' as const,
        extension: ext,
        language: ext.replace('.', ''),
      }))
    : [];

  const rootEntry: FileEntry = {
    name: project.name,
    path: project.path,
    type: 'directory',
    children: [
      ...(stats
        ? [
            { name: `src/ (${stats.total_files} files)`, path: `${project.path}/src`, type: 'directory' as const, children: extChildren },
            { name: `modules/ (${stats.total_modules})`, path: `${project.path}/modules`, type: 'directory' as const },
          ]
        : []),
    ],
  };

  return (
    <WorkspaceMiniGraph
      files={[rootEntry]}
      projectName={project.name}
      onExplain={onExplain ? (entry) => onExplain(entry, project) : undefined}
    />
  );
}

export const DashboardPage: React.FC = () => {
  const kernelState = useKernelStore((s) => s);
  const healthState = useHealthStore((s) => s);
  const telemetryState = useTelemetryStore((s) => s);
  const missionState = useMissionStore((s) => s);
  const workspaceState = useWorkspaceStore((s) => s);

  const loadKernel = useKernelStore((s) => s.loadKernel);
  const loadHealth = useHealthStore((s) => s.loadHealth);
  const loadTelemetry = useTelemetryStore((s) => s.loadTelemetry);
  const loadMissions = useMissionStore((s) => s.loadMissions);
  const loadProjects = useWorkspaceStore((s) => s.loadProjects);
  const loadInsights = useWorkspaceStore((s) => s.loadInsights);

  const [explainSubject, setExplainSubject] = useState<ExplainSubject | null>(null);

  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [toolsLoading, setToolsLoading] = useState(true);
  const [toolsError, setToolsError] = useState<string | null>(null);

  const loadTools = useCallback(async () => {
    setToolsLoading(true);
    setToolsError(null);
    try {
      const res = await toolsApi.listTools();
      setTools(res.tools);
    } catch (err: any) {
      setToolsError(err.message || 'Failed to load tools');
    } finally {
      setToolsLoading(false);
    }
  }, []);

  const toggleToolEnabled = useCallback(async (toolId: string, enabled: boolean) => {
    try {
      if (enabled) {
        await toolsApi.enableTool(toolId);
      } else {
        await toolsApi.disableTool(toolId);
      }
      setTools((prev) => prev.map((t) => (t.id === toolId ? { ...t, enabled } : t)));
    } catch (err: any) {
      setToolsError(err.message || 'Failed to toggle tool');
    }
  }, []);

  const refreshAll = useCallback(() => {
    loadKernel();
    loadHealth();
    loadTelemetry();
    loadMissions();
    loadProjects();
    loadInsights();
    loadTools();
  }, [loadKernel, loadHealth, loadTelemetry, loadMissions, loadProjects, loadInsights, loadTools]);

  useEffect(() => {
    refreshAll();
    const interval = setInterval(refreshAll, 30_000);
    return () => clearInterval(interval);
  }, [refreshAll]);

  const recentMissions = (missionState.missions ?? []).slice(0, 5);
  const projects = workspaceState.projects ?? [];
  const insights = workspaceState.insights?.insights ?? [];

  const kernelStatus = kernelState.kernelState === 'READY' || kernelState.kernelState === 'BUSY';
  const kernelLabel = kernelState.isOffline ? 'OFFLINE' : kernelState.kernelState;

  const healthOnline = healthState.services.filter((s) => s.status === 'HEALTHY').length;
  const healthTotal = healthState.services.length;

  return (
    <div className="space-y-8 animate-fade-in">
      <Hero />

      {/* ── System Status Row ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card variant="glow">
          <CardHeader>
            <div className="flex justify-between items-start">
              <CardTitle>Kernel Status</CardTitle>
              <Cpu className="w-4 h-4 text-cyan-glow" />
            </div>
            <CardDescription>System runtime</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-[10px] font-mono uppercase tracking-wider ${
                kernelStatus ? 'text-emerald-400' : 'text-rose-400'
              }`}>
                {kernelStatus ? (
                  <span className="flex items-center gap-1">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-400" />
                    </span>
                    {kernelLabel}
                  </span>
                ) : (
                  <span className="flex items-center gap-1">
                    <AlertCircle className="w-3 h-3" />
                    {kernelLabel}
                  </span>
                )}
              </span>
            </div>
            <div className="text-2xl font-bold tracking-tight text-zinc-100">
              {kernelState.cpuUtilization.toFixed(1)}%
            </div>
            <div className="w-full bg-zinc-900 h-1.5 rounded-full mt-3 overflow-hidden border border-matte-border">
              <div
                className="bg-cyan-glow h-full rounded-full transition-all duration-500"
                style={{ width: `${Math.min(kernelState.cpuUtilization, 100)}%` }}
              />
            </div>
            <div className="text-[10px] font-mono mt-2 flex justify-between text-zinc-500">
              <span>CPU</span>
              <span>{formatUptime(kernelState.uptime)} uptime</span>
            </div>
          </CardContent>
        </Card>

        <Card variant="default">
          <CardHeader>
            <div className="flex justify-between items-start">
              <CardTitle>Memory</CardTitle>
              <Database className="w-4 h-4 text-cyan-glow" />
            </div>
            <CardDescription>Process memory</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold tracking-tight text-zinc-100">
              {formatBytes(kernelState.memoryUsageBytes)}
            </div>
            <div className="text-[10px] text-zinc-500 font-mono mt-1">
              {kernelState.registeredServicesCount} registered services
            </div>
          </CardContent>
        </Card>

        <Card variant="default">
          <CardHeader>
            <div className="flex justify-between items-start">
              <CardTitle>System Health</CardTitle>
              <Activity className="w-4 h-4 text-cyan-glow" />
            </div>
            <CardDescription>Subsystem status</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold tracking-tight text-zinc-100">
              {healthOnline}/{healthTotal}
            </div>
            <div className="flex flex-wrap gap-1 mt-2">
              {healthState.services.slice(0, 5).map((svc) => (
                <span key={svc.name} className={`text-[9px] font-mono uppercase ${statusColor[svc.status] || 'text-zinc-600'}`}>
                  {svc.name}
                </span>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card variant="glow">
          <CardHeader>
            <div className="flex justify-between items-start">
              <CardTitle>Execution</CardTitle>
              <Zap className="w-4 h-4 text-cyan-glow" />
            </div>
            <CardDescription>Active telemetry</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold tracking-tight text-zinc-100">
              {telemetryState.executionTimeMs}ms
            </div>
            <div className="text-[10px] text-zinc-500 font-mono mt-1">
              {telemetryState.eventsCount} events — {telemetryState.fps} FPS
            </div>
            {telemetryState.currentTool && (
              <div className="text-[10px] text-cyan-glow/70 font-mono mt-0.5 truncate">
                Tool: {telemetryState.currentTool}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ── Projects + Insights Row ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Projects - takes 2 cols */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-zinc-100 tracking-tight flex items-center gap-2">
              <FolderOpen className="w-4 h-4 text-cyan-glow" />
              Projects
              <span className="text-xs font-mono text-zinc-500 font-normal">
                ({workspaceState.projectCount})
              </span>
            </h2>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => workspaceState.loadProjects(true)}
              isLoading={workspaceState.isLoading}
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </Button>
          </div>

          {workspaceState.isOffline && !projects.length ? (
            <Card variant="flat">
              <CardContent>
                <p className="text-sm text-zinc-500 font-mono">Unable to connect to workspace API.</p>
              </CardContent>
            </Card>
          ) : workspaceState.isLoading && projects.length === 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <CardSkeleton />
              <CardSkeleton />
            </div>
          ) : projects.length === 0 ? (
            <Card variant="flat">
              <CardContent>
                <p className="text-sm text-zinc-500 font-mono">No workspace projects discovered.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {projects.map((proj) => (
                <ProjectCard key={proj.path} project={proj} />
              ))}
            </div>
          )}
        </div>

        {/* Insights - takes 1 col */}
        <div className="space-y-4">
          <h2 className="text-lg font-bold text-zinc-100 tracking-tight flex items-center gap-2">
            <Globe className="w-4 h-4 text-cyan-glow" />
            Insights
          </h2>
          <Card variant="default">
            <CardContent>
              {insights.length === 0 ? (
                <p className="text-xs text-zinc-500 font-mono">No insights available.</p>
              ) : (
                <ul className="space-y-2">
                  {insights.map((insight, idx) => (
                    <li key={idx} className="text-xs text-zinc-300 font-mono leading-relaxed flex gap-2">
                      <span className="text-cyan-glow/60 mt-0.5 shrink-0">&#9656;</span>
                      <span>{insight}</span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
            <CardFooter>
              <span className="text-[10px] text-zinc-600 font-mono">
                {insights.length} insight{insights.length !== 1 ? 's' : ''}
              </span>
            </CardFooter>
          </Card>

          {/* Recent Activity */}
          <h2 className="text-lg font-bold text-zinc-100 tracking-tight flex items-center gap-2">
            <Clock className="w-4 h-4 text-cyan-glow" />
            Recent Activity
          </h2>
          <Card variant="default">
            <CardContent>
              {recentMissions.length === 0 ? (
                <p className="text-xs text-zinc-500 font-mono">No recent missions.</p>
              ) : (
                <ul className="space-y-2">
                  {recentMissions.map((m: any) => (
                    <li key={m.id} className="flex items-center justify-between text-xs font-mono">
                      <span className="text-zinc-300 truncate flex-1">{m.name}</span>
                      <span className={`text-[10px] uppercase ml-2 ${
                        m.status === 'COMPLETED' ? 'text-emerald-400' :
                        m.status === 'RUNNING' || m.status === 'ACTIVE' ? 'text-cyan-glow' :
                        m.status === 'FAILED' ? 'text-rose-400' : 'text-zinc-600'
                      }`}>
                        {m.status?.[0] || '?'}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
            <CardFooter>
              <span className="text-[10px] text-zinc-600 font-mono">
                {missionState.missions?.length ?? 0} total missions
              </span>
            </CardFooter>
          </Card>
        </div>
      </div>

      {/* ── Workspace Explorer ── */}
      {projects.length > 0 && (
        <Card variant="default">
          <CardHeader>
            <div className="flex justify-between items-start">
              <CardTitle>Workspace Explorer</CardTitle>
              <FolderTree className="w-4 h-4 text-cyan-glow" />
            </div>
            <CardDescription>{workspaceState.workspaceRoot || 'File tree'}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="max-h-[280px] overflow-y-auto scrollbar-thin">
              {projects.slice(0, 5).map((p) => (
                <ProjectFileTree
                  key={p.path}
                  project={p}
                  onExplain={(entry, project) =>
                    setExplainSubject({
                      kind: entry.type === 'directory' ? 'folder' : 'file',
                      label: entry.name,
                      context: [
                        `Project: ${project.name}`,
                        project.branch ? `Branch: ${project.branch}` : null,
                        `Path: ${entry.path}`,
                        project.technologies?.length ? `Stack: ${project.technologies.join(', ')}` : null,
                      ]
                        .filter(Boolean)
                        .join('\n'),
                    })
                  }
                />
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Tech Distribution + Tool Summary ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card variant="glow">
          <CardHeader>
            <div className="flex justify-between items-start">
              <CardTitle>Tech Distribution</CardTitle>
              <FileCode className="w-4 h-4 text-cyan-glow" />
            </div>
            <CardDescription>Languages across projects</CardDescription>
          </CardHeader>
          <CardContent>
            {projects.length === 0 ? (
              <p className="text-xs text-zinc-500 font-mono">No projects scanned.</p>
            ) : (
              <div className="space-y-2">
                {Array.from(
                  new Set(projects.flatMap((p) => p.technologies ?? []))
                ).map((tech) => {
                  const projCount = projects.filter((p) =>
                    (p.technologies ?? []).includes(tech)
                  ).length;
                  const pct = (projCount / projects.length) * 100;
                  return (
                    <div key={tech} className="flex items-center gap-3 text-xs">
                      <span className="w-20 font-mono text-zinc-300 uppercase text-[10px]">{tech}</span>
                      <div className="flex-1 bg-zinc-900 h-1.5 rounded-full overflow-hidden border border-matte-border">
                        <div
                          className="bg-cyan-glow h-full rounded-full transition-all duration-500"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="w-8 text-right font-mono text-zinc-500 text-[10px]">
                        {projCount}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        <Card variant="glow">
          <CardHeader>
            <div className="flex justify-between items-start">
              <CardTitle>Tool Registry</CardTitle>
              <Blocks className="w-4 h-4 text-cyan-glow" />
            </div>
            <CardDescription>
              {toolsLoading
                ? 'Loading...'
                : toolsError
                  ? 'Failed to load'
                  : `${tools.filter((t) => t.enabled).length}/${tools.length} enabled`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {toolsLoading ? (
              <div className="flex flex-wrap gap-2 animate-pulse">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-8 w-28 rounded-lg bg-zinc-900/50 border border-matte-border" />
                ))}
              </div>
            ) : toolsError ? (
              <div className="flex items-center gap-2 text-xs text-rose-400 font-mono">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                <span>{toolsError}</span>
                <button onClick={loadTools} className="ml-auto text-[10px] underline hover:text-rose-300 cursor-pointer">
                  Retry
                </button>
              </div>
            ) : tools.length === 0 ? (
              <p className="text-xs text-zinc-500 font-mono">No tools registered.</p>
            ) : (
              <div className="space-y-1.5 max-h-[320px] overflow-y-auto scrollbar-thin">
                {tools.map((tool) => {
                  const SvgIcon = categoryToIcon[tool.category] || Blocks;
                  return (
                    <div
                      key={tool.id}
                      className="flex items-center gap-2 px-3 py-2 rounded-lg bg-zinc-950 border border-matte-border hover:border-zinc-700/60 transition-colors"
                    >
                      <SvgIcon className="w-3.5 h-3.5 text-cyan-glow/80 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-mono text-zinc-300 truncate">{tool.name}</span>
                          <span className="text-[9px] font-mono text-zinc-600 uppercase shrink-0">{tool.category}</span>
                        </div>
                      </div>
                      <button
                        onClick={() => toggleToolEnabled(tool.id, !tool.enabled)}
                        className={`relative inline-flex h-4 w-7 shrink-0 items-center rounded-full border transition-colors focus:outline-none cursor-pointer ${
                          tool.enabled
                            ? 'bg-emerald-500/30 border-emerald-500/50'
                            : 'bg-zinc-800 border-zinc-700'
                        }`}
                        aria-label={tool.enabled ? `Disable ${tool.name}` : `Enable ${tool.name}`}
                      >
                        <span
                          className={`inline-block h-2.5 w-2.5 transform rounded-full bg-white shadow-sm transition-transform ${
                            tool.enabled ? 'translate-x-3.5' : 'translate-x-0.5'
                          }`}
                        />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <ExplainPanel
        open={!!explainSubject}
        subject={explainSubject}
        onClose={() => setExplainSubject(null)}
      />
    </div>
  );
};
