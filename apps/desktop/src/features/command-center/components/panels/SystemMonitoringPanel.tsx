import React, { useMemo } from 'react';
import { Activity } from 'lucide-react';
import { GlassPanel } from './GlassPanel';
import { CircularHUD } from '../widgets/CircularHUD';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';
import { useSystemStore } from '../../../../store/useSystemStore';

// Circular gauge component
const Gauge: React.FC<{ value: number; label: string; readout: string; color: string }> = ({
  value, label, readout, color,
}) => (
  <div className="flex flex-col items-center gap-1">
    <CircularHUD value={value} label={readout} sublabel="" size={72} color={color} />
    <span className="text-[7.5px] font-mono uppercase tracking-wider text-zinc-500 font-bold">{label}</span>
  </div>
);

// SVG history chart overlay of CPU, Memory, and GPU
const TelemetryHistoryChart: React.FC<{
  cpu: number[];
  memory: number[];
  gpu: number[];
  height?: number;
}> = ({ cpu, memory, gpu, height = 52 }) => {
  const W = 300;
  const H = height;

  const getPath = (series: number[]) => {
    if (!series.length) return '';
    const points = series.map((v, i) => {
      const x = (i / (series.length - 1)) * W;
      const y = H - (v / 100) * H;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    return `M ${points.join(' L ')}`;
  };

  const cpuPath = useMemo(() => getPath(cpu), [cpu]);
  const memPath = useMemo(() => getPath(memory), [memory]);
  const gpuPath = useMemo(() => getPath(gpu), [gpu]);

  return (
    <div className="relative flex flex-col gap-1 w-full bg-black/35 border border-cyan-border/5 rounded-xl p-2 mt-1">
      {/* Grid Lines */}
      <div className="absolute inset-0 flex flex-col justify-between pointer-events-none p-2 opacity-15">
        <div className="border-b border-dashed border-zinc-700 w-full" />
        <div className="border-b border-dashed border-zinc-700 w-full" />
        <div className="border-b border-dashed border-zinc-700 w-full" />
      </div>

      <div className="flex justify-between text-[7px] font-mono text-zinc-600 leading-none">
        <span>60</span>
        <span>40</span>
        <span>20</span>
        <span>0</span>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="w-full" style={{ height: H }}>
        {/* Draw series */}
        <path d={cpuPath} fill="none" stroke="#00f2fe" strokeWidth="1.2" style={{ filter: 'drop-shadow(0 0 2px rgba(0, 242, 254, 0.4))' }} />
        <path d={memPath} fill="none" stroke="#a78bfa" strokeWidth="1.2" style={{ filter: 'drop-shadow(0 0 2px rgba(167, 139, 250, 0.4))' }} />
        <path d={gpuPath} fill="none" stroke="#10b981" strokeWidth="1.2" style={{ filter: 'drop-shadow(0 0 2px rgba(16, 185, 129, 0.4))' }} />
      </svg>

      {/* X Axis Timeline Labels */}
      <div className="flex justify-between text-[6.5px] font-mono text-zinc-500 px-1 mt-0.5 leading-none">
        <span>60S</span>
        <span>45S</span>
        <span>30S</span>
        <span>15S</span>
        <span>0S</span>
      </div>
    </div>
  );
};

export const SystemMonitoringPanel: React.FC<{ className?: string }> = ({ className }) => {
  const cpu = useCommandCenterStore((s) => s.cpu);
  const memory = useCommandCenterStore((s) => s.memory);
  const gpu = useCommandCenterStore((s) => s.gpu);
  
  const apiConnected = useSystemStore((s) => s.apiConnected);

  // Derive memory GB readout
  const memoryGB = ((memory.value / 100) * 16).toFixed(1);

  return (
    <GlassPanel
      title="System Monitoring"
      icon={<Activity className="w-3.5 h-3.5" />}
      live
      sweep
      className={className}
      bodyClassName="flex flex-col justify-between h-[calc(100%-2.75rem)] gap-2"
      action={
        <span className={`flex items-center gap-1 text-[8px] font-mono uppercase tracking-[0.15em] ${apiConnected ? 'text-emerald-400 font-bold' : 'text-zinc-500'}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${apiConnected ? 'bg-emerald-400 cc-blink' : 'bg-zinc-600'}`} />
          {apiConnected ? 'live stream' : 'sim core'}
        </span>
      }
    >
      {/* 3 Circular HUD meters side by side */}
      <div className="grid grid-cols-3 gap-2 py-1 justify-items-center">
        <Gauge value={cpu.value} label="CPU" readout={`${Math.round(cpu.value)}%`} color="#00f2fe" />
        <Gauge value={memory.value} label="Memory" readout={`${memoryGB}G`} color="#a78bfa" />
        <Gauge value={gpu.value} label="GPU" readout={`${Math.round(gpu.value)}%`} color="#10b981" />
      </div>

      {/* Multi-line history graph overlay */}
      <div className="flex-1 flex flex-col justify-end">
        <span className="text-[7px] font-mono uppercase tracking-[0.18em] text-zinc-500 font-bold mb-1 pl-1">Activity Telemetry Log</span>
        <TelemetryHistoryChart 
          cpu={cpu.series} 
          memory={memory.series} 
          gpu={gpu.series} 
        />
      </div>
    </GlassPanel>
  );
};
