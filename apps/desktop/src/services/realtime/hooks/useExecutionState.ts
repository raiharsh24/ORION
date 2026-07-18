import { useEffect, useState } from 'react';
import { streamManager } from '../streamManager';
import type { ExecutionStatePayload } from '../eventTypes';

function defaultState(): ExecutionStatePayload {
  return {
    goal: '',
    planner_tasks: [],
    active_task: '',
    selected_tool: '',
    confidence: 0,
    execution_stage: 'idle',
    completed_tasks: [],
    stage_status: 'idle',
  };
}

export function useExecutionState(): ExecutionStatePayload {
  const [state, setState] = useState<ExecutionStatePayload>(defaultState);

  useEffect(() => {
    const unsub = streamManager.subscribe('ExecutionStateUpdated', (event) => {
      setState(event.data as ExecutionStatePayload);
    });
    return () => unsub();
  }, []);

  return state;
}
