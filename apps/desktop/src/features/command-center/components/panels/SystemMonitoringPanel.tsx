import React from 'react';
import { Activity, Radio, Mic, Volume2 } from 'lucide-react';
import { GlassPanel } from './GlassPanel';
import { CircularHUD } from '../widgets/CircularHUD';
import { Sparkline } from '../widgets/Sparkline';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';
import { useSystemStore } from '../../../../store/useSystemStore';
import { useAiStateStore } from '../../sync/useAiStateStore';

const Gauge: React.FC<{ value: number; label: string; color: string; series: number[] }> = ({
  value, label, color, series,
}) => (
  <div className="flex flex-col items-center gap-0.5">
    <CircularHUD value={value} label={`${Math.round(value)}`} sublabel={label} size={70} color={color} />
    <div className="w-full px-1">
      <Sparkline data={series} color={color} height={14} />
    </div>
  </div>
);

const StatRow: React.FC<{ label: string; value: string; accent?: string }> = ({ label, value, accent = 'text-cyan-glow' }) => (
  <div className="flex items-center justify-between gap-2 text-[9px] font-mono">
    <span className="uppercase tracking-[0.12em] text-zinc-500">{label}</span>
    <span className={`font-bold tabular-nums truncate max-w-[130px] ${accent}`}>{value}</span>
  </div>
);

export const SystemMonitoringPanel: React.FC<{ className?: string }> = ({ className }) => {
  const cpu = useCommandCenterStore((s) => s.cpu);
  const memory = useCommandCenterStore((s) => s.memory);
  const gpu = useCommandCenterStore((s) => s.gpu);
  const network = useCommandCenterStore((s) => s.network);
  const processes = useCommandCenterStore((s) => s.runningProcesses);
  const model = useCommandCenterStore((s) => s.model);
  const tokensFallback = useCommandCenterStore((s) => s.responseSpeed);
  const latencyFallback = useCommandCenterStore((s) => s.apiLatency);
  const sessionFallback = useCommandCenterStore((s) => s.activeSession);
  const listening = useCommandCenterStore((s) => s.listening);
  const coreState = useCommandCenterStore((s) => s.coreState);
  const aiState = useAiStateStore((s) => s.state);

  const telemetry = useSystemStore((s) => s.lastTelemetry);
  const execMs = useSystemStore((s) => s.lastExecutionTimeMs);
  const sessionId = useSystemStore((s) => s.currentSessionId);
  const apiConnected = useSystemStore((s) => s.apiConnected);

  const activeModel = telemetry?.model || model;
  const latency = execMs != null ? `${Math.round(execMs)} ms` : `${latencyFallback} ms`;
  const session = sessionId || sessionFallback;
  const tokens = telemetry?.total_tokens && execMs
    ? `${Math.round(telemetry.total_tokens / Math.max(execMs / 1000, 0.1))}/s`
    : `${tokensFallback} t/s`;

  const speaking = coreState === 'speaking' && !listening;

  return (
    <GlassPanel
      title="System Monitoring"
      icon={<Activity className="w-3.5 h-3.5" />}
      live
      sweep
      className={className}
      bodyClassName="flex flex-col gap-2 h-[calc(100%-2.75rem)] overflow-hidden"
      action={
        <span className={`flex items-center gap-1 text-[8px] font-mono uppercase tracking-[0.15em] ${apiConnected ? 'text-emerald-400' : 'text-zinc-500'}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${apiConnected ? 'bg-emerald-400' : 'bg-zinc-600'}`} />
          {apiConnected ? 'linked' : 'sim'}
        </span>
      }
    >
      {(listening || speaking) && (
        <div className={`flex items-center gap-1.5 text-[8px] font-mono uppercase tracking-[0.2em] ${listening ? 'text-emerald-400' : 'text-cyan-glow'} cc-blink`}>
          {listening ? <Mic className="w-3 h-3" /> : <Volume2 className="w-3 h-3" />}
          {listening ? 'Listening' : 'Speaking'}
        </div>
      )}

      <div className="flex items-center gap-1.5 text-[8px] font-mono uppercase tracking-[0.2em] text-zinc-400">
        <span className={`w-1.5 h-1.5 rounded-full ${aiState === 'error' ? 'bg-rose-500' : 'bg-cyan-glow/70'}`} />
        Friday · {aiState}
      </div>

      <div className="grid grid-cols-2 gap-x-1 gap-y-1">
        <Gauge value={cpu.value} label="CPU" color="#00f2fe" series={cpu.series} />
        <Gauge value={memory.value} label="Mem" color="#4db8ff" series={memory.series} />
        <Gauge value={gpu.value} label="GPU" color="#ff8a3d" series={gpu.series} />
        <Gauge value={network.value} label="Net" color="#34d399" series={network.series} />
      </div>

      <div className="space-y-1 mt-0.5">
        <StatRow label="Model" value={activeModel} accent="text-zinc-200" />
        <StatRow label="Session" value={session} />
        <StatRow label="Tokens" value={tokens} accent="text-orange-glow" />
        <StatRow label="API Latency" value={latency} />
      </div>

      <div className="mt-1">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[8px] font-mono uppercase tracking-[0.15em] text-zinc-500 flex items-center gap-1">
            <Radio className="w-3 h-3" /> Running Processes
          </span>
          <span className="text-[8px] font-mono text-cyan-glow/70">{processes.length}</span>
        </div>
        <div className="space-y-1">
          {processes.slice(0, 4).map((p) => (
            <div key={p.pid} className="flex items-center gap-2">
              <span className="text-[8.5px] font-mono text-zinc-400 w-24 truncate">{p.name}</span>
              <div className="flex-1 h-1 rounded-full bg-black/50 overflow-hidden border border-matte-border/50">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{ width: `${p.cpu}%`, background: 'linear-gradient(90deg,#00f2fe,#4db8ff)' }}
                />
              </div>
              <span className="text-[8px] font-mono tabular-nums text-zinc-500 w-8 text-right">{Math.round(p.cpu)}%</span>
            </div>
          ))}
        </div>
      </div>
    </GlassPanel>
  );
};
