/**
 * Lightweight, typed UI Event Bus.
 *
 * Decouples "something happened" from "what the UI does about it". Any module
 * (present or future) can `emit` an event; UI layers `on` it and react. No
 * business logic is coupled to visual effects.
 */
export type AiEvent =
  | 'AI_STATE_CHANGED'
  | 'MEMORY_UPDATED'
  | 'GRAPH_UPDATED'
  | 'AGENT_STARTED'
  | 'AGENT_FINISHED'
  | 'WORKFLOW_STARTED'
  | 'WORKFLOW_COMPLETED'
  | 'VOICE_STARTED'
  | 'VOICE_STOPPED';

type Handler<T = unknown> = (payload: T) => void;

class EventBus {
  private map = new Map<AiEvent, Set<Handler>>();

  on<T = unknown>(event: AiEvent, fn: Handler<T>): () => void {
    if (!this.map.has(event)) this.map.set(event, new Set());
    this.map.get(event)!.add(fn as Handler);
    return () => this.off(event, fn);
  }

  off<T = unknown>(event: AiEvent, fn: Handler<T>): void {
    this.map.get(event)?.delete(fn as Handler);
  }

  emit<T = unknown>(event: AiEvent, payload?: T): void {
    this.map.get(event)?.forEach((fn) => {
      try {
        fn(payload);
      } catch (err) {
        console.error('[eventBus]', event, err);
      }
    });
  }
}

export const eventBus = new EventBus();
