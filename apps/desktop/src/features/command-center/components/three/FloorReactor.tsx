import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { CoreVisualParams } from './coreConfig';

const FLOOR = -1.6;
const FLOOR_RINGS = [
  { r: 0.9, speed: 0.3, op: 0.5 },
  { r: 1.4, speed: -0.22, op: 0.4 },
  { r: 1.95, speed: 0.16, op: 0.3 },
];

/**
 * Holographic floor emitter beneath the core: a circular platform, glowing
 * concentric rings, a pulsing central energy disc, and a soft point light for
 * the illusion of reflection. Brightens with the active visual state.
 */
export const FloorReactor: React.FC<{ params: React.MutableRefObject<CoreVisualParams> }> = ({ params }) => {
  const rings = useRef<(THREE.Mesh | null)[]>([]);
  const ringMats = useRef<(THREE.MeshBasicMaterial | null)[]>([]);
  const discMat = useRef<THREE.MeshStandardMaterial>(null!);
  const energyRef = useRef<THREE.Mesh>(null!);
  const energyMat = useRef<THREE.MeshBasicMaterial>(null!);

  useFrame((state, dt) => {
    const t = state.clock.elapsedTime;
    const p = params.current;

    FLOOR_RINGS.forEach((ring, i) => {
      const m = rings.current[i];
      const mat = ringMats.current[i];
      if (!m || !mat) return;
      m.rotation.z += dt * ring.speed * (0.6 + p.ringSpeed * 2);
      mat.opacity = ring.op * (0.5 + p.glow * 0.5);
    });

    if (discMat.current) discMat.current.emissiveIntensity = 0.4 + p.intensity * 0.4 + Math.sin(t * 2) * 0.1 * p.pulse;

    const es = 1 + Math.sin(t * 3) * 0.06 + p.pulse * 0.08;
    energyRef.current.scale.set(es, es, es);
    energyMat.current.opacity = 0.25 + p.glow * 0.3;
  });

  return (
    <group position={[0, FLOOR, 0]}>
      {/* platform */}
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[2.2, 2.2, 0.03, 64]} />
        <meshStandardMaterial
          ref={discMat}
          color="#04141a"
          emissive="#00343f"
          emissiveIntensity={0.4}
          roughness={0.4}
          metalness={0.3}
        />
      </mesh>

      {/* glowing concentric floor rings */}
      {FLOOR_RINGS.map((ring, i) => (
        <mesh
          key={i}
          ref={(el) => {
            rings.current[i] = el;
          }}
          rotation={[-Math.PI / 2, 0, 0]}
        >
          <torusGeometry args={[ring.r, 0.01, 12, 120]} />
          <meshBasicMaterial
            ref={(el) => {
              ringMats.current[i] = el;
            }}
            color="#00f2fe"
            transparent
            opacity={ring.op}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      ))}

      {/* central energy pulse */}
      <mesh ref={energyRef} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.2, 0.5, 48]} />
        <meshBasicMaterial
          ref={energyMat}
          color="#00f2fe"
          transparent
          opacity={0.3}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      <pointLight color="#00f2fe" intensity={0.6} distance={5} position={[0, 0.3, 0]} decay={1.5} />
    </group>
  );
};
