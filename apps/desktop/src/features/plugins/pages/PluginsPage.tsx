import React from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../../../components/ui/Card';
import { Button } from '../../../components/ui/Button';
import { Blocks, ToggleLeft, ToggleRight, Sparkles, ShoppingBag } from 'lucide-react';

export const PluginsPage: React.FC = () => {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-extrabold text-zinc-100 tracking-tight flex items-center gap-3">
            <Blocks className="w-8 h-8 text-cyan-glow" />
            Plugin Registry
          </h1>
          <p className="font-mono text-xs text-zinc-500 tracking-wider mt-1 uppercase">
            Extend FRIDAY OS capabilities with custom neural plugins
          </p>
        </div>
        <Button variant="outline" size="sm">
          <ShoppingBag className="w-4 h-4 mr-1.5" />
          Browse Plugin Store
        </Button>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Plugin 1 */}
        <Card variant="glow">
          <CardHeader>
            <div className="flex justify-between items-start">
              <div className="flex gap-3 items-center">
                <div className="w-8 h-8 rounded-lg bg-black border border-cyan-border/40 flex items-center justify-center text-cyan-glow">
                  <Sparkles className="w-4.5 h-4.5" />
                </div>
                <div>
                  <CardTitle>Gemini Co-pilot</CardTitle>
                  <CardDescription className="mt-0.5">v1.2.0 // DeepMind</CardDescription>
                </div>
              </div>
              <ToggleRight className="w-8 h-8 text-cyan-glow cursor-pointer" />
            </div>
          </CardHeader>
          <CardContent className="mt-2 text-xs text-zinc-400 font-mono">
            Integrates advanced Gemini models directly into code execution sandboxes, offering real-time debugging instructions.
          </CardContent>
        </Card>

        {/* Plugin 2 */}
        <Card variant="default">
          <CardHeader>
            <div className="flex justify-between items-start">
              <div className="flex gap-3 items-center">
                <div className="w-8 h-8 rounded-lg bg-zinc-950 border border-matte-border flex items-center justify-center text-zinc-400">
                  <Blocks className="w-4.5 h-4.5" />
                </div>
                <div>
                  <CardTitle>Docker Control</CardTitle>
                  <CardDescription className="mt-0.5">v0.8.4 // FRIDAY Core</CardDescription>
                </div>
              </div>
              <ToggleLeft className="w-8 h-8 text-zinc-600 cursor-pointer" />
            </div>
          </CardHeader>
          <CardContent className="mt-2 text-xs text-zinc-400 font-mono">
            Enables agent commands to spawn, inspect, and monitor containerized sandbox environments safely on the user system.
          </CardContent>
        </Card>

      </div>
    </div>
  );
};
