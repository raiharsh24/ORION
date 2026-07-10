import type { CoreState } from '../../data/mock';

export interface CoreVisualParams {
  ringSpeed: number;      // multiplier on ring rotation
  intensity: number;      // emissive / light intensity
  particleRadius: number; // 1 = neutral; <1 inward (thinking), >1 expand (speaking)
  glow: number;           // bloom-ish glow level
  pulse: number;          // 0..1 breathing / response rhythm
}

export const STATE_PARAMS: Record<CoreState, CoreVisualParams> = {
  idle:      { ringSpeed: 0.15, intensity: 1.0,  particleRadius: 1.0,  glow: 0.6, pulse: 0.0 },
  listening: { ringSpeed: 0.30, intensity: 1.25, particleRadius: 1.06, glow: 0.8, pulse: 1.0 },
  thinking:  { ringSpeed: 0.45, intensity: 1.6,  particleRadius: 0.68, glow: 1.0, pulse: 0.4 },
  speaking:  { ringSpeed: 0.35, intensity: 1.5,  particleRadius: 1.18, glow: 1.0, pulse: 0.85 },
  executing: { ringSpeed: 0.60, intensity: 1.45, particleRadius: 0.95, glow: 1.0, pulse: 0.55 },
};

export const VISUAL_ORDER: CoreState[] = ['idle', 'thinking', 'speaking', 'executing', 'listening'];
