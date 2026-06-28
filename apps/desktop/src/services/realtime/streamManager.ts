import type { SystemEvent, SystemEventTopic } from './eventTypes';
import { API_BASE_URL, WS_BASE_URL } from '../../config/api';

export type ConnectionState = 'CONNECTED' | 'CONNECTING' | 'DISCONNECTED';
export type TransportType = 'WEBSOCKET' | 'SSE' | 'POLLING';

type EventCallback = (event: SystemEvent) => void;

class StreamManager {
  private ws: WebSocket | null = null;
  private sse: EventSource | null = null;
  private pollingIntervalId: any = null;
  
  private connectionState: ConnectionState = 'DISCONNECTED';
  private transportType: TransportType = 'POLLING';
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private baseDelay = 1000; // 1s base
  
  private lastEventTimestamp: number | null = null;
  private listeners: Map<string, Set<EventCallback>> = new Map();
  private stateListeners: Set<(state: { connectionState: ConnectionState; transportType: TransportType; reconnectAttempts: number; lastEventTimestamp: number | null }) => void> = new Set();
  
  private heartbeatIntervalId: any = null;
  private isOnline = true;
  
  constructor() {
    if (typeof window !== 'undefined') {
      window.addEventListener('online', () => this.handleNetworkChange(true));
      window.addEventListener('offline', () => this.handleNetworkChange(false));
    }
  }

  public connect() {
    if (this.connectionState === 'CONNECTED' || this.connectionState === 'CONNECTING') return;
    this.reconnectAttempts = 0;
    this.isOnline = typeof navigator !== 'undefined' ? navigator.onLine : true;
    
    if (!this.isOnline) {
      this.updateState('DISCONNECTED', 'POLLING');
      return;
    }
    
    this.tryWebSocket();
  }

  public disconnect() {
    this.cleanup();
    this.updateState('DISCONNECTED', 'POLLING');
  }

  public subscribe(topic: string, callback: EventCallback) {
    if (!this.listeners.has(topic)) {
      this.listeners.set(topic, new Set());
    }
    this.listeners.get(topic)!.add(callback);
    return () => {
      this.listeners.get(topic)?.delete(callback);
    };
  }

  public subscribeState(callback: (state: { connectionState: ConnectionState; transportType: TransportType; reconnectAttempts: number; lastEventTimestamp: number | null }) => void) {
    this.stateListeners.add(callback);
    callback(this.getDiagnostics());
    return () => {
      this.stateListeners.delete(callback);
    };
  }

  public getDiagnostics() {
    return {
      connectionState: this.connectionState,
      transportType: this.transportType,
      reconnectAttempts: this.reconnectAttempts,
      lastEventTimestamp: this.lastEventTimestamp,
    };
  }

  private updateState(state: ConnectionState, transport: TransportType) {
    this.connectionState = state;
    this.transportType = transport;
    this.notifyStateListeners();
  }

  private notifyStateListeners() {
    const diag = this.getDiagnostics();
    this.stateListeners.forEach((cb) => cb(diag));
  }

  private handleNetworkChange(online: boolean) {
    this.isOnline = online;
    if (!online) {
      this.cleanup();
      this.updateState('DISCONNECTED', 'POLLING');
    } else {
      this.reconnectAttempts = 0;
      this.tryWebSocket();
    }
  }

  private cleanup() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    if (this.sse) {
      this.sse.close();
      this.sse = null;
    }
    if (this.pollingIntervalId) {
      clearInterval(this.pollingIntervalId);
      this.pollingIntervalId = null;
    }
    if (this.heartbeatIntervalId) {
      clearInterval(this.heartbeatIntervalId);
      this.heartbeatIntervalId = null;
    }
  }

  private tryWebSocket() {
    this.cleanup();
    this.updateState('CONNECTING', 'WEBSOCKET');
    
    try {
      this.ws = new WebSocket(`${WS_BASE_URL}/ws`);
      
      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.updateState('CONNECTED', 'WEBSOCKET');
        this.startHeartbeat();
      };
      
      this.ws.onmessage = (event) => {
        if (event.data === 'pong') return;
        try {
          const parsed = JSON.parse(event.data) as SystemEvent;
          this.dispatchEvent(parsed);
        } catch (e) {
          // ignore parsing error
        }
      };
      
      this.ws.onerror = () => {
        // Will fail to onclose
      };
      
      this.ws.onclose = () => {
        if (this.connectionState === 'CONNECTED' || this.connectionState === 'CONNECTING') {
          this.handleReconnectFailure('WEBSOCKET');
        }
      };
    } catch (e) {
      this.handleReconnectFailure('WEBSOCKET');
    }
  }

  private trySSE() {
    this.cleanup();
    this.updateState('CONNECTING', 'SSE');
    
    try {
      this.sse = new EventSource(`${API_BASE_URL}/events`);
      
      this.sse.onopen = () => {
        this.reconnectAttempts = 0;
        this.updateState('CONNECTED', 'SSE');
      };
      
      this.sse.onerror = () => {
        this.sse?.close();
        this.handleReconnectFailure('SSE');
      };
      
      // Handle generic message or add custom event listeners
      const topics: SystemEventTopic[] = [
        'MissionStarted', 'MissionUpdated', 'MissionCompleted', 
        'MissionFailed', 'MissionCancelled', 'TelemetryUpdated', 
        'KernelHealthChanged', 'ServiceStatusChanged'
      ];
      
      topics.forEach((topic) => {
        this.sse?.addEventListener(topic, (e: any) => {
          try {
            const parsed = JSON.parse(e.data) as SystemEvent;
            this.dispatchEvent(parsed);
          } catch (err) {
            // ignore
          }
        });
      });
      
    } catch (e) {
      this.handleReconnectFailure('SSE');
    }
  }

  private tryPollingFallback() {
    this.cleanup();
    this.updateState('CONNECTED', 'POLLING');
    
    // Polling triggers generic dispatchers that notify subscribers periodically
    // No-op here since MissionCenterPage does the fallback polling directly when POLLING is active
  }

  private handleReconnectFailure(failedTransport: TransportType) {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = this.baseDelay * Math.pow(2, this.reconnectAttempts);
      
      setTimeout(() => {
        if (failedTransport === 'WEBSOCKET') {
          this.tryWebSocket();
        } else {
          this.trySSE();
        }
      }, delay);
    } else {
      // Switch fallback
      this.reconnectAttempts = 0;
      if (failedTransport === 'WEBSOCKET') {
        this.trySSE();
      } else {
        this.tryPollingFallback();
      }
    }
  }

  private startHeartbeat() {
    this.heartbeatIntervalId = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send('ping');
      }
    }, 10000); // 10s heartbeat
  }

  private dispatchEvent(event: SystemEvent) {
    this.lastEventTimestamp = Date.now();
    this.notifyStateListeners();
    
    const topic = event.topic;
    
    // Wildcard list
    this.listeners.get('*')?.forEach((cb) => cb(event));
    
    // Specific list
    this.listeners.get(topic)?.forEach((cb) => cb(event));
  }
}

export const streamManager = new StreamManager();
