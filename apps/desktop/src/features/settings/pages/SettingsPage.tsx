import React from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../../../components/ui/Card';
import { Button } from '../../../components/ui/Button';
import { Input } from '../../../components/ui/Input';
import { Settings, Shield, Network, User } from 'lucide-react';

export const SettingsPage: React.FC = () => {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-extrabold text-zinc-100 tracking-tight flex items-center gap-3">
          <Settings className="w-8 h-8 text-cyan-glow" />
          Settings Panel
        </h1>
        <p className="font-mono text-xs text-zinc-500 tracking-wider mt-1 uppercase">
          Configure core parameters of the FRIDAY AI Operating System
        </p>
      </div>

      {/* Settings Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Side: General Form */}
        <div className="lg:col-span-2 space-y-6">
          <Card variant="glow">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <User className="w-4 h-4 text-cyan-glow" />
                <span>Admin Profile</span>
              </CardTitle>
              <CardDescription>Configure user identity for agent conversations</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input label="Admin Name" defaultValue="Harsh" />
                <Input label="Workspace Title" defaultValue="Project FRIDAY" />
              </div>
              <Button size="sm">Save Configuration</Button>
            </CardContent>
          </Card>

          <Card variant="default">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Network className="w-4 h-4 text-cyan-glow" />
                <span>Network & Sandbox Security</span>
              </CardTitle>
              <CardDescription>Port mappings and communication settings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Input label="Secure Handshake Port" defaultValue="9000" />
                <Input label="System Daemon Host" defaultValue="localhost" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Side: Options list */}
        <div className="space-y-6">
          <Card variant="default">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-cyan-glow" />
                <span>Sandbox Security</span>
              </CardTitle>
              <CardDescription>Safety configurations</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 font-mono text-xs text-zinc-400">
              <div className="flex justify-between items-center border-b border-matte-border/30 pb-2">
                <span>LOCAL FILE READS:</span>
                <span className="text-emerald-400 font-bold">ALLOWED</span>
              </div>
              <div className="flex justify-between items-center border-b border-matte-border/30 pb-2">
                <span>SYSTEM WRITES:</span>
                <span className="text-amber-400 font-bold">PROMPTED</span>
              </div>
              <div className="flex justify-between items-center">
                <span>SANDBOX ISOLATION:</span>
                <span className="text-zinc-200">CONTAINER LEVEL</span>
              </div>
            </CardContent>
          </Card>
        </div>

      </div>
    </div>
  );
};
