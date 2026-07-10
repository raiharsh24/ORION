import React from 'react';
import { Activity } from 'lucide-react';
import { GlassPanel } from './GlassPanel';
import { Sparkline } from '../widgets/Sparkline';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';

interface Row {
  key: 'cpu' | 'memory' | 'gpu' | 'network';
  label: string;
  color: string;
  unit?: string;
}

const ROWS: Row[] = [
  { key: 'cpu', label: 'CPU', color: '#00f2fe' },
  { key: 'memory', label: 'Memory', color: '#4db8ff' },
  { key: 'gpu', label: 'GPU', color: '#ff8a3d' },
  { key: 'network', label: 'Network', color: '#34d399' },
];

export const SystemOverviewPanel: React.FC<{ className?: string }> = ({ className }) => {
  const cpu = useCommandCenterStore((s) => s.cpu);
  const memory = useCommandCenterStore((s) => s.memory);
  const gpu = useCommandCenterStore((s) => s.gpu);
  const network = useCommandCenterStore((s) => s.network);
  const metrics = { cpu, memory, gpu, network };

  return (
    <GlassPanel
      title="System Overview"
      icon={<Activity className="w-3.5 h-3.5" />}
      live
      sweep
      className={className}
      bodyClassName="grid grid-rows-4 gap-2 h-[calc(100%-2.75rem)]"
    >
      {ROWS.map((row) => {
        const m = metrics[row.key];
        return (
          <div key={row.key} className="flex flex-col justify-center">
            <div className="flex items-center justify-between mb-0.5">
              <span className="text-[9px] font-mono uppercase tracking-[0.15em] text-zinc-400">{row.label}</span>
              <span className="text-[10px] font-mono font-bold tabular-nums" style={{ color: row.color }}>
                {Math.round(m.value)}%
              </span>
            </div>
            <Sparkline data={m.series} color={row.color} height={26} />
          </div>
        );
      })}
    </GlassPanel>
  );
};
