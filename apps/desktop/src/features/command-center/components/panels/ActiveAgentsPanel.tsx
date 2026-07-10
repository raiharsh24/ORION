import React from 'react';
import { Users } from 'lucide-react';
import { GlassPanel } from './GlassPanel';
import { StatusPill } from '../widgets/StatusPill';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';
import { useAiStateStore } from '../../sync/useAiStateStore';
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

const AgentRow: React.FC<{ agent: Agent; working: boolean }> = ({ agent, working }) => {
  const Icon = agent.icon;
  const statusActive = agent.status === 'ACTIVE' || agent.status === 'BUSY';
  return (
    <div
      className={`group flex items-center gap-2.5 rounded-xl border px-2 py-1.5 transition-all ${
        working
          ? 'border-cyan-border/60 bg-cyan-glow/5 shadow-[0_0_16px_rgba(0,242,254,0.25)]'
          : 'border-transparent hover:border-cyan-border/25 hover:bg-white/[0.03]'
      }`}
    >
      <div className="relative w-8 h-8 rounded-lg bg-black/50 border border-cyan-border/30 flex items-center justify-center shrink-0">
        <Icon className="w-4 h-4 text-cyan-glow" />
        {(statusActive || working) && <span className="absolute inset-0 rounded-lg bg-cyan-glow/5 blur-sm" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] font-bold text-zinc-100 truncate">{agent.name}</span>
          {statusActive && <ThinkingDots />}
          {working && <span className="text-[6.5px] font-mono uppercase tracking-[0.2em] text-cyan-glow/80">exec</span>}
        </div>
        <div className="text-[8.5px] font-mono text-zinc-500 truncate">{agent.role}</div>
        {working && (
          <div className="mt-1 h-1 rounded-full bg-black/50 overflow-hidden border border-matte-border/60">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${agent.activity}%`, background: 'linear-gradient(90deg,#00f2fe,#4db8ff)' }}
            />
          </div>
        )}
      </div>
      <div className="flex flex-col items-end gap-1 shrink-0">
        <StatusPill status={agent.status} />
        <div className="w-14 h-1 rounded-full bg-black/50 overflow-hidden border border-matte-border/60">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{ width: `${agent.activity}%`, background: agent.status === 'IDLE' ? '#52525b' : 'linear-gradient(90deg,#00f2fe,#4db8ff)' }}
          />
        </div>
      </div>
    </div>
  );
};

export const ActiveAgentsPanel: React.FC<{ className?: string }> = ({ className }) => {
  const agents = useCommandCenterStore((s) => s.agents);
  const aiState = useAiStateStore((s) => s.state);

  const busy = aiState === 'executing' || aiState === 'tool' || aiState === 'workflow';
  const workingId = busy
    ? agents.reduce<Agent | null>((best, a) => ((best ? a.activity > best.activity : true) ? a : best), null)?.id
    : null;

  return (
    <GlassPanel
      title="Active Agents"
      icon={<Users className="w-3.5 h-3.5" />}
      action={<span className="text-[8px] font-mono text-zinc-500">{agents.filter((a) => a.status !== 'IDLE').length}/{agents.length} active</span>}
      className={className}
      bodyClassName="flex flex-col justify-between h-[calc(100%-2.75rem)] gap-1"
    >
      {agents.map((a) => (
        <AgentRow key={a.id} agent={a} working={a.id === workingId} />
      ))}
    </GlassPanel>
  );
};
