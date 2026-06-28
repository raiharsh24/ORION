import React from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../../../components/ui/Card';
import { Button } from '../../../components/ui/Button';
import { useSystemStore } from '../../../store/useSystemStore';
import { Terminal, Code, Wrench, PlayCircle, ShieldCheck, RefreshCw } from 'lucide-react';

export const DeveloperPage: React.FC = () => {
  const { logs, clearLogs, addLog } = useSystemStore();

  const handleClearLogs = () => {
    clearLogs();
    addLog("System telemetry logs cleared.", "warn");
  };

  return (
    <div className="space-y-8 select-none">
      {/* Page Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-extrabold text-zinc-100 tracking-tight flex items-center gap-3">
            <Terminal className="w-8 h-8 text-cyan-glow" />
            Developer Sandbox
          </h1>
          <p className="font-mono text-xs text-zinc-500 tracking-wider mt-1 uppercase">
            Build actions, environmental control panel, and terminal logs
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleClearLogs} className="h-8 font-mono text-[10px] tracking-wider">
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
          CLEAR CONSOLE
        </Button>
      </div>

      {/* Grid of config & commands */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Environment Settings Card */}
        <Card variant="glow" className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Environment Profiles</CardTitle>
            <CardDescription>Configure local agent environments & API endpoints</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-4">
              {[
                { name: 'FRIDAY_MODEL_PROVIDER', val: 'Gemini 1.5 Flash (v0.4)' },
                { name: 'FRIDAY_WORKSPACE_DIR', val: '/home/warlock/ORION' },
                { name: 'SECURE_LINK_PORT', val: '8000' },
              ].map((env, i) => (
                <div key={i} className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 bg-black/40 border border-matte-border/60 rounded-xl font-mono text-xs">
                  <span className="text-cyan-glow/85 font-semibold">{env.name}</span>
                  <span className="text-zinc-400 break-all">{env.val}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* System Scripts Card */}
        <div className="space-y-6">
          <Card variant="default">
            <CardHeader>
              <CardTitle>Core Commands</CardTitle>
              <CardDescription>Quick scripts</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button variant="outline" size="sm" className="w-full justify-start gap-2.5">
                <PlayCircle className="w-4 h-4 text-cyan-glow" />
                <span>Build Workspaces</span>
              </Button>
              <Button variant="outline" size="sm" className="w-full justify-start gap-2.5">
                <Wrench className="w-4 h-4 text-cyan-glow" />
                <span>Run Linter Suite</span>
              </Button>
              <Button variant="outline" size="sm" className="w-full justify-start gap-2.5">
                <Code className="w-4 h-4 text-cyan-glow" />
                <span>Update Embeddings</span>
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Real-time System Logs Console Panel */}
        <Card variant="glow" className="lg:col-span-3">
          <CardHeader className="pb-2 border-b border-matte-border/30 bg-black/20">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-cyan-glow">
                <ShieldCheck className="w-4 h-4" />
                <CardTitle>Active System Console Logs</CardTitle>
              </div>
              <span className="font-mono text-[9px] text-zinc-500 uppercase tracking-widest">LIVE DATA FEED</span>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="bg-black/80 font-mono text-xs p-5 max-h-[300px] min-h-[160px] overflow-y-auto scrollbar-thin select-text">
              {logs.length === 0 ? (
                <div className="text-center py-8 text-zinc-600 uppercase tracking-widest text-[10px]">
                  CONSOLE IDLE // NO NEW EMISSIONS
                </div>
              ) : (
                logs.map((log) => (
                  <div key={log.id} className="flex items-start gap-4 mb-2.5 leading-relaxed">
                    <span className="text-zinc-600 text-[10px] select-none">{log.timestamp}</span>
                    <span className={`px-2 py-0.5 rounded text-[9px] uppercase font-bold select-none border flex-shrink-0
                      ${log.type === 'error' ? 'bg-rose-950/40 border-rose-500/20 text-rose-400' :
                        log.type === 'success' ? 'bg-cyan-950/40 border-cyan-500/20 text-cyan-glow' :
                        log.type === 'warn' ? 'bg-amber-950/40 border-amber-500/20 text-amber-400' :
                        'bg-zinc-900 border-matte-border text-zinc-400'}`}
                    >
                      {log.type}
                    </span>
                    <span className={`flex-1 break-all 
                      ${log.type === 'error' ? 'text-rose-300' :
                        log.type === 'success' ? 'text-cyan-200' :
                        log.type === 'warn' ? 'text-amber-200' :
                        'text-zinc-300'}`}
                    >
                      {log.message}
                    </span>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

      </div>
    </div>
  );
};
