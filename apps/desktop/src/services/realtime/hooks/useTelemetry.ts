import { useEffect } from 'react';
import { streamManager } from '../streamManager';
import { useTelemetryStore } from '../../../pages/MissionCenter/store';
import type { SystemEvent } from '../eventTypes';
import type { TelemetryUpdatedPayload } from '../eventTypes';

export const useTelemetry = () => {
  useEffect(() => {
    const handleTelemetry = (event: SystemEvent) => {
      if (event.topic === 'TelemetryUpdated') {
        const data = event.data as TelemetryUpdatedPayload;
        useTelemetryStore.setState({
          executionTimeMs: data.executionTimeMs,
          eventsCount: data.eventsCount,
          currentTool: data.currentTool,
          workflow: data.workflow,
          latency: data.latency,
          fps: data.fps,
          memory: data.memory,
          current_desktop_task: data.current_desktop_task,
          last_executed_action: data.last_executed_action,
          average_execution_time_ms: data.average_execution_time_ms,
          failure_count: data.failure_count,
          queue_length: data.queue_length,
          isOffline: false,
          error: null
        });
      }
    };

    const unsubscribe = streamManager.subscribe('TelemetryUpdated', handleTelemetry);
    return () => {
      unsubscribe();
    };
  }, []);
};
export default useTelemetry;
