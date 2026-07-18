import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ListChecks, CheckCircle2, Circle } from 'lucide-react';
import { GlassPanel } from './GlassPanel';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';

export const CurrentTaskPanel: React.FC<{ className?: string }> = ({ className }) => {
  const currentTask = useCommandCenterStore((s) => s.currentTask);
  const taskProgress = useCommandCenterStore((s) => s.taskProgress);
  const subtasks = useCommandCenterStore((s) => s.subtasks);
  const toggleSubtask = useCommandCenterStore((s) => s.toggleSubtask);

  return (
    <GlassPanel
      title="Current Task"
      icon={<ListChecks className="w-3.5 h-3.5" />}
      className={className}
      bodyClassName="h-[calc(100%-2.75rem)] grid grid-cols-[1.2fr_1.8fr] gap-4"
    >
      {/* Left side: Task Title and Progress Bar */}
      <div className="flex flex-col justify-between py-1">
        <div className="space-y-1">
          <span className="text-[7.5px] font-mono uppercase tracking-[0.15em] text-zinc-500">Active Goal</span>
          <h4 className="text-xs font-bold text-zinc-100 line-clamp-2 leading-snug">{currentTask}</h4>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between text-[8px] font-mono">
            <span className="text-zinc-500">PROGRESS</span>
            <span className="font-bold text-cyan-glow tracking-wider">{taskProgress}%</span>
          </div>
          <div className="h-2 w-full rounded-full bg-black/45 border border-cyan-border/10 overflow-hidden relative">
            <motion.div
              className="h-full rounded-full bg-gradient-to-r from-cyan-glow to-hud-blue"
              initial={{ width: 0 }}
              animate={{ width: `${taskProgress}%` }}
              transition={{ duration: 0.6, ease: 'easeOut' }}
            />
            {/* Pulsing glow line */}
            <div
              className="absolute top-0 bottom-0 w-2 bg-white/20 blur-[1px] animate-pulse"
              style={{ left: `calc(${taskProgress}% - 8px)` }}
            />
          </div>
        </div>
      </div>

      {/* Right side: Animated Interactive Subtasks Checklist */}
      <div className="flex flex-col gap-1.5 overflow-y-auto pr-1 scrollbar-thin py-0.5">
        <span className="text-[7px] font-mono uppercase tracking-[0.15em] text-zinc-500 mb-0.5">Sub-Tasks Checklist</span>
        {subtasks.map((task) => (
          <button
            key={task.id}
            onClick={() => toggleSubtask(task.id)}
            className={`flex items-center gap-2 px-2 py-1 rounded-lg border text-left transition-all duration-300 relative overflow-hidden cursor-pointer ${
              task.done
                ? 'border-emerald-500/25 bg-emerald-500/5 text-zinc-300'
                : 'border-transparent hover:border-cyan-border/20 hover:bg-white/[0.02] text-zinc-400'
            }`}
          >
            {/* Checkbox scale bounce animation */}
            <motion.div 
              className="shrink-0"
              initial={false}
              animate={{ scale: task.done ? [0.8, 1.1, 1.0] : 1.0 }}
              transition={{ duration: 0.3 }}
            >
              {task.done ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              ) : (
                <Circle className="w-3.5 h-3.5 text-zinc-600 group-hover:text-cyan-glow/60" />
              )}
            </motion.div>

            {/* Label with animated strike-through overlay */}
            <div className="relative flex-1 min-w-0 pr-2">
              <span className={`text-[9px] font-mono block truncate transition-colors duration-300 ${
                task.done ? 'text-zinc-500' : 'text-zinc-300'
              }`}>
                {task.label}
              </span>
              
              {/* Custom linear strike-through path */}
              <AnimatePresence>
                {task.done && (
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: '100%' }}
                    exit={{ width: 0 }}
                    transition={{ duration: 0.35, ease: 'easeInOut' }}
                    className="absolute left-0 top-[50%] h-[1px] bg-emerald-400/50 pointer-events-none"
                  />
                )}
              </AnimatePresence>
            </div>
          </button>
        ))}
      </div>
    </GlassPanel>
  );
};
export default CurrentTaskPanel;
