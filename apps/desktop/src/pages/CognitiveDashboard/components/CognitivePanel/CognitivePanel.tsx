import React from 'react';
import { motion } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardContent } from '../../../../components/ui/Card';
import { useCognitiveStore } from '../../store';
import { useMissionStore } from '../../../MissionCenter/store';
import {
  BrainCircuit, Gauge, Cog, Bot, Database, BookOpen,
} from 'lucide-react';

export const CognitivePanel: React.FC = () => {
  const panel = useCognitiveStore((s) => s.panel);
  const { reflectionStats, learningData } = useCognitiveStore();
  const missions = useMissionStore((s) => s.missions);

  const reflect = reflectionStats as Record<string, any> | null;
  const learning = learningData as Record<string, any> | null;
  const activeMission = missions.find((m) => m.status === 'RUNNING');

  const gaugeRotation = (panel.confidence * 180) - 90;

  const items = [
    {
      icon: BrainCircuit,
      label: 'Reasoning Stage',
      value: panel.reasoningStage,
      color: 'text-cyan-glow',
    },
    {
      icon: Cog,
      label: 'Selected Tools',
      value: panel.selectedTools.length > 0 ? panel.selectedTools.join(', ') : 'none',
      color: 'text-amber-400',
    },
    {
      icon: Bot,
      label: 'Active Agent',
      value: panel.activeAgent,
      color: 'text-purple-400',
    },
    {
      icon: Database,
      label: 'Memory Updates',
      value: panel.memoryUpdates,
      color: 'text-emerald-400',
    },
    {
      icon: BookOpen,
      label: 'Reflections',
      value: reflect?.total_reflections ?? 0,
      sub: `${((reflect?.avg_stage_success_rate ?? 0) * 100).toFixed(0)}% success rate`,
      color: 'text-sky-400',
    },
  ];

  return (
    <div className="space-y-4">
      <Card variant="glow">
        <CardHeader>
          <CardTitle>Live Cognitive Panel</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4">
            {items.map((item) => (
              <motion.div
                key={item.label}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="p-3 rounded-xl bg-black/20 border border-matte-border/20"
              >
                <div className="flex items-center gap-2 mb-2">
                  <div className={`p-1.5 rounded-lg bg-black/30 ${item.color}`}>
                    <item.icon className="w-3 h-3" />
                  </div>
                  <span className="text-[8px] font-mono uppercase tracking-widest text-zinc-500">
                    {item.label}
                  </span>
                </div>
                <div className="text-xs font-mono text-zinc-200 truncate">{item.value}</div>
                {'sub' in item && item.sub && (
                  <div className="text-[8px] font-mono text-zinc-600 mt-0.5">{item.sub}</div>
                )}
              </motion.div>
            ))}

            {/* Confidence gauge */}
            <div className="p-3 rounded-xl bg-black/20 border border-matte-border/20 col-span-2">
              <div className="flex items-center gap-2 mb-3">
                <div className="p-1.5 rounded-lg bg-black/30 text-cyan-glow">
                  <Gauge className="w-3 h-3" />
                </div>
                <span className="text-[8px] font-mono uppercase tracking-widest text-zinc-500">
                  Confidence
                </span>
              </div>
              <div className="flex items-center gap-4">
                <div className="relative w-16 h-8 overflow-hidden">
                  <svg viewBox="0 0 36 20" className="w-16 h-8">
                    <path
                      d="M4 16 A14 14 0 0 1 32 16"
                      fill="none"
                      stroke="rgb(39,39,42)"
                      strokeWidth="3"
                      strokeLinecap="round"
                    />
                    <path
                      d="M4 16 A14 14 0 0 1 32 16"
                      fill="none"
                      stroke="rgb(0,242,254)"
                      strokeWidth="3"
                      strokeLinecap="round"
                      strokeDasharray={`${panel.confidence * 44} 44`}
                      transform="rotate(0 18 16)"
                    />
                    <circle
                      cx={18 + 14 * Math.cos((gaugeRotation * Math.PI) / 180)}
                      cy={16 + 14 * Math.sin((gaugeRotation * Math.PI) / 180)}
                      r="1.5"
                      fill="rgb(0,242,254)"
                    />
                  </svg>
                </div>
                <div>
                  <span className="text-lg font-bold font-mono text-cyan-glow">
                    {(panel.confidence * 100).toFixed(0)}%
                  </span>
                  <span className="text-[8px] font-mono text-zinc-600 ml-2">confidence</span>
                </div>
              </div>
            </div>
          </div>

          {/* Reflection summary */}
          <div className="mt-4 p-3 rounded-xl bg-black/20 border border-matte-border/20">
            <div className="flex items-center gap-2 mb-2">
              <BookOpen className="w-3 h-3 text-sky-400" />
              <span className="text-[8px] font-mono uppercase tracking-widest text-zinc-500">
                Reflection Summary
              </span>
            </div>
            <p className="text-[10px] font-mono text-zinc-400 leading-relaxed">
              {panel.reflectionSummary}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Active mission context */}
      {activeMission && (
        <Card>
          <CardHeader>
            <CardTitle>Current Mission</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono text-zinc-400">{activeMission.name}</span>
                <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded bg-cyan-dim/20 text-cyan-glow border border-cyan-border/30">
                  {activeMission.status}
                </span>
              </div>
              <div className="w-full h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                <div
                  className="h-full rounded-full bg-cyan-glow transition-all"
                  style={{ width: `${activeMission.progress}%` }}
                />
              </div>
              <div className="flex justify-between text-[8px] font-mono text-zinc-600">
                <span>Step: {activeMission.currentStep || 'N/A'}</span>
                <span>{Math.round(activeMission.progress)}%</span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Learning insights */}
      {learning && (learning as any).agent_reliability && (
        <Card>
          <CardHeader>
            <CardTitle>Agent Reliability</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1.5">
              {Object.entries((learning as any).agent_reliability).map(([agent, rate]) => (
                <div key={agent} className="flex items-center justify-between">
                  <span className="text-[10px] font-mono text-zinc-400">{agent}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-16 h-1 rounded-full bg-zinc-800 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${(rate as number) > 0.7 ? 'bg-emerald-400' : (rate as number) > 0.4 ? 'bg-amber-400' : 'bg-red-400'}`}
                        style={{ width: `${(rate as number) * 100}%` }}
                      />
                    </div>
                    <span className="text-[9px] font-mono text-zinc-500 w-8 text-right">
                      {((rate as number) * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
