import React from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../../../components/ui/Card';
import { Button } from '../../../components/ui/Button';
import { Brain, ShieldAlert } from 'lucide-react';

export const MemoryPage: React.FC = () => {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-extrabold text-zinc-100 tracking-tight flex items-center gap-3">
            <Brain className="w-8 h-8 text-cyan-glow" />
            Vector Memory Store
          </h1>
          <p className="font-mono text-xs text-zinc-500 tracking-wider mt-1 uppercase">
            Manage long-term semantic context & codebase embeddings
          </p>
        </div>
        <Button variant="outline" size="sm">
          Optimize Store
        </Button>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Side: Summary metrics */}
        <div className="lg:col-span-2 space-y-6">
          <Card variant="glow">
            <CardHeader>
              <CardTitle>Memory Collections</CardTitle>
              <CardDescription>Indexes loaded into local active RAM</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs font-mono">
                  <thead>
                    <tr className="border-b border-matte-border text-zinc-500 pb-3">
                      <th className="py-2.5">Collection ID</th>
                      <th>Dimensions</th>
                      <th>Documents</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-matte-border/30 text-zinc-300">
                    <tr>
                      <td className="py-3 text-cyan-glow font-bold">friday-core-docs</td>
                      <td>1536</td>
                      <td>4,212</td>
                      <td>
                        <span className="text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/25">ACTIVE</span>
                      </td>
                    </tr>
                    <tr>
                      <td className="py-3 text-cyan-glow font-bold">project-friday-code</td>
                      <td>1536</td>
                      <td>12,940</td>
                      <td>
                        <span className="text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/25">ACTIVE</span>
                      </td>
                    </tr>
                    <tr>
                      <td className="py-3 text-cyan-glow font-bold">harsh-personal-context</td>
                      <td>768</td>
                      <td>142</td>
                      <td>
                        <span className="text-zinc-500 bg-zinc-500/10 px-2 py-0.5 rounded-full border border-zinc-700">STANDBY</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Side: Telemetry details */}
        <div className="space-y-6">
          <Card variant="default">
            <CardHeader>
              <CardTitle>Vector Database Engine</CardTitle>
              <CardDescription>Telemetry diagnostics</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 font-mono text-xs text-zinc-400">
              <div className="flex justify-between border-b border-matte-border/30 pb-2">
                <span>ENGINE:</span>
                <span className="text-zinc-200">ChromaDB Embedded</span>
              </div>
              <div className="flex justify-between border-b border-matte-border/30 pb-2">
                <span>TOTAL EMBEDDINGS:</span>
                <span className="text-zinc-200">17,294</span>
              </div>
              <div className="flex justify-between border-b border-matte-border/30 pb-2">
                <span>COMPACTION INTEGRITY:</span>
                <span className="text-emerald-400 font-bold">99.8%</span>
              </div>
              <div className="flex justify-between">
                <span>LOCAL CACHE:</span>
                <span className="text-zinc-200">Enabled</span>
              </div>
            </CardContent>
          </Card>

          <Card variant="flat" className="border-rose-500/15 bg-rose-500/5">
            <CardHeader className="pb-2">
              <div className="flex gap-2.5 items-center text-rose-400">
                <ShieldAlert className="w-5 h-5" />
                <CardTitle className="text-rose-400">Memory Pressure Alert</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-rose-300 leading-normal font-mono">
                No active memory pressure. System status remains within nominal thresholds.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};
