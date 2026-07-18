import React from 'react';
import { Terminal, Plus, FileCode, SearchCode, Cpu, ClipboardList, Settings } from 'lucide-react';
import { GlassPanel } from './GlassPanel';
import { useAiStateStore } from '../../sync/useAiStateStore';
import { useSystemStore } from '../../../../store/useSystemStore';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';

export const SystemCommandsPanel: React.FC<{ className?: string }> = ({ className }) => {
  const transition = useAiStateStore((s) => s.transition);
  const addLog = useSystemStore((s) => s.addLog);
  const setActiveWorkspace = useCommandCenterStore((s) => s.setActiveWorkspace);

  const triggerScan = () => {
    addLog('Initiating full neural diagnostic scan...', 'info');
    transition('thinking');
    setTimeout(() => {
      addLog('Neural diagnostic scan complete: 0 faults detected.', 'success');
      transition('idle');
    }, 3500);
  };

  const triggerOptimize = () => {
    addLog('Optimizing resource distribution schedules...', 'info');
    transition('executing');
    setTimeout(() => {
      addLog('Optimization complete. CPU and Memory alignment refreshed.', 'success');
      transition('idle');
    }, 3500);
  };

  const triggerNewTask = () => {
    addLog('Awaiting prompt injection sequence...', 'warn');
    transition('listening');
  };

  const triggerOpenFile = () => {
    addLog('Opening file system explorer context...', 'info');
    setActiveWorkspace('command');
  };

  const triggerReport = () => {
    addLog('Generating executive intelligence telemetry report...', 'info');
    setTimeout(() => {
      addLog('Telemetry report written to artifacts workspace.', 'success');
    }, 1500);
  };

  const triggerSettings = () => {
    addLog('Navigating to Settings panel config workspace.', 'info');
    setActiveWorkspace('settings');
  };

  const commands = [
    { label: 'New Task', icon: Plus, action: triggerNewTask },
    { label: 'Open File', icon: FileCode, action: triggerOpenFile },
    { label: 'System Scan', icon: SearchCode, action: triggerScan, primary: true },
    { label: 'Optimize', icon: Cpu, action: triggerOptimize, primary: true },
    { label: 'Generate Report', icon: ClipboardList, action: triggerReport },
    { label: 'Settings', icon: Settings, action: triggerSettings },
  ];

  return (
    <GlassPanel
      title="System Commands"
      icon={<Terminal className="w-3.5 h-3.5" />}
      className={className}
      bodyClassName="h-[calc(100%-2.75rem)] flex items-center"
    >
      <div className="grid grid-cols-2 gap-2 w-full">
        {commands.map((cmd) => (
          <button
            key={cmd.label}
            onClick={cmd.action}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-left font-mono text-[9px] uppercase tracking-wider border transition-all duration-300 ${
              cmd.primary
                ? 'bg-cyan-glow/5 border-cyan-border/45 hover:border-cyan-glow text-cyan-glow hover:bg-cyan-glow/15 shadow-[0_0_8px_rgba(0,242,254,0.05)]'
                : 'bg-black/35 border-zinc-800/80 hover:border-zinc-700/80 text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <cmd.icon className={`w-3.5 h-3.5 ${cmd.primary ? 'text-cyan-glow' : 'text-zinc-500 group-hover:text-zinc-300'}`} />
            <span className="truncate">{cmd.label}</span>
          </button>
        ))}
      </div>
    </GlassPanel>
  );
};
