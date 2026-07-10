import type { AiState } from '../../sync/useAiStateStore';

export interface CoreVisualParams {
  ringSpeed: number;      // multiplier on ring rotation
  intensity: number;      // emissive / light intensity
  particleRadius: number; // 1 = neutral; <1 inward (thinking), >1 expand (speaking)
  glow: number;           // bloom-ish glow level
  pulse: number;          // 0..1 breathing / response rhythm
  halo: number;           // volumetric core halo strength
  accentT: number;        // 0 = cyan, 1 = red (error state)
}

/** One visual target per canonical AI state — the single source of core motion. */
export const STATE_PARAMS: Record<AiState, CoreVisualParams> = {
  idle:      { ringSpeed: 0.15, intensity: 1.0,  particleRadius: 1.0,  glow: 0.6, pulse: 0.0,  halo: 0.5,  accentT: 0 },
  listening: { ringSpeed: 0.30, intensity: 1.3,  particleRadius: 1.05, glow: 0.85, pulse: 1.0, halo: 0.8, accentT: 0 },
  thinking:  { ringSpeed: 0.45, intensity: 1.7,  particleRadius: 0.6,  glow: 1.0, pulse: 0.4, halo: 1.0, accentT: 0 },
  speaking:  { ringSpeed: 0.35, intensity: 1.55, particleRadius: 1.16, glow: 1.0, pulse: 0.9, halo: 0.95, accentT: 0 },
  executing: { ringSpeed: 0.60, intensity: 1.5,  particleRadius: 0.92, glow: 1.0, pulse: 0.6, halo: 0.9, accentT: 0 },
  memory:    { ringSpeed: 0.42, intensity: 1.7,  particleRadius: 0.66, glow: 1.0, pulse: 0.5, halo: 1.0, accentT: 0 },
  knowledge: { ringSpeed: 0.50, intensity: 1.65, particleRadius: 1.08, glow: 1.0, pulse: 0.35, halo: 0.95, accentT: 0 },
  tool:      { ringSpeed: 0.58, intensity: 1.48, particleRadius: 0.9,  glow: 1.0, pulse: 0.6, halo: 0.9, accentT: 0 },
  workflow:  { ringSpeed: 0.52, intensity: 1.5,  particleRadius: 0.94, glow: 1.0, pulse: 0.55, halo: 0.9, accentT: 0 },
  error:     { ringSpeed: 0.20, intensity: 0.9,  particleRadius: 0.98, glow: 0.5, pulse: 0.9, halo: 0.4, accentT: 1 },
};

export const VISUAL_ORDER: AiState[] = [
  'idle', 'thinking', 'speaking', 'executing', 'memory',
  'knowledge', 'tool', 'workflow', 'listening', 'error',
];
