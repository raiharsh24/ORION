import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardContent } from '../../../../components/ui/Card';
import { useCognitiveStore } from '../../store';
import {
  CircleCheck, CircleX, Info, AlertTriangle,
} from 'lucide-react';

const statusIcon = (status: string) => {
  switch (status) {
    case 'success': return <CircleCheck className="w-3 h-3 text-emerald-400" />;
    case 'failure': return <CircleX className="w-3 h-3 text-red-400" />;
    case 'warning': return <AlertTriangle className="w-3 h-3 text-amber-400" />;
    default: return <Info className="w-3 h-3 text-cyan-glow" />;
  }
};



const typeLabel = (type: string) => {
  const labels: Record<string, string> = {
    mission_state: 'Mission',
    tool_exec: 'Tool',
    agent_delegation: 'Agent',
    recovery: 'Recovery',
    learning_update: 'Learning',
    goal_event: 'Goal',
    scheduler_event: 'Scheduler',
    system: 'System',
  };
  return labels[type] || type;
};

export const TimelineView: React.FC = () => {
  const timeline = useCognitiveStore((s) => s.timeline);
  const items = useMemo(() => timeline.slice(0, 100), [timeline]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Event Timeline</CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <div className="text-xs text-zinc-600 font-mono py-8 text-center">
            No events yet. Events will appear here in real-time as the system operates.
          </div>
        ) : (
          <div className="relative">
            <div className="absolute left-4 top-0 bottom-0 w-px bg-matte-border/30" />
            <div className="space-y-1">
              {items.map((event) => (
                <motion.div
                  key={event.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="relative pl-10 py-2 hover:bg-white/5 rounded-lg transition-colors group"
                >
                  <div className="absolute left-[11px] top-2.5 w-[9px] h-[9px] rounded-full bg-matte-card border-2 border-matte-border/50 flex items-center justify-center group-hover:border-cyan-border/50 transition-colors">
                    <span className="scale-75">{statusIcon(event.status)}</span>
                  </div>

                  <div className="flex items-start gap-2 min-w-0">
                    <span className="text-[9px] font-mono text-zinc-600 flex-shrink-0 mt-0.5 w-14">
                      {new Date(event.timestamp * 1000).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[9px] font-mono uppercase tracking-widest text-zinc-500 flex-shrink-0">
                          {typeLabel(event.type)}
                        </span>
                        <span className="text-xs font-mono text-zinc-300 truncate">
                          {event.summary}
                        </span>
                      </div>
                      {event.detail && (
                        <div className="text-[9px] font-mono text-zinc-600 mt-0.5 truncate">
                          {event.detail}
                        </div>
                      )}
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
