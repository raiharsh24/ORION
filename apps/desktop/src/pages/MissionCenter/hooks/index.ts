import { useKernelStore, useHealthStore, useTelemetryStore, useMissionStore } from '../store';

export const useKernelHealth = () => {
  const { cpuUtilization, memoryUsageBytes, uptime, kernelState } = useKernelStore();
  return { 
    cpu: cpuUtilization, 
    memory: +(memoryUsageBytes / 1024 / 1024).toFixed(1), 
    uptime, 
    state: kernelState 
  };
};

export const useServiceStatus = () => {
  const { services } = useHealthStore();
  return { services };
};

export const useTelemetry = () => {
  const { executionTimeMs, eventsCount, currentTool, workflow, latency, fps, memory } = useTelemetryStore();
  const { activeMissionId } = useMissionStore();
  
  return { 
    telemetry: {
      executionTimeMs,
      eventsCount,
      currentTool,
      missionId: activeMissionId || 'None',
      workflow,
      latency,
      fps,
      memory
    }
  };
};
