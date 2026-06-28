import React from 'react';
import { motion } from 'framer-motion';
import { Pin, Clock, Play, CheckCircle, AlertCircle, XCircle } from 'lucide-react';
import type { Mission } from '../../types';

// 1. TypeScript interface for Props
export interface MissionCardProps {
  mission: Mission;
  isActive?: boolean;
  isPinned?: boolean;
  onClick?: () => void;
  onTogglePin?: (e: React.MouseEvent) => void;
  isLoading?: boolean;
  hasError?: boolean;
}

// 2. Export component
export const MissionCard: React.FC<MissionCardProps> = ({
  mission,
  isActive = false,
  isPinned = false,
  onClick = () => {},
  onTogglePin = () => {},
  isLoading = false,
  hasError = false,
}) => {
  // 3. Accessibility comments
  // role="tab" marks this item as a selectable tab in a navigation container list
  // aria-selected communicates the active state

  // 4. Loading state
  if (isLoading) {
    return (
      <div className="p-4 bg-zinc-900 border border-matte-border/20 rounded-xl space-y-3 animate-pulse">
        <div className="h-4 w-3/4 bg-zinc-800 rounded" />
        <div className="h-2 w-full bg-zinc-800 rounded" />
        <div className="h-3 w-1/4 bg-zinc-800 rounded" />
      </div>
    );
  }

  // 5. Error state
  if (hasError) {
    return (
      <div 
        className="p-4 bg-red-950/15 border border-red-900/30 rounded-xl text-center text-xs font-mono text-red-400"
        role="alert"
      >
        Failed to load card.
      </div>
    );
  }

  // 6. Empty state fallback
  if (!mission) {
    return (
      <div className="p-4 border border-dashed border-matte-border rounded-xl text-center text-[10px] text-zinc-600 font-mono">
        No Data
      </div>
    );
  }

  const priorityThemes = {
    LOW: 'text-zinc-500 bg-zinc-950/40 border-zinc-900',
    MEDIUM: 'text-cyan-glow bg-cyan-dim/10 border-cyan-glow/20',
    HIGH: 'text-orange-400 bg-orange-950/15 border-orange-900/20',
    CRITICAL: 'text-red-400 bg-red-950/20 border-red-900/30 shadow-[0_0_10px_rgba(239,68,68,0.15)]',
  };

  const statusIcons = {
    PENDING: Clock,
    RUNNING: Play,
    COMPLETED: CheckCircle,
    FAILED: AlertCircle,
    CANCELLED: XCircle,
  };

  const statusThemes = {
    PENDING: 'bg-zinc-950/50 border-zinc-900 text-zinc-400',
    RUNNING: 'bg-cyan-dim/15 border-cyan-glow/30 text-cyan-glow font-bold shadow-[0_0_10px_rgba(0,242,254,0.05)]',
    COMPLETED: 'bg-emerald-dim/15 border-emerald-500/20 text-emerald-400 font-bold',
    FAILED: 'bg-red-dim/15 border-red-500/20 text-red-400 font-bold',
    CANCELLED: 'bg-yellow-950/20 border-yellow-500/20 text-yellow-400',
  };

  const IconComponent = statusIcons[mission.status] || Clock;

  return (
    <motion.button
      onClick={onClick}
      role="tab"
      aria-selected={isActive}
      tabIndex={0}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.2 }}
      className={`w-full text-left p-4.5 rounded-xl border transition-all duration-300 relative overflow-hidden group focus:outline-none focus:ring-1 focus:ring-cyan-glow/30
        ${isActive 
          ? 'bg-cyan-dim/20 border-cyan-border/40 shadow-[0_0_20px_rgba(0,242,254,0.04)]' 
          : 'bg-matte-card/40 border-matte-border/30 hover:border-matte-border hover:bg-matte-card/65'
        }
      `}
    >
      {/* Background active glow highlight bar */}
      {isActive && (
        <motion.div 
          layoutId="active-card-bar"
          className="absolute left-0 top-0 bottom-0 w-0.75 bg-cyan-glow"
        />
      )}

      {/* Title Header */}
      <div className="flex justify-between items-start gap-3">
        <div className="flex items-center gap-2 overflow-hidden flex-1">
          <IconComponent className={`w-3.5 h-3.5 flex-shrink-0 ${mission.status === 'RUNNING' ? 'animate-spin' : ''}`} />
          <h3 className="text-xs font-bold text-zinc-100 font-sans tracking-wide truncate group-hover:text-cyan-glow transition-colors">
            {mission.name}
          </h3>
        </div>

        <div className="flex items-center gap-1.5 flex-shrink-0">
          {/* Pinned Button Indicator */}
          <button 
            onClick={onTogglePin}
            className={`p-0.5 rounded hover:bg-white/5 transition-colors focus:outline-none ${isPinned ? 'text-cyan-glow' : 'text-zinc-600 hover:text-zinc-400'}`}
            aria-label="Toggle pin mission"
          >
            <Pin className="w-3 h-3" />
          </button>

          <span className={`text-[8px] font-mono font-bold px-1.5 py-0.5 rounded border uppercase tracking-wider ${priorityThemes[mission.priority]}`}>
            {mission.priority}
          </span>
        </div>
      </div>

      {/* Description */}
      <p className="text-[10px] text-zinc-400 mt-2 truncate font-mono">
        {mission.description}
      </p>

      {/* Step Progress indicators */}
      <div className="mt-3.5 space-y-2">
        <div className="flex justify-between items-center text-[9px] font-mono uppercase tracking-wider text-zinc-500">
          <span className="truncate max-w-[200px]">{mission.currentStep}</span>
          <span className="text-zinc-300 font-bold">{mission.progress}%</span>
        </div>
        
        {/* Progress Gauge */}
        <div className="w-full bg-zinc-950/60 h-1.5 rounded-full overflow-hidden border border-matte-border/20">
          <motion.div 
            initial={{ width: 0 }}
            animate={{ width: `${mission.progress}%` }}
            transition={{ duration: 0.5 }}
            className={`h-full rounded-full
              ${mission.status === 'FAILED' ? 'bg-red-500' : 'bg-cyan-glow'}
            `}
          />
        </div>
      </div>

      {/* Footer statistics */}
      <div className="mt-4 pt-3.5 border-t border-matte-border/20 flex justify-between items-center text-[9px] font-mono text-zinc-500 uppercase tracking-widest">
        <span>Duration: {mission.durationMs > 0 ? `${(mission.durationMs / 1000).toFixed(1)}s` : '--'}</span>
        <span className={`px-1.5 py-0.5 rounded-sm text-[8px] tracking-wide font-bold border ${statusThemes[mission.status]}`}>
          {mission.status}
        </span>
      </div>
    </motion.button>
  );
};
