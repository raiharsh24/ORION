import { useEffect } from 'react';
import { streamManager } from '../streamManager';
import { useCognitiveStore } from '../../../pages/CognitiveDashboard/store';
import type { SystemEvent } from '../eventTypes';

const COGNITIVE_TOPICS = [
  'cognitive.goal.created',
  'cognitive.goal.updated',
  'cognitive.goal.milestone_completed',
  'cognitive.scheduler.started',
  'cognitive.scheduler.stopped',
  'cognitive.mission.delegated',
  'cognitive.mission.recovered',
  'cognitive.learning.updated',
] as const;

export const useCognitiveEvents = () => {
  const addTimelineEvent = useCognitiveStore((s) => s.addTimelineEvent);
  const updatePanel = useCognitiveStore((s) => s.updatePanel);

  useEffect(() => {
    const handleEvent = (event: SystemEvent) => {
      const topic = event.topic;
      const data = event.data as Record<string, unknown>;
      const ts = event.timestamp;
      const id = `${topic}:${ts}:${Math.random().toString(16).slice(2, 8)}`;

      let summary: string = topic;
      let detail = JSON.stringify(data).slice(0, 200);
      let category: 'cognitive' | 'learning' = 'cognitive';

      if (topic === 'cognitive.goal.created') {
        summary = `Goal created: ${(data.objective as string)?.slice(0, 60)}`;
        detail = `Goal ${data.goal_id} — ${data.objective}`;
        category = 'cognitive';
      } else if (topic === 'cognitive.goal.updated') {
        summary = `Goal updated: ${(data.objective as string)?.slice(0, 60)} → ${data.status}`;
        detail = `Progress: ${data.progress_pct}%`;
        category = 'cognitive';
        updatePanel({ memoryUpdates: Date.now() });
      } else if (topic === 'cognitive.goal.milestone_completed') {
        summary = `Milestone: ${data.milestone_name}`;
        detail = `Goal ${data.goal_id} — ${data.progress_pct}% complete`;
        category = 'cognitive';
      } else if (topic === 'cognitive.scheduler.started') {
        summary = 'Scheduler started';
        detail = 'Background scheduler loop activated';
        category = 'cognitive';
      } else if (topic === 'cognitive.scheduler.stopped') {
        summary = 'Scheduler stopped';
        detail = 'Background scheduler loop deactivated';
        category = 'cognitive';
      } else if (topic === 'cognitive.mission.delegated') {
        summary = `Mission delegated: ${(data.objective as string)?.slice(0, 60)}`;
        detail = `Type: ${data.workflow_type} | Agents: ${(data.agent_ids as string[])?.join(', ')}`;
        category = 'cognitive';
      } else if (topic === 'cognitive.mission.recovered') {
        summary = `Recovery: ${data.workflow_id}`;
        detail = `Strategy: ${data.strategy}`;
        category = 'cognitive';
      } else if (topic === 'cognitive.learning.updated') {
        summary = `Learning updated: ${data.learning_type}`;
        detail = data.summary as string;
        category = 'learning';
      }

      addTimelineEvent({
        id,
        type: category === 'learning' ? 'learning_update' : 'goal_event',
        summary,
        detail,
        timestamp: ts,
        status: 'info',
      });
    };

    const unsubs = COGNITIVE_TOPICS.map((topic) =>
      streamManager.subscribe(topic, handleEvent)
    );

    return () => {
      unsubs.forEach((unsub) => unsub());
    };
  }, [addTimelineEvent, updatePanel]);
};

export default useCognitiveEvents;
