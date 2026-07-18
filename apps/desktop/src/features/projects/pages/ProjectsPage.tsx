import React, { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../../../components/ui/Card';
import { Button } from '../../../components/ui/Button';
import { WorkspaceMiniGraph } from '../../../components/ui/WorkspaceMiniGraph';
import type { FileEntry } from '../../../components/ui/WorkspaceMiniGraph';
import { ExplainPanel } from '../../../components/ui/ExplainPanel';
import type { ExplainSubject } from '../../../components/ui/ExplainPanel';
import type { WorkspaceProject } from '../../../services/api/workspaceApi';
import { useWorkspaceStore } from '../../../store/useWorkspaceStore';
import { FolderGit, GitBranch, Plus, FolderOpen, FileCode, Box, Zap, ChevronRight } from 'lucide-react';

function buildFileTree(project: WorkspaceProject): FileEntry {
  const stats = project.graph_stats;
  const extChildren: FileEntry[] = stats?.files_by_extension
    ? Object.entries(stats.files_by_extension).map(([ext, count]) => ({
        name: `${ext} files (${count})`,
        path: `${project.path}/files${ext}`,
        type: 'file' as const,
        extension: ext,
        language: ext.replace('.', ''),
      }))
    : [];

  return {
    name: project.name,
    path: project.path,
    type: 'directory',
    children: [
      ...(stats
        ? [
            { name: `src/ (${stats.total_files} files)`, path: `${project.path}/src`, type: 'directory' as const, children: extChildren },
            { name: `modules/ (${stats.total_modules})`, path: `${project.path}/modules`, type: 'directory' as const },
          ]
        : [{ name: 'Not yet scanned', path: project.path + '/unknown', type: 'file' as const }]),
    ],
  };
}

function subjectForEntry(entry: FileEntry, project: WorkspaceProject): ExplainSubject {
  const kind = entry.type === 'directory' ? 'folder' : 'file';
  return {
    kind,
    label: entry.name,
    context: [
      `Project: ${project.name}`,
      project.branch ? `Branch: ${project.branch}` : null,
      `Path: ${entry.path}`,
      entry.language ? `Language: ${entry.language}` : null,
      project.technologies?.length ? `Stack: ${project.technologies.join(', ')}` : null,
    ]
      .filter(Boolean)
      .join('\n'),
  };
}

export const ProjectsPage: React.FC = () => {
  const { projects, workspaceRoot, isOffline, isLoading, loadProjects, activeFilePath, setActiveFile, setCurrentProject } = useWorkspaceStore();
  const [explainSubject, setExplainSubject] = useState<ExplainSubject | null>(null);

  useEffect(() => {
    if (projects.length === 0) loadProjects();
  }, [loadProjects, projects.length]);

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-extrabold text-zinc-100 tracking-tight flex items-center gap-3">
            <FolderGit className="w-8 h-8 text-cyan-glow" />
            Projects Workspace
          </h1>
          <p className="font-mono text-xs text-zinc-500 tracking-wider mt-1 uppercase">
            {isOffline
              ? 'Offline — cannot reach workspace API'
              : `${projects.length} repositories synchronized${workspaceRoot ? ` · ${workspaceRoot}` : ''}`}
          </p>
        </div>
        <Button size="sm">
          <Plus className="w-4 h-4 mr-1.5" />
          Link Repository
        </Button>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Project Cards */}
        <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-6">
          {projects.slice(0, 4).map((project) => {
            const stats = project.graph_stats;
            return (
              <Card key={project.path} variant="default" hoverable>
                <CardHeader>
                  <div className="flex justify-between items-start">
                    <span className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full border ${
                      project.is_git
                        ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
                        : 'text-zinc-500 bg-zinc-800/40 border-matte-border'
                    }`}>
                      {project.is_git ? 'ACTIVE' : 'LOCAL'}
                    </span>
                    <button
                      onClick={() =>
                        setExplainSubject({
                          kind: 'module',
                          label: project.name,
                          context: subjectForEntry(buildFileTree(project), project).context,
                        })
                      }
                      className="text-[9px] font-mono uppercase tracking-widest text-zinc-500 hover:text-cyan-glow transition-colors"
                    >
                      Explain
                    </button>
                  </div>
                  <CardTitle className="text-xl mt-3">{project.name}</CardTitle>
                  <CardDescription className="line-clamp-2">{project.path}</CardDescription>
                </CardHeader>
                <CardContent className="mt-4 space-y-3.5">
                  {project.is_git && project.branch && (
                    <div className="flex items-center gap-2 text-xs font-mono text-zinc-400">
                      <GitBranch className="w-4 h-4 text-cyan-glow/80" />
                      <span>{project.branch}</span>
                    </div>
                  )}
                  {stats && (
                    <div className="grid grid-cols-2 gap-2 text-xs font-mono">
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
                  )}
                  <div className="flex flex-wrap gap-1.5">
                    {project.technologies?.map((t: string) => (
                      <span key={t}
                        className="text-[9px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full
                                   bg-cyan-glow/5 border border-cyan-border/20 text-cyan-glow/80"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </CardContent>
              </Card>
            );
          })}

          {isLoading && (
            <Card variant="flat">
              <CardContent>
                <p className="text-xs text-zinc-500 font-mono animate-pulse">Scanning projects...</p>
              </CardContent>
            </Card>
          )}

          {/* Import placeholder */}
          <div className="border border-dashed border-matte-border rounded-2xl flex flex-col justify-center items-center p-8 text-center bg-black/10 hover:border-cyan-border/30 transition-all hover:bg-black/20 group cursor-pointer min-h-[220px]">
            <div className="w-10 h-10 rounded-xl bg-zinc-950 border border-matte-border flex items-center justify-center text-zinc-500 group-hover:text-cyan-glow group-hover:border-cyan-border/50 transition-colors mb-4">
              <FolderGit className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-semibold text-zinc-300 group-hover:text-zinc-100 transition-colors">Import Project</h3>
            <p className="text-xs text-zinc-500 font-mono mt-1 max-w-[200px] leading-relaxed">Map local Git projects to let FRIDAY index codebases.</p>
          </div>
        </div>

        {/* Workspace Explorer sidebar */}
        <div className="space-y-4">
          <h2 className="text-lg font-bold text-zinc-100 tracking-tight flex items-center gap-2">
            <FolderOpen className="w-4 h-4 text-cyan-glow" />
            Explorer
          </h2>
          <Card variant="default">
            <CardContent className="p-0">
              {projects.length === 0 ? (
                <div className="p-6 text-xs text-zinc-500 font-mono text-center">No projects scanned yet.</div>
              ) : (
                <div className="max-h-[500px] overflow-y-auto scrollbar-thin p-3">
                  {projects.slice(0, 3).map((project) => (
                    <div key={project.path}>
                      <div className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider px-2 py-2 font-bold">
                        {project.name}
                      </div>
                      <WorkspaceMiniGraph
                        files={[buildFileTree(project)]}
                        projectName={project.name}
                        activePath={activeFilePath ?? undefined}
                        onFileClick={(entry) => {
                          if (entry.type === 'file') {
                            setActiveFile(entry.path);
                            setCurrentProject(project.path);
                          }
                        }}
                        onExplain={(entry) => setExplainSubject(subjectForEntry(entry, project))}
                      />
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
          <p className="text-[10px] font-mono text-zinc-600 px-1 leading-relaxed">
            Tip: hover a file and click the spark icon to have FRIDAY explain it.
          </p>
        </div>
      </div>

      <ExplainPanel
        open={!!explainSubject}
        subject={explainSubject}
        onClose={() => setExplainSubject(null)}
      />
    </div>
  );
};
