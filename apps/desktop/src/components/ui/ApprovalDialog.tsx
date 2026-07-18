import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, Check, X, Terminal } from 'lucide-react';

interface ApprovalDialogProps {
  open: boolean;
  title?: string;
  prompt: string;
  toolName?: string;
  args?: Record<string, unknown>;
  onApprove: () => void;
  onReject: () => void;
  approving?: boolean;
}

export const ApprovalDialog: React.FC<ApprovalDialogProps> = ({
  open,
  title = 'Action Requires Approval',
  prompt,
  toolName,
  args,
  onApprove,
  onReject,
  approving = false,
}) => {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={onReject}
        >
          <motion.div
            initial={{ scale: 0.92, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.92, opacity: 0, y: 20 }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            className="bg-zinc-900/95 border border-amber-500/25 rounded-2xl p-6 max-w-lg w-full space-y-4 shadow-[0_0_60px_rgba(245,158,11,0.1)]"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="Approval dialog"
          >
            <div className="flex items-center gap-3">
              <div className="p-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-zinc-100">{title}</h3>
                {toolName && (
                  <span className="flex items-center gap-1 text-[10px] font-mono text-amber-400/80 mt-0.5">
                    <Terminal className="w-3 h-3" />
                    {toolName}
                  </span>
                )}
              </div>
            </div>

            <div className="bg-zinc-950/60 border border-matte-border/50 rounded-xl p-4 max-h-32 overflow-y-auto">
              <p className="text-xs text-zinc-300 font-mono leading-relaxed">{prompt}</p>
            </div>

            {args && Object.keys(args).length > 0 && (
              <pre className="p-3 bg-black/40 rounded-lg text-[10px] text-zinc-400 overflow-x-auto font-mono max-h-28 scrollbar-thin leading-relaxed border border-matte-border/30">
                {JSON.stringify(args, null, 2)}
              </pre>
            )}

            <div className="flex gap-3 justify-end pt-1">
              <button
                onClick={onReject}
                disabled={approving}
                className="inline-flex items-center gap-1.5 text-xs font-semibold px-4 py-2 rounded-xl
                           bg-zinc-800/80 text-zinc-300 border border-matte-border
                           hover:bg-zinc-700/80 hover:border-rose-500/30 hover:text-rose-400
                           disabled:opacity-50 transition-all"
              >
                <X className="w-3.5 h-3.5" />
                Reject
              </button>
              <button
                onClick={onApprove}
                disabled={approving}
                className="inline-flex items-center gap-1.5 text-xs font-semibold px-5 py-2 rounded-xl
                           bg-cyan-glow text-black
                           hover:bg-cyan-glow/90 hover:shadow-[0_0_20px_rgba(0,242,254,0.25)]
                           disabled:opacity-50 transition-all"
              >
                {approving ? (
                  <>
                    <svg className="animate-spin w-3.5 h-3.5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Approving...
                  </>
                ) : (
                  <>
                    <Check className="w-3.5 h-3.5" />
                    Approve
                  </>
                )}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
