import React, { useMemo, useState } from 'react';
import { Waves, Database, History, Link2, FileSearch, Cpu } from 'lucide-react';
import { GlassPanel } from './GlassPanel';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';
import type { MemoryEvent } from '../../data/mock';

const KIND_META: Record<MemoryEvent['kind'], { icon: React.ReactNode; label: string; color: string; important?: boolean }> = {
  store: { icon: <Database className="w-3 h-3" />, label: 'Stored', color: 'text-orange-glow', important: true },
  recall: { icon: <History className="w-3 h-3" />, label: 'Recalled', color: 'text-cyan-glow' },
  link: { icon: <Link2 className="w-3 h-3" />, label: 'Linked', color: 'text-blue-300' },
  index: { icon: <FileSearch className="w-3 h-3" />, label: 'Indexed', color: 'text-emerald-300' },
};

const bucketOf = (time: string): 'Live' | 'Recent' | 'Earlier' =>
  time === 'now' ? 'Live' : time.endsWith('s') ? 'Recent' : 'Earlier';

const FILTERS: Array<{ key: MemoryEvent['kind'] | 'all'; label: string }> = [
  { key: 'all', label: 'All' },
  { key: 'store', label: 'Store' },
  { key: 'recall', label: 'Recall' },
  { key: 'link', label: 'Link' },
  { key: 'index', label: 'Index' },
];

const MemoryRow: React.FC<{ event: MemoryEvent; highlight?: boolean }> = ({ event, highlight }) => {
  const meta = KIND_META[event.kind];
  return (
    <div
      className={`group flex items-start gap-2 rounded-lg border px-2 py-1.5 transition-colors ${
        meta.important
          ? 'border-orange-border/40 bg-orange-glow/5'
          : 'border-transparent hover:border-cyan-border/20 hover:bg-white/[0.03]'
      } ${highlight ? 'cc-recall-glow' : ''}`}
    >
      <span className={`mt-0.5 ${meta.color}`}>{meta.icon}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[10px] font-semibold text-zinc-200 truncate">{event.label}</span>
          <span className="text-[7.5px] font-mono text-zinc-600 shrink-0">{event.time}</span>
        </div>
        <div className="text-[8px] font-mono text-zinc-500 truncate">{event.detail}</div>
      </div>
    </div>
  );
};

export const MemoryStreamPanel: React.FC<{ className?: string }> = ({ className }) => {
  const stream = useCommandCenterStore((s) => s.memoryStream);
  const thinking = useCommandCenterStore((s) => s.coreState === 'thinking');
  const [filter, setFilter] = useState<MemoryEvent['kind'] | 'all'>('all');

  const grouped = useMemo(() => {
    const filtered = filter === 'all' ? stream : stream.filter((e) => e.kind === filter);
    const order: Array<'Live' | 'Recent' | 'Earlier'> = ['Live', 'Recent', 'Earlier'];
    const map: Record<'Live' | 'Recent' | 'Earlier', MemoryEvent[]> = { Live: [], Recent: [], Earlier: [] };
    filtered.forEach((e) => map[bucketOf(e.time)].push(e));
    return order.map((b) => ({ bucket: b, items: map[b] })).filter((g) => g.items.length > 0);
  }, [stream, filter]);

  return (
    <GlassPanel
      title="Memory Stream"
      icon={<Waves className="w-3.5 h-3.5" />}
      live
      liveColor="green"
      className={className}
      bodyClassName="flex flex-col gap-2 h-[calc(100%-2.75rem)]"
    >
      <div className="flex flex-wrap gap-1">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-1.5 py-0.5 rounded-full border text-[7.5px] font-mono uppercase tracking-[0.12em] transition-colors ${
              filter === f.key
                ? 'border-cyan-border/50 bg-cyan-glow/10 text-cyan-glow'
                : 'border-zinc-700/50 text-zinc-500 hover:text-zinc-300'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto pr-1 space-y-2">
        {grouped.length === 0 && (
          <div className="h-full flex items-center justify-center text-[9px] font-mono text-zinc-600">No events</div>
        )}
        {grouped.map((g) => (
          <div key={g.bucket} className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-[7px] font-mono uppercase tracking-[0.2em] text-zinc-600">{g.bucket}</span>
              <div className="flex-1 h-px bg-zinc-800/60" />
            </div>
            {g.items.map((e) => (
              <MemoryRow key={e.id} event={e} highlight={thinking && e.kind === 'recall'} />
            ))}
          </div>
        ))}
      </div>

      {thinking && (
        <div className="flex items-center gap-1.5 text-[7.5px] font-mono uppercase tracking-[0.2em] text-cyan-glow/70 cc-blink">
          <Cpu className="w-3 h-3" /> Retrieving memories…
        </div>
      )}
    </GlassPanel>
  );
};
