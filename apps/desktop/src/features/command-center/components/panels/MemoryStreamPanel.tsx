import React, { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Waves, Database, History, Link2, FileSearch, Cpu } from 'lucide-react';
import { GlassPanel } from './GlassPanel';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';
import { useAiStateStore } from '../../sync/useAiStateStore';
import { useBusEvent } from '../../hooks/useBusEvent';
import type { MemoryEvent } from '../../data/mock';

const KIND_META: Record<MemoryEvent['kind'], { icon: React.ReactNode; label: string; color: string; bg: string; border: string }> = {
  store: { icon: <Database className="w-3 h-3" />, label: 'Stored', color: 'text-amber-500', bg: 'bg-amber-950/20', border: 'border-amber-500/20' },
  recall: { icon: <History className="w-3 h-3" />, label: 'Recalled', color: 'text-cyan-glow', bg: 'bg-cyan-950/20', border: 'border-cyan-500/20' },
  link: { icon: <Link2 className="w-3 h-3" />, label: 'Linked', color: 'text-blue-400', bg: 'bg-blue-950/20', border: 'border-blue-500/20' },
  index: { icon: <FileSearch className="w-3 h-3" />, label: 'Indexed', color: 'text-emerald-400', bg: 'bg-emerald-950/20', border: 'border-emerald-500/20' },
};

const FILTERS: Array<{ key: MemoryEvent['kind'] | 'all'; label: string }> = [
  { key: 'all', label: 'All' },
  { key: 'store', label: 'Store' },
  { key: 'recall', label: 'Recall' },
  { key: 'link', label: 'Link' },
  { key: 'index', label: 'Index' },
];

const MemoryRow: React.FC<{ event: MemoryEvent; highlight?: boolean; isLast?: boolean }> = ({ event, highlight, isLast }) => {
  const meta = KIND_META[event.kind];
  
  const formatTime = (time: string) => {
    if (time === 'now') return 'now';
    if (time.endsWith('s')) return `${time} ago`;
    return time;
  };

  const isReflection = event.label.toLowerCase().includes('reflection') || event.kind === 'store';
  const isRecall = event.kind === 'recall' || highlight;

  const rowStyles = isReflection
    ? 'border-amber-550/25 bg-amber-500/5 shadow-[0_0_8px_rgba(245,158,11,0.12)]'
    : isRecall
    ? 'cc-recall-glow border-cyan-border/45 bg-cyan-glow/5 shadow-[0_0_8px_rgba(0,242,254,0.12)]'
    : 'border-transparent hover:border-zinc-800/80 hover:bg-white/[0.02]';

  const iconColor = isReflection ? 'text-amber-400' : meta.color;
  const iconBg = isReflection ? 'bg-amber-950/20' : meta.bg;
  const iconBorder = isReflection ? 'border-amber-500/20' : meta.border;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: -15, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.96 }}
      transition={{ type: 'spring', stiffness: 350, damping: 26 }}
      className={`group relative flex items-start gap-3 pl-6 pr-2 py-2 border rounded-xl transition-all duration-300 ${rowStyles}`}
    >
      {/* Vertical timeline track line */}
      {!isLast && (
        <span className="absolute left-[13px] top-6 bottom-0 w-px border-l border-dashed border-zinc-800 pointer-events-none" />
      )}
      
      {/* Icon with glowing status wrapper */}
      <div 
        className={`absolute left-[5px] top-2.5 w-4 h-4 rounded-full flex items-center justify-center border ${iconBg} ${iconBorder} text-xs shrink-0`}
      >
        <span className={iconColor}>{meta.icon}</span>
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-3">
          <span className={`text-[10px] font-bold truncate group-hover:text-cyan-glow transition-colors duration-200 ${isReflection ? 'text-amber-300' : 'text-zinc-100'}`}>
            {event.label}
          </span>
          <span className="text-[8px] font-mono text-zinc-500 tabular-nums shrink-0 mt-0.5">
            {formatTime(event.time)}
          </span>
        </div>
        <div className="text-[8.5px] font-mono text-zinc-500 truncate mt-0.5">{event.detail}</div>
      </div>
    </motion.div>
  );
};

export const MemoryStreamPanel: React.FC<{ className?: string }> = ({ className }) => {
  const stream = useCommandCenterStore((s) => s.memoryStream);
  const aiState = useAiStateStore((s) => s.state);
  const [filter, setFilter] = useState<MemoryEvent['kind'] | 'all'>('all');
  const [flash, setFlash] = useState(false);

  // React to updates on event bus
  useBusEvent('MEMORY_UPDATED', () => {
    setFlash(true);
    window.setTimeout(() => setFlash(false), 900);
  });

  const retrieving = aiState === 'memory' || aiState === 'thinking';

  const filteredItems = useMemo(() => {
    return filter === 'all' ? stream : stream.filter((e) => e.kind === filter);
  }, [stream, filter]);

  return (
    <GlassPanel
      title="Memory Stream"
      icon={<Waves className="w-3.5 h-3.5" />}
      live
      liveColor="green"
      className={className}
      bodyClassName="flex flex-col gap-2.5 h-[calc(100%-2.75rem)]"
    >
      {/* Filters bar */}
      <div className="flex flex-wrap gap-1">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-2 py-0.5 rounded-full border text-[7.5px] font-mono uppercase tracking-[0.12em] transition-colors cursor-pointer ${
              filter === f.key
                ? 'border-cyan-border/50 bg-cyan-glow/10 text-cyan-glow font-bold'
                : 'border-zinc-800/80 text-zinc-500 hover:text-zinc-300'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Stream lists with timeline connections */}
      <div className={`flex-1 min-h-0 overflow-y-auto pr-1 space-y-1 ${flash ? 'cc-flash-ring' : ''}`}>
        {filteredItems.length === 0 ? (
          <div className="h-full flex items-center justify-center text-[9px] font-mono text-zinc-600">No events</div>
        ) : (
          <AnimatePresence initial={false}>
            {filteredItems.map((e, idx) => (
              <MemoryRow 
                key={e.id} 
                event={e} 
                highlight={retrieving && e.kind === 'recall'} 
                isLast={idx === filteredItems.length - 1}
              />
            ))}
          </AnimatePresence>
        )}
      </div>

      {retrieving && (
        <div className="flex items-center gap-1.5 text-[8px] font-mono uppercase tracking-[0.2em] text-cyan-glow/85 cc-blink mt-1 shrink-0">
          <Cpu className="w-3 h-3" /> Retrieving memories…
        </div>
      )}
    </GlassPanel>
  );
};
