import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useWorkflowStore, useTelemetryStore } from '../../store';
import type { Workflow } from '../../types';

interface WorkflowPanelProps {
  className?: string;
}

const STATUS_DOT: Record<string, string> = {
  RUNNING:   'bg-cyan-500 animate-pulse',
  PAUSED:    'bg-amber-500',
  COMPLETED: 'bg-emerald-500',
  FAILED:    'bg-red-500 animate-pulse',
  CANCELLED: 'bg-zinc-600',
  PENDING:   'bg-zinc-700',
};

export const WorkflowPanel: React.FC<WorkflowPanelProps> = ({ className = '' }) => {
  const [isOpen, setIsOpen] = useState(false);
  const {
    workflows,
    activeWorkflowId,
    selectWorkflow,
    startWorkflow,
    pauseWorkflow,
    resumeWorkflow,
    cancelWorkflow,
    restartWorkflow,
  } = useWorkflowStore();

  const telemetry = useTelemetryStore();

  const activeWorkflow: Workflow | null =
    workflows.find(w => w.id === activeWorkflowId) ?? null;

  const runningCount = workflows.filter(w => w.status === 'RUNNING').length;

  return (
    <div className={`border border-matte-border/20 rounded-xl bg-matte-card/30 overflow-hidden ${className}`}>
      {/* Header / Toggle */}
      <button
        id="workflow-panel-toggle"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex justify-between items-center px-4 py-2.5 bg-black/10 hover:bg-black/20 focus:outline-none transition-colors text-[9px] font-mono uppercase tracking-widest text-zinc-500 font-bold"
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-2">
          <span>Workflow Engine</span>
          {runningCount > 0 && (
            <span className="px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-400 text-[7px] font-bold">
              {runningCount} ACTIVE
            </span>
          )}
        </div>
        <span className="text-[8px]">{isOpen ? '▼' : '▲'}</span>
      </button>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="p-3.5 space-y-3 border-t border-matte-border/10 bg-zinc-950/20">

              {/* Live telemetry row */}
              {telemetry.current_workflow && (
                <div className="space-y-1.5 pb-2 border-b border-matte-border/10">
                  <div className="flex justify-between items-center">
                    <span className="text-[8px] font-mono uppercase text-zinc-500">Active</span>
                    <span className="text-[8px] font-mono text-cyan-400 font-bold truncate max-w-[110px]">
                      {telemetry.current_workflow}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-[8px] font-mono uppercase text-zinc-500">Node</span>
                    <span className="text-[8px] font-mono text-zinc-300 truncate max-w-[110px]">
                      {telemetry.current_workflow_node || '—'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-[8px] font-mono uppercase text-zinc-500">Duration</span>
                    <span className="text-[8px] font-mono text-zinc-400">
                      {telemetry.workflow_duration_seconds?.toFixed(1) ?? '0'}s
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-[8px] font-mono uppercase text-zinc-500">Retries</span>
                    <span className={`text-[8px] font-mono font-bold ${
                      (telemetry.workflow_retries ?? 0) > 0 ? 'text-orange-400' : 'text-zinc-600'
                    }`}>
                      {telemetry.workflow_retries ?? 0}
                    </span>
                  </div>
                  {telemetry.workflow_branch_decisions && (
                    <div className="flex justify-between items-center">
                      <span className="text-[8px] font-mono uppercase text-zinc-500">Branch</span>
                      <span className="text-[8px] font-mono text-violet-400 truncate max-w-[110px]">
                        {telemetry.workflow_branch_decisions}
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* Workflow list */}
              {workflows.length === 0 ? (
                <p className="text-[8px] font-mono text-zinc-600 text-center py-2">
                  No workflows registered
                </p>
              ) : (
                <div className="space-y-1.5 max-h-40 overflow-y-auto scrollbar-thin">
                  {workflows.map(wf => (
                    <button
                      key={wf.id}
                      id={`wf-item-${wf.id}`}
                      onClick={() => selectWorkflow(wf.id)}
                      className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-colors ${
                        activeWorkflowId === wf.id
                          ? 'bg-cyan-500/10 border border-cyan-500/20'
                          : 'hover:bg-white/5 border border-transparent'
                      }`}
                    >
                      <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${STATUS_DOT[wf.status] || 'bg-zinc-700'}`} />
                      <span className="text-[8px] font-mono text-zinc-300 truncate">{wf.name}</span>
                      <span className={`ml-auto text-[7px] font-mono font-bold uppercase ${
                        wf.status === 'RUNNING'   ? 'text-cyan-400' :
                        wf.status === 'COMPLETED' ? 'text-emerald-400' :
                        wf.status === 'FAILED'    ? 'text-red-400' :
                        wf.status === 'PAUSED'    ? 'text-amber-400' :
                        'text-zinc-600'
                      }`}>
                        {wf.status}
                      </span>
                    </button>
                  ))}
                </div>
              )}

              {/* Controls for selected workflow */}
              {activeWorkflow && (
                <div className="flex flex-wrap gap-1.5 pt-1 border-t border-matte-border/10">
                  {(activeWorkflow.status === 'PENDING' || activeWorkflow.status === 'CANCELLED' || activeWorkflow.status === 'FAILED') && (
                    <CtrlBtn
                      id="wf-btn-start"
                      label="▶ Start"
                      colour="text-cyan-400 border-cyan-500/30 hover:bg-cyan-500/10"
                      onClick={() => startWorkflow(activeWorkflow.id)}
                    />
                  )}
                  {activeWorkflow.status === 'RUNNING' && (
                    <>
                      <CtrlBtn
                        id="wf-btn-pause"
                        label="⏸ Pause"
                        colour="text-amber-400 border-amber-500/30 hover:bg-amber-500/10"
                        onClick={() => pauseWorkflow(activeWorkflow.id)}
                      />
                      <CtrlBtn
                        id="wf-btn-cancel"
                        label="✕ Cancel"
                        colour="text-red-400 border-red-500/30 hover:bg-red-500/10"
                        onClick={() => cancelWorkflow(activeWorkflow.id)}
                      />
                    </>
                  )}
                  {activeWorkflow.status === 'PAUSED' && (
                    <>
                      <CtrlBtn
                        id="wf-btn-resume"
                        label="▶ Resume"
                        colour="text-cyan-400 border-cyan-500/30 hover:bg-cyan-500/10"
                        onClick={() => resumeWorkflow(activeWorkflow.id)}
                      />
                      <CtrlBtn
                        id="wf-btn-cancel"
                        label="✕ Cancel"
                        colour="text-red-400 border-red-500/30 hover:bg-red-500/10"
                        onClick={() => cancelWorkflow(activeWorkflow.id)}
                      />
                    </>
                  )}
                  {(activeWorkflow.status === 'COMPLETED' || activeWorkflow.status === 'FAILED') && (
                    <CtrlBtn
                      id="wf-btn-restart"
                      label="↺ Restart"
                      colour="text-violet-400 border-violet-500/30 hover:bg-violet-500/10"
                      onClick={() => restartWorkflow(activeWorkflow.id)}
                    />
                  )}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

// ─── Small control button ─────────────────────────────────────────────────────

interface CtrlBtnProps {
  id: string;
  label: string;
  colour: string;
  onClick: () => void;
}

const CtrlBtn: React.FC<CtrlBtnProps> = ({ id, label, colour, onClick }) => (
  <button
    id={id}
    onClick={onClick}
    className={`px-2 py-1 rounded border text-[7px] font-mono font-bold uppercase tracking-wider transition-colors cursor-pointer ${colour}`}
  >
    {label}
  </button>
);
