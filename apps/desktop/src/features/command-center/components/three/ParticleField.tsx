import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { CoreVisualParams } from './coreConfig';

const COUNT = 700;

/**
 * Surrounding particle field. Orbits slowly as a group and scales inward
 * (thinking) / outward (speaking) via the shared visual params. Cheap: no
 * per-vertex updates, additive blending for a subtle glow.
 */
export const ParticleField: React.FC<{ params: React.MutableRefObject<CoreVisualParams> }> = ({ params }) => {
  const groupRef = useRef<THREE.Points>(null!);
  const scaleRef = useRef(1);

  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const pos = new Float32Array(COUNT * 3);
    for (let i = 0; i < COUNT; i++) {
      const r = 2.6 + Math.random() * 1.2;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = r * Math.cos(phi) * 0.6;
      pos[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
    }
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    return g;
  }, []);

  const mat = useMemo(
    () =>
      new THREE.PointsMaterial({
        color: new THREE.Color('#7fe9ff'),
        size: 0.025,
        transparent: true,
        opacity: 0.6,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        sizeAttenuation: true,
      }),
    [],
  );

  useFrame((_, dt) => {
    const p = params.current;
    scaleRef.current += (p.particleRadius - scaleRef.current) * Math.min(1, dt * 2);
    const g = groupRef.current;
    g.rotation.y += dt * 0.05;
    g.rotation.x += dt * 0.01;
    g.scale.setScalar(scaleRef.current);
    mat.opacity = 0.4 + p.glow * 0.25;
  });

  return <points ref={groupRef} geometry={geo} material={mat} />;
};
