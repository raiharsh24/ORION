import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Sparkles, Loader, Send, FileCode, FolderOpen, Box, Globe, AlertOctagon } from 'lucide-react';
import { MarkdownRenderer } from './MarkdownRenderer';
import { API_BASE_URL } from '../../config/api';

export type ExplainKind = 'file' | 'folder' | 'module' | 'api' | 'error';

export interface ExplainSubject {
  kind: ExplainKind;
  label: string;
  /** Extra grounding context passed to the model (paths, branch, stack, stack traces...). */
  context?: string;
}

interface ExplainPanelProps {
  open: boolean;
  onClose: () => void;
  subject: ExplainSubject | null;
}

const kindMeta: Record<ExplainKind, { icon: React.FC<{ className?: string }>; verb: string }> = {
  file: { icon: FileCode, verb: 'Explain this file' },
  folder: { icon: FolderOpen, verb: 'Explain this folder' },
  module: { icon: Box, verb: 'Explain this module' },
  api: { icon: Globe, verb: 'Explain this API' },
  error: { icon: AlertOctagon, verb: 'Explain this error' },
};

function buildPrompt(subject: ExplainSubject, followUp?: string): string {
  const ctx = subject.context ? `Context:\n${subject.context}\n\n` : '';
  if (followUp) {
    return `${ctx}Regarding the ${subject.kind} "${subject.label}", answer this follow-up concisely: ${followUp}`;
  }
  const asks: Record<ExplainKind, string> = {
    file: `Explain the purpose and responsibilities of the file "${subject.label}". Cover what it does, key exports, and how it fits into the wider project.`,
    folder: `Explain the role of the folder/directory "${subject.label}" in this project. Summarise what it groups together and its architectural purpose.`,
    module: `Explain the module/project "${subject.label}": its main responsibilities, entry points, key technologies, and notable structure.`,
    api: `Explain the API "${subject.label}": what it does, expected inputs/outputs, and how it is typically used.`,
    error: `Explain the following error "${subject.label}": likely root cause, what it means, and concrete steps to fix it.`,
  };
  return `${ctx}${asks[subject.kind]} Use concise Markdown.`;
}

export const ExplainPanel: React.FC<ExplainPanelProps> = ({ open, onClose, subject }) => {
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState('');
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const runExplain = useCallback(async (prompt: string) => {
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setResponse('');

    try {
      const res = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          prompt,
          stream: true,
          session_id: `explain-${Date.now()}`,
        }),
      });

      const contentType = res.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        const data = await res.json();
        setResponse(data.response || data.text || data.message || 'No explanation generated.');
        return;
      }

      if (!res.ok || !res.body) {
        throw new Error(`API error ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let accumulated = '';
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const chunk = line.substring(6);
            if (chunk === '[DONE]') continue;
            accumulated += chunk;
            setResponse(accumulated);
          }
        }
      }
      if (!accumulated) setResponse('No explanation generated.');
    } catch (err: any) {
      if (err?.name === 'AbortError') return;
      setResponse('Failed to connect to the AI engine. Please ensure the backend is running.');
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  }, []);

  // Auto-explain when a new subject is opened.
  useEffect(() => {
    if (open && subject) {
      setQuery('');
      runExplain(buildPrompt(subject));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, subject?.kind, subject?.label]);

  // Keep the view pinned to the latest streamed tokens.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [response]);

  useEffect(() => {
    if (!open && abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, [open]);

  const handleFollowUp = () => {
    if (!query.trim() || !subject) return;
    const q = query;
    setQuery('');
    runExplain(buildPrompt(subject, q));
  };

  const Icon = subject ? kindMeta[subject.kind].icon : Sparkles;

  return (
    <AnimatePresence>
      {open && subject && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
          onClick={onClose}
        >
          <motion.div
            initial={{ y: '100%', opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: '100%', opacity: 0 }}
            transition={{ type: 'spring', stiffness: 400, damping: 35 }}
            className="bg-zinc-900/95 border-t sm:border border-matte-border w-full sm:max-w-lg sm:rounded-2xl max-h-[80vh] flex flex-col shadow-2xl"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="Explain panel"
          >
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-matte-border/50">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="p-1.5 rounded-lg bg-cyan-dim/20 border border-cyan-border/30 shrink-0">
                  <Icon className="w-4 h-4 text-cyan-glow" />
                </div>
                <div className="min-w-0">
                  <h3 className="text-sm font-bold text-zinc-100 flex items-center gap-2">
                    Explain
                    <span className="text-[9px] font-mono uppercase tracking-widest text-cyan-glow/70 bg-cyan-dim/10 border border-cyan-border/20 px-1.5 py-0.5 rounded">
                      {subject.kind}
                    </span>
                  </h3>
                  <p className="text-[10px] font-mono text-zinc-500 truncate max-w-[250px]">{subject.label}</p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-all"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Content */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin">
              {loading && !response && (
                <div className="flex items-center justify-center py-8">
                  <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono">
                    <Loader className="w-4 h-4 animate-spin text-cyan-glow" />
                    Generating explanation...
                  </div>
                </div>
              )}

              {response && (
                <div className="bg-zinc-950/60 border border-matte-border/50 rounded-xl p-4">
                  <MarkdownRenderer content={response} />
                  {loading && (
                    <span className="inline-block w-1.5 h-3.5 bg-cyan-glow animate-pulse ml-1 align-middle" />
                  )}
                </div>
              )}
            </div>

            {/* Follow-up input */}
            <div className="p-4 border-t border-matte-border/50">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleFollowUp();
                }}
                className="flex gap-2"
              >
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Ask a follow-up question..."
                  className="flex-1 bg-black/40 border border-matte-border hover:border-cyan-border/40 focus:border-cyan-glow/80
                             rounded-xl px-3.5 py-2 text-xs font-mono text-zinc-200 placeholder-zinc-600 focus:outline-none transition-all"
                />
                <button
                  type="submit"
                  disabled={!query.trim() || loading}
                  className="p-2 rounded-xl bg-cyan-glow text-black hover:bg-cyan-glow/90 disabled:opacity-30 transition-all"
                >
                  <Send className="w-4 h-4" />
                </button>
              </form>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
