import { create } from 'zustand';
import { eventBus, type AiEvent } from './eventBus';
import { useCommandCenterStore } from '../store/useCommandCenterStore';

/**
 * The single, canonical visual state of the FRIDAY OS.
 * Every UI component subscribes to THIS instead of keeping its own animation
 * logic. Business logic / future modules call `transition()` or `emit()`;
 * the sync layer (and the panels) react. No UI effect is coupled to business
 * code — only to this state + the event bus.
 */
export type AiState =
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'executing'
  | 'memory'
  | 'knowledge'
  | 'tool'
  | 'workflow'
  | 'error';

export interface AiStateMeta {
  agent?: string;
  workflow?: string;
  detail?: string;
}

/** Map the rich visual state onto the 5 states the 3D core understands. */
const CORE_MAP: Record<AiState, 'idle' | 'listening' | 'thinking' | 'speaking' | 'executing'> = {
  idle: 'idle',
  listening: 'listening',
  thinking: 'thinking',
  speaking: 'speaking',
  executing: 'executing',
  memory: 'thinking',
  knowledge: 'thinking',
  tool: 'executing',
  workflow: 'executing',
  error: 'idle',
};

interface AiStateStore {
  state: AiState;
  prev: AiState;
  meta: AiStateMeta;
  updatedAt: number;
  demoActive: boolean;
  setDemo: (on: boolean) => void;
  transition: (next: AiState, meta?: AiStateMeta) => void;
  emit: <T>(event: AiEvent, payload?: T) => void;
}

export const useAiStateStore = create<AiStateStore>((set, get) => ({
  state: 'idle',
  prev: 'idle',
  meta: {},
  updatedAt: Date.now(),
  demoActive: true,
  setDemo: (on) => set({ demoActive: on }),
  emit: (event, payload) => eventBus.emit(event, payload),
  transition: (next, meta = {}) => {
    const prev = get().state;
    const cc = useCommandCenterStore.getState();

    if (next === prev) {
      set({ meta: { ...get().meta, ...meta } });
    } else {
      set({ state: next, prev, meta, updatedAt: Date.now() });
      // Mirror into the legacy command-center store so the 3D core, tick load
      // bias, and any not-yet-migrated panel keep working during the transition.
      cc.setCoreState(CORE_MAP[next]);
      if (next === 'listening') {
        if (!cc.listening) cc.toggleListening();
      } else if (cc.listening) {
        cc.toggleListening();
      }
      eventBus.emit('AI_STATE_CHANGED', { from: prev, to: next, meta });
      if (next === 'listening' && prev !== 'listening') eventBus.emit('VOICE_STARTED');
      if (prev === 'listening' && next !== 'listening') eventBus.emit('VOICE_STOPPED');
      if (next === 'speaking' && prev !== 'speaking') eventBus.emit('VOICE_STARTED');
      if (prev === 'speaking' && next !== 'speaking') eventBus.emit('VOICE_STOPPED');
      if (next === 'workflow' || next === 'tool') eventBus.emit('WORKFLOW_STARTED', { state: next, meta });
      if ((prev === 'workflow' || prev === 'tool') && next !== 'workflow' && next !== 'tool') {
        eventBus.emit('WORKFLOW_COMPLETED', { meta });
      }
    }
  },
}));

/**
 * Gentle ambient demo: cycles through active states so the whole interface is
 * visibly synchronized even without a live backend. Pauses while the user is
 * interacting (non-demo state). Toggle via `setDemo(false)` for production.
 */
const DEMO_STATES: AiState[] = [
  'thinking', 'memory', 'knowledge', 'tool', 'workflow', 'speaking', 'listening', 'executing',
];
let demoIdx = 0;

export function startAiDemo(): () => void {
  const tick = setInterval(() => {
    const st = useAiStateStore.getState();
    if (!st.demoActive) return;
    // Only inject from a resting idle state; never interrupt a user-driven state.
    if (st.state === 'idle') {
      const next = DEMO_STATES[demoIdx % DEMO_STATES.length];
      demoIdx++;
      st.transition(next, { detail: 'demo' });
      // Auto-return to idle after a dwell (only if still our demo state).
      setTimeout(() => {
        const cur = useAiStateStore.getState();
        if (cur.state !== 'idle' && cur.meta.detail === 'demo') {
          cur.transition('idle');
        }
      }, 3600);
    }
  }, 6500);
  return () => clearInterval(tick);
}
