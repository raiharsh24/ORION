import React from 'react';
import { Activity, ArrowDown, ArrowUp } from 'lucide-react';
import { GlassPanel } from './GlassPanel';
import { Sparkline } from '../widgets/Sparkline';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';

export const SystemOverviewPanel: React.FC<{ className?: string }> = ({ className }) => {
  const cpu = useCommandCenterStore((s) => s.cpu);
  const memory = useCommandCenterStore((s) => s.memory);
  const gpu = useCommandCenterStore((s) => s.gpu);
  const network = useCommandCenterStore((s) => s.network);

  // Compute memory readout based on memory percentage
  const totalMem = 16; // GB
  const currentMem = ((memory.value / 100) * totalMem).toFixed(1);

  // Compute upload and download speeds derived from network metric
  const downloadSpeed = (network.value * 0.42).toFixed(1);
  const uploadSpeed = (network.value * 0.12).toFixed(1);

  return (
    <GlassPanel
      title="System Overview"
      icon={<Activity className="w-3.5 h-3.5" />}
      live
      sweep
      className={className}
      bodyClassName="flex flex-col gap-3 h-[calc(100%-2.75rem)]"
    >
      {/* CPU Usage Section */}
      <div className="flex flex-col">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[7.5px] font-mono uppercase tracking-[0.15em] text-zinc-500">CPU USAGE</span>
          <span className="text-[10px] font-mono font-bold text-cyan-glow tabular-nums cc-text-glow">
            {Math.round(cpu.value)}%
          </span>
        </div>
        <Sparkline data={cpu.series} color="#00f2fe" height={22} />
      </div>

      {/* Memory Utilization Progress Bar Section */}
      <div className="flex flex-col">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[7.5px] font-mono uppercase tracking-[0.15em] text-zinc-500">MEMORY</span>
          <span className="text-[9px] font-mono text-purple-400 tabular-nums">
            {currentMem} GB / {totalMem} GB
          </span>
        </div>
        <div className="h-2 w-full rounded-full bg-black/45 border border-purple-900/10 overflow-hidden relative">
          <div
            className="h-full rounded-full bg-gradient-to-r from-purple-600 to-indigo-500 transition-all duration-500"
            style={{ width: `${memory.value}%` }}
          />
        </div>
      </div>

      {/* GPU Section */}
      <div className="flex flex-col">
        <div className="flex items-center justify-between mb-1">
          <div className="flex flex-col leading-none">
            <span className="text-[7.5px] font-mono uppercase tracking-[0.15em] text-zinc-500">GPU</span>
            <span className="text-[6.5px] font-mono text-zinc-600 mt-0.5">NVIDIA RTX 4060</span>
          </div>
          <span className="text-[10px] font-mono font-bold text-emerald-400 tabular-nums">
            {Math.round(gpu.value)}%
          </span>
        </div>
        <Sparkline data={gpu.series} color="#10b981" height={22} />
      </div>

      {/* Network Speeds Section */}
      <div className="flex flex-col">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[7.5px] font-mono uppercase tracking-[0.15em] text-zinc-500">NETWORK</span>
          <div className="flex items-center gap-2 text-[8px] font-mono text-zinc-400">
            <span className="flex items-center text-cyan-glow">
              <ArrowDown className="w-2.5 h-2.5 mr-0.5" /> {downloadSpeed} MB/s
            </span>
            <span className="flex items-center text-orange-glow">
              <ArrowUp className="w-2.5 h-2.5 mr-0.5" /> {uploadSpeed} MB/s
            </span>
          </div>
        </div>
        <Sparkline data={network.series} color="#f97316" height={22} />
      </div>

      {/* Footer: Workspace Intel & System Status */}
      <div className="mt-1 pt-2 border-t border-cyan-border/10 flex flex-col gap-1.5 text-[8.5px] font-mono text-zinc-500">
        <div className="flex items-center justify-between">
          <span>Project: <span className="text-zinc-300 font-bold">ORION</span> (<span className="text-cyan-glow font-bold">main</span>)</span>
          <span>Framework: <span className="text-zinc-300">Vite / React</span></span>
        </div>
        <div className="flex items-center justify-between text-[8px]">
          <span>Tech: <span className="text-zinc-400">TypeScript, Three.js, Zustand</span></span>
          <span>Health: <span className="text-emerald-400 font-bold">98%</span></span>
        </div>
        <div className="flex items-center justify-between border-t border-zinc-900 pt-1.5">
          <span className="uppercase tracking-wider">System Kernel</span>
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 cc-blink" />
            <span className="text-[9px] font-bold uppercase text-emerald-400 tracking-wider">Optimal</span>
          </div>
        </div>
      </div>
    </GlassPanel>
  );
};
