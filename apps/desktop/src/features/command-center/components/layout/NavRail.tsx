import React from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import type { LucideIcon } from 'lucide-react';
import {
  Command, Brain, Database, Bot, Workflow, Cpu, Settings, Sparkles,
} from 'lucide-react';

export interface NavItem {
  id: string;
  label: string;
  icon: LucideIcon;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'command', label: 'Command', icon: Command },
  { id: 'memory', label: 'Memory', icon: Brain },
  { id: 'knowledge', label: 'Knowledge', icon: Database },
  { id: 'agents', label: 'Agents', icon: Bot },
  { id: 'workflows', label: 'Workflows', icon: Workflow },
  { id: 'system', label: 'System', icon: Cpu },
  { id: 'settings', label: 'Settings', icon: Settings },
];

interface NavRailProps {
  active: string;
  onSelect: (id: string) => void;
}

export const NavRail: React.FC<NavRailProps> = ({ active, onSelect }) => {
  const navigate = useNavigate();

  return (
    <nav className="h-full w-[92px] shrink-0 flex flex-col items-center py-5 cc-glass rounded-none border-y-0 border-l-0 relative z-20">
      {/* Brand */}
      <button
        onClick={() => navigate('/')}
        title="Exit to dashboard"
        className="group flex flex-col items-center gap-2 mb-8"
      >
        <div className="relative w-11 h-11 rounded-2xl bg-black/60 border border-cyan-border/50 flex items-center justify-center shadow-[0_0_20px_rgba(0,242,254,0.15)]">
          <span className="absolute inset-0 rounded-2xl bg-cyan-glow/10 blur-md group-hover:bg-cyan-glow/20 transition-all" />
          <Sparkles className="w-5 h-5 text-cyan-glow relative z-10" />
        </div>
        <div className="text-center leading-tight">
          <div className="text-[11px] font-extrabold tracking-[0.2em] text-zinc-100 cc-text-glow">FRIDAY</div>
          <div className="text-[6.5px] font-mono uppercase tracking-[0.15em] text-cyan-glow/70">AI Operating System</div>
        </div>
      </button>

      {/* Nav items */}
      <div className="flex-1 flex flex-col items-center gap-2 w-full px-3">
        {NAV_ITEMS.map((item) => {
          const isActive = active === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelect(item.id)}
              title={item.label}
              className={`group relative w-full flex flex-col items-center gap-1 py-2.5 rounded-xl transition-all duration-200
                ${isActive
                  ? 'bg-cyan-dim/25 border border-cyan-border/50 shadow-[0_0_18px_rgba(0,242,254,0.12)]'
                  : 'border border-transparent hover:bg-white/[0.04] hover:border-cyan-border/20'}`}
            >
              {isActive && (
                <motion.span
                  layoutId="nav-active-bar"
                  className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-6 rounded-r-full bg-cyan-glow shadow-[0_0_10px_rgba(0,242,254,0.9)]"
                />
              )}
              <item.icon
                className={`w-5 h-5 transition-all duration-200
                  ${isActive
                    ? 'text-cyan-glow drop-shadow-[0_0_6px_rgba(0,242,254,0.8)]'
                    : 'text-zinc-500 group-hover:text-cyan-glow/80'}`}
              />
              <span
                className={`text-[7.5px] font-mono uppercase tracking-[0.12em] transition-colors
                  ${isActive ? 'text-cyan-glow' : 'text-zinc-600 group-hover:text-zinc-400'}`}
              >
                {item.label}
              </span>
            </button>
          );
        })}
      </div>

      {/* Bottom: FRIDAY Core */}
      <div className="w-full px-3 pt-4 mt-2 border-t border-cyan-border/10 flex flex-col items-center gap-1.5">
        <div className="relative w-8 h-8 rounded-full border border-cyan-border/40 flex items-center justify-center">
          <span className="absolute inset-0 rounded-full bg-cyan-glow/10 blur-sm cc-blink" />
          <div className="w-2.5 h-2.5 rounded-full bg-cyan-glow shadow-[0_0_10px_rgba(0,242,254,0.9)] relative z-10" />
        </div>
        <div className="text-[7px] font-mono uppercase tracking-[0.12em] text-zinc-500 text-center">FRIDAY Core</div>
        <div className="text-[7px] font-mono text-cyan-glow/60">v2.0.0</div>
      </div>
    </nav>
  );
};
