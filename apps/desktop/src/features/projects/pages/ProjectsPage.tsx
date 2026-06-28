import React from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../../../components/ui/Card';
import { Button } from '../../../components/ui/Button';
import { FolderGit, GitBranch, Plus, FolderSync } from 'lucide-react';

export const ProjectsPage: React.FC = () => {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-extrabold text-zinc-100 tracking-tight flex items-center gap-3">
            <FolderGit className="w-8 h-8 text-cyan-glow" />
            Projects Workspace
          </h1>
          <p className="font-mono text-xs text-zinc-500 tracking-wider mt-1 uppercase">
            Active repositories synchronized with FRIDAY OS sandbox
          </p>
        </div>
        <Button size="sm">
          <Plus className="w-4 h-4 mr-1.5" />
          Link Repository
        </Button>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        
        {/* Active Project Card */}
        <Card variant="glow" className="flex flex-col justify-between">
          <CardHeader>
            <div className="flex justify-between items-start">
              <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2.5 py-0.5 rounded-full border border-emerald-500/20">ACTIVE</span>
              <span className="text-xs font-mono text-zinc-500">2.4 MB</span>
            </div>
            <CardTitle className="text-xl mt-3">FRIDAY Project</CardTitle>
            <CardDescription className="line-clamp-2">The core foundation of the AI Operating System. Monorepo codebase setup.</CardDescription>
          </CardHeader>
          <CardContent className="mt-4 space-y-3.5">
            <div className="flex items-center gap-2 text-xs font-mono text-zinc-400">
              <GitBranch className="w-4 h-4 text-cyan-glow/80" />
              <span>main</span>
              <span className="text-zinc-600">//</span>
              <span className="text-cyan-glow">origin</span>
            </div>
            <div className="flex items-center gap-2 text-xs font-mono text-zinc-400">
              <FolderSync className="w-4 h-4 text-zinc-500" />
              <span>Path: /home/warlock/ORION</span>
            </div>
          </CardContent>
        </Card>

        {/* Inactive Project Placeholder */}
        <Card variant="default" className="opacity-70 hover:opacity-100 transition-opacity">
          <CardHeader>
            <div className="flex justify-between items-start">
              <span className="text-[10px] font-mono text-zinc-500 bg-zinc-800/40 px-2.5 py-0.5 rounded-full border border-matte-border">ARCHIVED</span>
              <span className="text-xs font-mono text-zinc-500">12.5 MB</span>
            </div>
            <CardTitle className="text-xl mt-3">Hyper-LLM Middleware</CardTitle>
            <CardDescription>Python-based local model router, custom proxy gateway configs.</CardDescription>
          </CardHeader>
          <CardContent className="mt-4 space-y-3.5">
            <div className="flex items-center gap-2 text-xs font-mono text-zinc-500">
              <GitBranch className="w-4 h-4" />
              <span>stable-v2</span>
            </div>
            <div className="flex items-center gap-2 text-xs font-mono text-zinc-500">
              <FolderSync className="w-4 h-4" />
              <span>Path: /home/warlock/hyper-middleware</span>
            </div>
          </CardContent>
        </Card>

        {/* Empty state link card */}
        <div className="border border-dashed border-matte-border rounded-2xl flex flex-col justify-center items-center p-8 text-center bg-black/10 hover:border-cyan-border/30 transition-all hover:bg-black/20 group cursor-pointer min-h-[220px]">
          <div className="w-10 h-10 rounded-xl bg-zinc-950 border border-matte-border flex items-center justify-center text-zinc-500 group-hover:text-cyan-glow group-hover:border-cyan-border/50 transition-colors mb-4">
            <FolderGit className="w-5 h-5" />
          </div>
          <h3 className="text-sm font-semibold text-zinc-300 group-hover:text-zinc-100 transition-colors">Import Project</h3>
          <p className="text-xs text-zinc-500 font-mono mt-1 max-w-[200px] leading-relaxed">Map local Git projects to let FRIDAY index codebases.</p>
        </div>

      </div>
    </div>
  );
};
