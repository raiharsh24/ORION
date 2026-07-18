import React from 'react';
import { motion } from 'framer-motion';
import { Check, Loader, AlertCircle, Ban, Clock } from 'lucide-react';

export interface TimelineStep {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  duration?: number;
  startedAt?: string;
  error?: string;
}

interface Props {
  steps: TimelineStep[];
  className?: string;
}

const statusConfig = {
  pending: { icon: Clock, color: 'text-zinc-600', bg: 'bg-zinc-900/50', line: 'bg-zinc-800' },
  running: { icon: Loader, color: 'text-cyan-glow', bg: 'bg-cyan-dim/20', line: 'bg-cyan-glow/50' },
  completed: { icon: Check, color: 'text-emerald-400', bg: 'bg-emerald-500/10', line: 'bg-emerald-500/50' },
  failed: { icon: AlertCircle, color: 'text-rose-400', bg: 'bg-rose-500/10', line: 'bg-rose-500/50' },
  skipped: { icon: Ban, color: 'text-zinc-500', bg: 'bg-zinc-900/50', line: 'bg-zinc-800' },
};

export const ExecutionTimeline: React.FC<Props> = ({ steps, className = '' }) => {
  return (
    <div className={`space-y-0 ${className}`}>
      {steps.map((step, idx) => {
        const cfg = statusConfig[step.status];
        const Icon = cfg.icon;
        const isLast = idx === steps.length - 1;

        return (
          <motion.div
            key={step.id}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.05, duration: 0.25 }}
            className="relative flex gap-4"
          >
            {/* Vertical line */}
            {!isLast && (
              <div className={`absolute left-[15px] top-8 w-[2px] h-full ${cfg.line}`} />
            )}

            {/* Icon circle */}
            <div className={`relative z-10 w-8 h-8 rounded-xl flex items-center justify-center border shrink-0 ${cfg.bg} border-matte-border`}>
              {step.status === 'running' ? (
                <Icon className={`w-4 h-4 ${cfg.color} animate-spin`} />
              ) : (
                <Icon className={`w-4 h-4 ${cfg.color}`} />
              )}
            </div>

            {/* Content */}
            <div className={`flex-1 pb-6 min-w-0 ${cfg.color}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-zinc-200 truncate">
                  {step.name}
                </span>
                <div className="flex items-center gap-2 shrink-0">
                  {step.duration !== undefined && (
                    <span className="text-[10px] font-mono text-zinc-500 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {step.duration}ms
                    </span>
                  )}
                  <span className={`text-[9px] font-mono uppercase tracking-wider ${cfg.color}`}>
                    {step.status}
                  </span>
                </div>
              </div>

              {step.error && (
                <div className="mt-1.5 text-[10px] font-mono text-rose-400/80 bg-rose-500/5 border border-rose-500/10 rounded-lg px-2.5 py-1.5 leading-relaxed">
                  {step.error}
                </div>
              )}

              {step.startedAt && (
                <div className="mt-1 text-[9px] font-mono text-zinc-600">{step.startedAt}</div>
              )}
            </div>
          </motion.div>
        );
      })}

      {steps.length === 0 && (
        <div className="flex items-center justify-center h-24 text-xs text-zinc-500 font-mono">
          No execution steps recorded yet.
        </div>
      )}
    </div>
  );
};

export const TimelinePlaceholder: React.FC<{ count?: number }> = ({ count = 3 }) => (
  <div className="space-y-0 animate-pulse">
    {Array.from({ length: count }).map((_, i) => (
      <div key={i} className="relative flex gap-4 pb-6">
        <div className="w-8 h-8 rounded-xl bg-zinc-900/50 border border-matte-border" />
        <div className="flex-1 space-y-2">
          <div className="h-3 bg-zinc-900/50 rounded w-1/2" />
          <div className="h-2 bg-zinc-900/30 rounded w-1/4" />
        </div>
      </div>
    ))}
  </div>
);
