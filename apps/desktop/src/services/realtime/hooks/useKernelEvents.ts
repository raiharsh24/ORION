import { useEffect } from 'react';
import { streamManager } from '../streamManager';
import { useKernelStore, useHealthStore } from '../../../pages/MissionCenter/store';
import type { SystemEvent } from '../eventTypes';
import type { KernelHealthChangedPayload, ServiceStatusChangedPayload } from '../eventTypes';

export const useKernelEvents = () => {
  useEffect(() => {
    const handleKernelEvent = (event: SystemEvent) => {
      if (event.topic === 'KernelHealthChanged') {
        const data = event.data as KernelHealthChangedPayload;
        useKernelStore.setState({
          kernelState: data.kernel_state,
          bootTimeMs: data.boot_time_ms,
          registeredServicesCount: data.registered_services_count,
          cpuUtilization: data.cpu_utilization,
          memoryUsageBytes: data.memory_usage_bytes,
          uptime: data.uptime,
          isOffline: false,
          error: null
        });
      } else if (event.topic === 'ServiceStatusChanged') {
        const data = event.data as ServiceStatusChangedPayload;
        useHealthStore.setState({
          services: data.services.map((s) => ({
            name: s.name,
            status: s.status,
            message: s.message
          })),
          isOffline: false,
          error: null
        });
      }
    };

    const unsubKernel = streamManager.subscribe('KernelHealthChanged', handleKernelEvent);
    const unsubHealth = streamManager.subscribe('ServiceStatusChanged', handleKernelEvent);

    return () => {
      unsubKernel();
      unsubHealth();
    };
  }, []);
};
export default useKernelEvents;
