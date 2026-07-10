import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Sparkles } from '@react-three/drei';
import * as THREE from 'three';
import { useAiStateStore, type AiState } from '../../sync/useAiStateStore';

/** Per-state ambient mood: color + light intensity for the command room. */
const MOOD: Record<AiState, { color: string; intensity: number }> = {
  idle:      { color: '#2a4a7a', intensity: 0.35 },
  listening: { color: '#2f6db0', intensity: 0.42 },
  thinking:  { color: '#3a7fd0', intensity: 0.5 },
  speaking:  { color: '#2f6db0', intensity: 0.46 },
  executing: { color: '#3f8fe0', intensity: 0.62 },
  memory:    { color: '#4a6fd0', intensity: 0.5 },
  knowledge: { color: '#2f8fd0', intensity: 0.52 },
  tool:      { color: '#3f8fe0', intensity: 0.6 },
  workflow:  { color: '#3f8fe0', intensity: 0.6 },
  error:     { color: '#7a2a2a', intensity: 0.5 },
};

/**
 * The immersive command-room environment. Fog + base lighting are constant;
 * a single "mood" light eases its color/intensity toward the active AI state so
 * the whole room subtly shifts with FRIDAY's activity.
 */
export const AmbientScene: React.FC = () => {
  const moodRef = useRef<THREE.PointLight>(null!);
  const target = useRef(new THREE.Color('#2a4a7a'));
  const targetI = useRef(0.35);

  useFrame((_, dt) => {
    const state = useAiStateStore.getState().state;
    const m = MOOD[state];
    target.current.set(m.color);
    targetI.current = m.intensity;
    const ease = 1 - Math.pow(0.002, dt);
    if (moodRef.current) {
      moodRef.current.color.lerp(target.current, ease);
      moodRef.current.intensity += (targetI.current - moodRef.current.intensity) * ease;
    }
  });

  return (
    <>
      <fogExp2 attach="fog" args={['#05070d', 0.14]} />

      <ambientLight intensity={0.35} color="#2a4a7a" />
      <pointLight ref={moodRef} position={[0, 2, 4]} intensity={0.35} color="#2a4a7a" distance={14} decay={1.2} />
      <pointLight position={[-4, -1, -2]} intensity={0.85} color="#ff8a3d" distance={14} decay={1.2} />
      <pointLight position={[4, 1, 2]} intensity={0.9} color="#4db8ff" distance={14} decay={1.2} />

      {/* Far-field floating particles for cinematic depth */}
      <Sparkles count={70} scale={[14, 9, 9]} size={2.2} speed={0.18} color="#1f4a6b" opacity={0.45} />
    </>
  );
};
