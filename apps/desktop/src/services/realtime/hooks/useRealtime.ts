import { useEffect, useState } from 'react';
import { streamManager } from '../streamManager';
import type { ConnectionState, TransportType } from '../streamManager';

export interface RealtimeDiagnostics {
  connectionState: ConnectionState;
  transportType: TransportType;
  reconnectAttempts: number;
  lastEventTimestamp: number | null;
}

export const useRealtime = (): RealtimeDiagnostics => {
  const [state, setState] = useState<RealtimeDiagnostics>({
    connectionState: 'DISCONNECTED',
    transportType: 'POLLING',
    reconnectAttempts: 0,
    lastEventTimestamp: null,
  });

  useEffect(() => {
    // Initiate connection on mount
    streamManager.connect();
    
    // Subscribe to state triggers
    const unsubscribe = streamManager.subscribeState((diag) => {
      setState(diag);
    });
    
    return () => {
      unsubscribe();
    };
  }, []);

  return state;
};
export default useRealtime;
