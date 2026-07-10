import React from 'react';
import { Users } from 'lucide-react';
import { GlassPanel } from './GlassPanel';
import { StatusPill } from '../widgets/StatusPill';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';
import type { Agent } from '../../data/mock';

const ThinkingDots: React.FC = () => (
  <span className="inline-flex items-center gap-0.5">
    {[0, 1, 2].map((i) => (
      <span
        key={i}
        className="w-1 h-1 rounded-full bg-cyan-glow/80"
        style={{ animation: `cc-blink 1s ease-in-out ${i * 0.18}s infinite` }}
      />
    ))}
  </span>
);

const AgentRow: React.FC<{ agent: Agent }> = ({ agent }) => {
  const Icon = agent.icon;
  const working = agent.status === 'ACTIVE' || agent.status === 'BUSY';
  return (
    <div className="group flex items-center gap-2.5 rounded-xl border border-transparent hover:border-cyan-border/25 hover:bg-white/[0.03] px-2 py-1.5 transition-all">
      <div className="relative w-8 h-8 rounded-lg bg-black/50 border border-cyan-border/30 flex items-center justify-center shrink-0">
        <Icon className="w-4 h-4 text-cyan-glow" />
        {working && <span className="absolute inset-0 rounded-lg bg-cyan-glow/5 blur-sm" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] font-bold text-zinc-100 truncate">{agent.name}</span>
          {working && <ThinkingDots />}
        </div>
        <div className="text-[8.5px] font-mono text-zinc-500 truncate">{agent.role}</div>
      </div>
      <div className="flex flex-col items-end gap-1 shrink-0">
        <StatusPill status={agent.status} />
        <div className="w-14 h-1 rounded-full bg-black/50 overflow-hidden border border-matte-border/60">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${agent.activity}%`,
              background: agent.status === 'IDLE' ? '#52525b' : 'linear-gradient(90deg,#00f2fe,#4db8ff)',
            }}
          />
        </div>
      </div>
    </div>
  );
};

export const ActiveAgentsPanel: React.FC<{ className?: string }> = ({ className }) => {
  const agents = useCommandCenterStore((s) => s.agents);
  return (
    <GlassPanel
      title="Active Agents"
      icon={<Users className="w-3.5 h-3.5" />}
      action={<span className="text-[8px] font-mono text-zinc-500">{agents.filter((a) => a.status !== 'IDLE').length}/{agents.length} active</span>}
      className={className}
      bodyClassName="flex flex-col justify-between h-[calc(100%-2.75rem)] gap-1"
    >
      {agents.map((a) => (
        <AgentRow key={a.id} agent={a} />
      ))}
    </GlassPanel>
  );
};
