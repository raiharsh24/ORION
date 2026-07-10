import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { CoreVisualParams } from './coreConfig';

interface RingDef {
  r: number;
  tube: number;
  speed: number;
  tilt: [number, number, number];
  opacity: number;
  color: string;
}

const RINGS: RingDef[] = [
  { r: 1.35, tube: 0.012, speed: 0.30, tilt: [0.35, 0, 0.15], opacity: 0.55, color: '#00f2fe' },
  { r: 1.75, tube: 0.010, speed: -0.22, tilt: [0.5, 0.2, 0], opacity: 0.45, color: '#4db8ff' },
  { r: 2.10, tube: 0.014, speed: 0.18, tilt: [0.2, 0.4, 0.3], opacity: 0.4, color: '#00f2fe' },
  { r: 2.45, tube: 0.008, speed: -0.13, tilt: [0.6, 0.1, 0.2], opacity: 0.3, color: '#ff8a3d' },
];

/**
 * Multiple independent concentric rings. Each rotates on its own tilted axis
 * at a different speed and opacity; outer rings accelerate under "executing".
 */
export const ConcentricRings: React.FC<{ params: React.MutableRefObject<CoreVisualParams> }> = ({ params }) => {
  const meshes = useRef<(THREE.Mesh | null)[]>([]);
  const mats = useRef<(THREE.MeshBasicMaterial | null)[]>([]);

  useFrame((_, dt) => {
    const p = params.current;
    const speedMul = 1 + (p.ringSpeed - 0.15) * 3;
    RINGS.forEach((ring, i) => {
      const m = meshes.current[i];
      const mat = mats.current[i];
      if (!m || !mat) return;
      m.rotation.z += dt * ring.speed * speedMul;
      mat.opacity = ring.opacity * (0.55 + p.glow * 0.5);
    });
  });

  return (
    <>
      {RINGS.map((ring, i) => (
        <mesh
          key={i}
          ref={(el) => {
            meshes.current[i] = el;
          }}
          rotation={ring.tilt}
        >
          <torusGeometry args={[ring.r, ring.tube, 16, 120]} />
          <meshBasicMaterial
            ref={(el) => {
              mats.current[i] = el;
            }}
            color={ring.color}
            transparent
            opacity={ring.opacity}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      ))}
    </>
  );
};
