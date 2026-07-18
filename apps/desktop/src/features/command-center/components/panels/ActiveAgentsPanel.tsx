import React, { useEffect, useState } from 'react';
import { Users, Shield, BookOpen, BarChart3, Radio } from 'lucide-react';
import { GlassPanel } from './GlassPanel';
import { StatusPill } from '../widgets/StatusPill';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';
import { useAiStateStore } from '../../sync/useAiStateStore';
import type { Agent } from '../../data/mock';

const ThinkingDots: React.FC = () => (
  <span className="inline-flex items-center gap-0.5 ml-1">
    {[0, 1, 2].map((i) => (
      <span
        key={i}
        className="w-1 h-1 rounded-full bg-emerald-400"
        style={{ animation: `cc-blink 1.2s ease-in-out ${i * 0.2}s infinite` }}
      />
    ))}
  </span>
);

const AGENT_THEMES: Record<string, { bg: string; border: string; text: string; iconColor: string; defaultIcon: React.ComponentType<any> }> = {
  orion: { bg: 'bg-purple-950/45', border: 'border-purple-500/35', text: 'text-purple-400', iconColor: '#c084fc', defaultIcon: Shield },
  atlas: { bg: 'bg-cyan-950/45', border: 'border-cyan-500/35', text: 'text-cyan-400', iconColor: '#38bdf8', defaultIcon: BookOpen },
  nova: { bg: 'bg-slate-900/60', border: 'border-slate-700/40', text: 'text-zinc-400', iconColor: '#94a3b8', defaultIcon: BarChart3 },
  echo: { bg: 'bg-orange-950/45', border: 'border-orange-500/35', text: 'text-orange-400', iconColor: '#fb923c', defaultIcon: Radio },
};

const formatRuntime = (totalSecs: number) => {
  const mins = Math.floor(totalSecs / 60);
  const secs = totalSecs % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
};

const AgentRow: React.FC<{ agent: Agent; working: boolean; runtime: number; aiState: string }> = ({ 
  agent, working, runtime, aiState 
}) => {
  const theme = AGENT_THEMES[agent.id] || {
    bg: 'bg-black/50',
    border: 'border-cyan-border/30',
    text: 'text-cyan-glow',
    iconColor: '#00f2fe',
    defaultIcon: Shield,
  };
  const Icon = theme.defaultIcon;
  const statusActive = agent.status === 'ACTIVE' || agent.status === 'BUSY';

  // Compute status description override
  let labelOverride = undefined;
  if (agent.status === 'IDLE') {
    labelOverride = 'Waiting';
  } else if (agent.status === 'ACTIVE' || agent.status === 'BUSY') {
    if (aiState === 'thinking') labelOverride = 'Planning';
    else if (aiState === 'executing' || aiState === 'tool' || aiState === 'workflow') labelOverride = 'Executing';
    else if (aiState === 'speaking') labelOverride = 'Reflecting';
    else labelOverride = 'Executing';
  }

  return (
    <div
      className={`group flex items-center gap-3 rounded-lg border px-2.5 py-1.5 transition-all duration-300 ${
        working
          ? 'border-cyan-border/50 bg-cyan-glow/5 shadow-[0_0_12px_rgba(0,242,254,0.15)]'
          : 'border-transparent hover:border-zinc-800 hover:bg-white/[0.02]'
      }`}
    >
      {/* Avatar Container */}
      <div 
        className={`relative w-8 h-8 rounded-lg ${theme.bg} border ${theme.border} flex items-center justify-center shrink-0`}
        style={{ boxShadow: statusActive ? `0 0 10px ${theme.iconColor}20` : 'none' }}
      >
        <Icon className="w-4 h-4" style={{ color: theme.iconColor }} />
        {statusActive && <span className="absolute inset-0 rounded-lg animate-pulse-glow" style={{ backgroundColor: `${theme.iconColor}08` }} />}
      </div>

      {/* Info details */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1 leading-none">
          <span className="text-[10px] font-bold text-zinc-100 truncate">{agent.name}</span>
          {statusActive && <ThinkingDots />}
        </div>
        
        {/* Current activity readout */}
        <div className="text-[7.5px] font-mono text-zinc-400 truncate mt-0.5" style={{ color: statusActive ? theme.iconColor : '' }}>
          {agent.task}
        </div>
        
        {/* Active task details */}
        <div className="text-[6.5px] font-mono text-zinc-600 truncate mt-0.5">
          Role: {agent.role}
        </div>
      </div>

      {/* Status & Stopwatch Runtime */}
      <div className="flex flex-col items-end gap-1 shrink-0 text-right">
        <StatusPill status={agent.status} labelOverride={labelOverride} />
        
        {/* Stopwatch indicator */}
        <span className={`text-[8.5px] font-mono font-semibold tabular-nums mt-0.5 ${statusActive ? 'text-zinc-300' : 'text-zinc-600'}`}>
          {statusActive ? formatRuntime(runtime) : '--:--'}
        </span>

        {/* Dynamic progress slider */}
        <div className="w-14 h-1 rounded-full bg-black/45 overflow-hidden border border-zinc-900 mt-0.5">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{ 
              width: `${agent.activity}%`, 
              backgroundColor: agent.status === 'IDLE' ? '#3f3f46' : theme.iconColor 
            }}
          />
        </div>
      </div>
    </div>
  );
};

export const ActiveAgentsPanel: React.FC<{ className?: string }> = ({ className }) => {
  const agents = useCommandCenterStore((s) => s.agents);
  const aiState = useAiStateStore((s) => s.state);

  // Keep tracking local stopwatch times in seconds for each agent
  const [runtimes, setRuntimes] = useState<Record<string, number>>({
    orion: 132,
    atlas: 84,
    nova: 0,
    echo: 485,
  });

  useEffect(() => {
    const interval = setInterval(() => {
      setRuntimes((prev) => {
        const next = { ...prev };
        agents.forEach((a) => {
          if (a.status === 'ACTIVE' || a.status === 'BUSY') {
            next[a.id] = (next[a.id] || 0) + 1;
          }
        });
        return next;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [agents]);

  const busy = aiState === 'executing' || aiState === 'tool' || aiState === 'workflow';
  const workingId = busy
    ? agents.reduce<Agent | null>((best, a) => ((best ? a.activity > best.activity : true) ? a : best), null)?.id
    : null;

  return (
    <GlassPanel
      title={`Active Agents (${agents.length})`}
      icon={<Users className="w-3.5 h-3.5" />}
      live
      liveColor="green"
      className={className}
      bodyClassName="flex flex-col gap-2 h-[calc(100%-2.75rem)]"
    >
      <div className="flex flex-col gap-1.5 justify-between h-full">
        {agents.map((a) => (
          <AgentRow 
            key={a.id} 
            agent={a} 
            working={a.id === workingId} 
            runtime={runtimes[a.id] || 0}
            aiState={aiState}
          />
        ))}
      </div>
    </GlassPanel>
  );
};
