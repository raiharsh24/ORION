import { useEffect } from 'react';
import { streamManager } from '../streamManager';
import { useMissionStore } from '../../../pages/MissionCenter/store';
import type { SystemEvent } from '../eventTypes';
import type { Mission } from '../../../pages/MissionCenter/types';

export const useMissionEvents = () => {
  useEffect(() => {
    const handleEvent = (event: SystemEvent) => {
      const topic = event.topic;
      if (
        topic === 'MissionStarted' || 
        topic === 'MissionUpdated' || 
        topic === 'MissionCompleted' || 
        topic === 'MissionFailed' || 
        topic === 'MissionCancelled'
      ) {
        const mission = event.data as Mission;
        
        useMissionStore.setState((state) => {
          const exists = state.missions.some((m) => m.id === mission.id);
          const nextMissions = exists
            ? state.missions.map((m) => (m.id === mission.id ? mission : m))
            : [...state.missions, mission];
            
          const archived = nextMissions.filter(
            (m) => m.status === 'COMPLETED' || m.status === 'FAILED' || m.status === 'CANCELLED'
          );
          
          return {
            missions: nextMissions,
            historyMissions: archived
          };
        });
      }
    };

    const unsubStarted = streamManager.subscribe('MissionStarted', handleEvent);
    const unsubUpdated = streamManager.subscribe('MissionUpdated', handleEvent);
    const unsubCompleted = streamManager.subscribe('MissionCompleted', handleEvent);
    const unsubFailed = streamManager.subscribe('MissionFailed', handleEvent);
    const unsubCancelled = streamManager.subscribe('MissionCancelled', handleEvent);

    return () => {
      unsubStarted();
      unsubUpdated();
      unsubCompleted();
      unsubFailed();
      unsubCancelled();
    };
  }, []);
};
export default useMissionEvents;
