import React from 'react';
import { motion } from 'framer-motion';
import { Check, Loader, AlertCircle, Ban } from 'lucide-react';

// 1. TypeScript interface for Props
export interface MissionTimelineProps {
  steps?: string[];
  currentStep?: string;
  status?: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  isLoading?: boolean;
  hasError?: boolean;
}

// 2. Export component
export const MissionTimeline: React.FC<MissionTimelineProps> = ({
  steps = [],
  currentStep = '',
  status = 'PENDING',
  isLoading = false,
  hasError = false,
}) => {
  // 3. Accessibility comments
  // role="progressbar" signals this represents progress steps to screen readers
  // aria-valuenow indicates the current active step index

  const activeIndex = steps.indexOf(currentStep);

  // 4. Loading placeholder
  if (isLoading) {
    return (
      <div 
        className="flex gap-4 p-6 items-center animate-pulse"
        aria-busy="true"
        aria-label="Loading progress timeline"
      >
        {[1, 2, 3].map((n) => (
          <div key={n} className="flex items-center gap-2">
            <div className="h-6 w-6 rounded-full bg-zinc-800" />
            <div className="h-2 w-16 bg-zinc-800" />
          </div>
        ))}
      </div>
    );
  }

  // 5. Error state
  if (hasError) {
    return (
      <div 
        className="p-6 bg-red-950/10 border border-red-900/20 text-xs font-mono text-red-400 rounded-xl"
        role="alert"
      >
        Failed to render timeline sequence.
      </div>
    );
  }

  // 6. Empty state
  if (steps.length === 0) {
    return (
      <div className="p-6 border border-dashed border-matte-border/30 rounded-xl text-center text-xs font-mono text-zinc-500">
        No execution timeline steps defined.
      </div>
    );
  }

  return (
    <div 
      className="p-6 border border-matte-border/20 rounded-xl bg-matte-card/30 backdrop-blur-sm"
      role="progressbar"
      aria-label="Mission execution timeline"
      aria-valuenow={activeIndex >= 0 ? activeIndex + 1 : 0}
      aria-valuemin={1}
      aria-valuemax={steps.length}
    >
      <h4 className="text-[10px] font-mono uppercase tracking-widest text-zinc-500 mb-6">
        Timeline Sequence
      </h4>

      <div className="flex items-center w-full overflow-x-auto pb-4 scrollbar-thin">
        {steps.map((step, idx) => {
          const isCompleted = idx < activeIndex || status === 'COMPLETED';
          const isActive = idx === activeIndex && status === 'RUNNING';
          const isFailed = idx === activeIndex && status === 'FAILED';
          const isCancelled = idx === activeIndex && status === 'CANCELLED';

          let nodeColor = 'bg-zinc-850 border-matte-border text-zinc-500';
          let textColor = 'text-zinc-500';
          let lineColor = 'bg-zinc-850';

          if (isCompleted) {
            nodeColor = 'bg-emerald-dim border-emerald-500 text-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.1)]';
            textColor = 'text-zinc-300';
            lineColor = 'bg-emerald-500/40';
          } else if (isActive) {
            nodeColor = 'bg-cyan-dim border-cyan-glow text-cyan-glow shadow-[0_0_15px_rgba(0,242,254,0.15)]';
            textColor = 'text-cyan-glow font-bold';
            lineColor = 'bg-cyan-glow/20';
          } else if (isFailed) {
            nodeColor = 'bg-red-dim border-red-500 text-red-400 shadow-[0_0_10px_rgba(239,68,68,0.1)]';
            textColor = 'text-red-400';
          } else if (isCancelled) {
            nodeColor = 'bg-yellow-dim border-yellow-500 text-yellow-400';
            textColor = 'text-yellow-400';
          }

          return (
            <div key={step} className="flex items-center flex-shrink-0">
              {/* Step Node */}
              <div className="flex flex-col items-center gap-2 relative">
                <motion.div 
                  initial={{ scale: 0.8, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ delay: idx * 0.1 }}
                  className={`w-7 h-7 rounded-full border flex items-center justify-center text-[10px] font-mono font-bold transition-all duration-300 ${nodeColor}`}
                >
                  {isCompleted ? (
                    <Check className="w-3.5 h-3.5" />
                  ) : isActive ? (
                    <Loader className="w-3.5 h-3.5 animate-spin" />
                  ) : isFailed ? (
                    <AlertCircle className="w-3.5 h-3.5" />
                  ) : isCancelled ? (
                    <Ban className="w-3.5 h-3.5" />
                  ) : (
                    <span>{idx + 1}</span>
                  )}
                </motion.div>
                
                {/* Ping ring for active step */}
                {isActive && (
                  <span className="absolute -top-1 -left-1 w-9 h-9 border border-cyan-glow rounded-full animate-ping opacity-35" />
                )}

                <span className={`text-[9px] font-mono uppercase tracking-wider absolute top-9 whitespace-nowrap ${textColor}`}>
                  {step}
                </span>
              </div>

              {/* Connecting Line */}
              {idx < steps.length - 1 && (
                <div className={`relative w-20 h-0.5 mx-3 transition-colors duration-300 ${lineColor}`}>
                  <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: isCompleted ? '100%' : '0%' }}
                    transition={{ duration: 0.4 }}
                    className="absolute inset-y-0 left-0 bg-gradient-to-r from-emerald-500/40 to-emerald-500"
                  />
                  {isActive && (
                    <div className="absolute inset-y-0 left-0 bg-cyan-glow animate-pulse" style={{ width: '50%' }} />
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

