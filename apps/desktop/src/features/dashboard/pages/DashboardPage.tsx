import React from 'react';
import { Hero } from '../../../components/Hero';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../../../components/ui/Card';
import { Cpu, Database, Blocks, HardDrive } from 'lucide-react';

export const DashboardPage: React.FC = () => {
  return (
    <div className="space-y-8 animate-fade-in">
      {/* Dynamic Brand Hero */}
      <Hero />

      {/* Auxiliary telemetry cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mt-8">
        <Card variant="glow">
          <CardHeader>
            <div className="flex justify-between items-start">
              <CardTitle>Memory Allocation</CardTitle>
              <Database className="w-4 h-4 text-cyan-glow" />
            </div>
            <CardDescription>Vector DB capacity</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold tracking-tight text-zinc-100">1.24 GB / 10 GB</div>
            <div className="w-full bg-zinc-900 h-1.5 rounded-full mt-3 overflow-hidden border border-matte-border">
              <div className="bg-cyan-glow h-full rounded-full w-[12%]" />
            </div>
          </CardContent>
        </Card>

        <Card variant="default">
          <CardHeader>
            <div className="flex justify-between items-start">
              <CardTitle>Plugin Registry</CardTitle>
              <Blocks className="w-4 h-4 text-cyan-glow" />
            </div>
            <CardDescription>Active micro-plugins</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold tracking-tight text-zinc-100">12 Enabled</div>
            <div className="text-[10px] text-zinc-500 font-mono mt-1">ALL INTEGRATIONS SECURED</div>
          </CardContent>
        </Card>

        <Card variant="default">
          <CardHeader>
            <div className="flex justify-between items-start">
              <CardTitle>Core Utilization</CardTitle>
              <Cpu className="w-4 h-4 text-cyan-glow" />
            </div>
            <CardDescription>Multi-agent processing</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold tracking-tight text-zinc-100">2.4%</div>
            <div className="text-[10px] text-zinc-500 font-mono mt-1">4 ACTIVE AGENT WORKERS</div>
          </CardContent>
        </Card>

        <Card variant="glow">
          <CardHeader>
            <div className="flex justify-between items-start">
              <CardTitle>Sandbox Cache</CardTitle>
              <HardDrive className="w-4 h-4 text-cyan-glow" />
            </div>
            <CardDescription>Local project context</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold tracking-tight text-zinc-100">412.5 MB</div>
            <div className="w-full bg-zinc-900 h-1.5 rounded-full mt-3 overflow-hidden border border-matte-border">
              <div className="bg-cyan-glow h-full rounded-full w-[45%]" />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
