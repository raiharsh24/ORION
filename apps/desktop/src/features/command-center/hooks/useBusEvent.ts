import { useEffect } from 'react';
import { eventBus, type AiEvent } from '../sync/eventBus';

/**
 * Subscribe a component to a bus event for its lifetime.
 * Keeps panels decoupled: they react to events, never to business logic.
 */
export function useBusEvent<T = unknown>(
  event: AiEvent,
  handler: (payload: T) => void,
  deps: React.DependencyList = [],
): void {
  useEffect(() => {
    const off = eventBus.on<T>(event, handler);
    return off;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
