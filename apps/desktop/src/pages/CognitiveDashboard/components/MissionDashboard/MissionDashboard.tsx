import React from 'react';
import { motion } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardContent } from '../../../../components/ui/Card';
import { useCognitiveStore } from '../../store';
import { useMissionStore } from '../../../MissionCenter/store';
import { Target, ListChecks, Brain, Timer, Activity, BarChart3 } from 'lucide-react';

export const MissionDashboard: React.FC = () => {
  const { goals, context, schedulerStats, reflectionStats } = useCognitiveStore();
  const missions = useMissionStore((s) => s.missions);

  const ctx = context as Record<string, any> | null;
  const activeGoals = ctx?.goals?.active_goals ?? goals.filter((g) => g.status === 'active').length;
  const completedGoals = ctx?.goals?.completed_goals ?? goals.filter((g) => g.status === 'completed').length;
  const totalGoals = ctx?.goals?.total_goals ?? goals.length;

  const sched = schedulerStats as Record<string, any> | null;
  const pendingScheduled = sched?.stats?.pending_count ?? 0;
  const totalScheduled = sched?.stats?.total_scheduled ?? 0;

  const reflect = reflectionStats as Record<string, any> | null;
  const reflectionCount = reflect?.total_reflections ?? 0;
  const avgSuccessRate = reflect?.avg_stage_success_rate ?? 0;

  const activeMissions = missions.filter((m) => m.status === 'RUNNING');
  const failedMissions = missions.filter((m) => m.status === 'FAILED');

  const stats = [
    {
      icon: Target,
      label: 'Active Missions',
      value: activeMissions.length,
      sub: `${missions.length} total`,
      color: 'text-cyan-glow',
    },
    {
      icon: ListChecks,
      label: 'Active Goals',
      value: activeGoals,
      sub: `${completedGoals} completed of ${totalGoals}`,
      color: 'text-emerald-400',
    },
    {
      icon: Timer,
      label: 'Scheduled',
      value: pendingScheduled,
      sub: `${totalScheduled} total in queue`,
      color: 'text-amber-400',
    },
    {
      icon: Brain,
      label: 'Reflections',
      value: reflectionCount,
      sub: `${(avgSuccessRate * 100).toFixed(0)}% avg success`,
      color: 'text-purple-400',
    },
    {
      icon: Activity,
      label: 'Failed',
      value: failedMissions.length,
      sub: 'missions need attention',
      color: 'text-red-400',
    },
    {
      icon: BarChart3,
      label: 'Learning',
      value: ctx?.learning?.patterns_stored ?? 0,
      sub: 'patterns stored',
      color: 'text-sky-400',
    },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {stats.map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
          >
            <Card variant="glow" className="p-4">
              <div className="flex items-center gap-3 mb-3">
                <div className={`p-2 rounded-lg bg-black/30 ${stat.color}`}>
                  <stat.icon className="w-4 h-4" />
                </div>
                <span className="text-[9px] font-mono uppercase tracking-widest text-zinc-500">
                  {stat.label}
                </span>
              </div>
              <div className="text-2xl font-bold text-zinc-100 font-mono">{stat.value}</div>
              <div className="text-[9px] font-mono text-zinc-600 mt-0.5">{stat.sub}</div>
            </Card>
          </motion.div>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Goal Overview</CardTitle>
        </CardHeader>
        <CardContent>
          {goals.length === 0 ? (
            <div className="text-xs text-zinc-600 font-mono py-8 text-center">
              No goals created yet. Start a mission to generate goals.
            </div>
          ) : (
            <div className="space-y-2">
              {goals.slice(0, 10).map((goal) => (
                <div
                  key={goal.goal_id}
                  className="flex items-center justify-between p-3 rounded-xl bg-black/20 border border-matte-border/20"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span
                      className={`w-2 h-2 rounded-full flex-shrink-0 ${
                        goal.status === 'completed' ? 'bg-emerald-400' :
                        goal.status === 'failed' ? 'bg-red-400' :
                        goal.status === 'active' ? 'bg-cyan-glow' :
                        'bg-zinc-600'
                      }`}
                    />
                    <span className="text-xs font-mono text-zinc-300 truncate">
                      {goal.objective.slice(0, 80)}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 flex-shrink-0 ml-4">
                    <span className="text-[9px] font-mono text-zinc-500 uppercase">
                      {goal.status}
                    </span>
                    <div className="w-16 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-cyan-glow transition-all"
                        style={{ width: `${goal.progress_pct}%` }}
                      />
                    </div>
                    <span className="text-[10px] font-mono text-zinc-400 w-8 text-right">
                      {Math.round(goal.progress_pct)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
