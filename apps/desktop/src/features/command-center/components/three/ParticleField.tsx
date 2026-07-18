import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { useAiStateStore } from '../../sync/useAiStateStore';
import type { CoreVisualParams } from './coreConfig';

const COUNT = 500;

interface ParticleData {
  dirX: number;
  dirY: number;
  dirZ: number;
  r: number;
  speed: number;
}

export const ParticleField: React.FC<{ params: React.MutableRefObject<CoreVisualParams> }> = ({ params }) => {
  const groupRef = useRef<THREE.Points>(null!);

  // Generate initial particle vectors and coordinates
  const particles = useMemo(() => {
    const list: ParticleData[] = [];
    for (let i = 0; i < COUNT; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const dirX = Math.sin(phi) * Math.cos(theta);
      const dirY = Math.cos(phi);
      const dirZ = Math.sin(phi) * Math.sin(theta);
      const baseR = 1.4 + Math.random() * 2.2;
      list.push({ dirX, dirY, dirZ, r: baseR, speed: 0.3 + Math.random() * 0.7 });
    }
    return list;
  }, []);

  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const pos = new Float32Array(COUNT * 3);
    for (let i = 0; i < COUNT; i++) {
      const p = particles[i];
      pos[i * 3] = p.dirX * p.r;
      pos[i * 3 + 1] = p.dirY * p.r * 0.8;
      pos[i * 3 + 2] = p.dirZ * p.r;
    }
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    return g;
  }, [particles]);

  const mat = useMemo(
    () =>
      new THREE.PointsMaterial({
        color: new THREE.Color('#7fe9ff'),
        size: 0.024,
        transparent: true,
        opacity: 0.65,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        sizeAttenuation: true,
      }),
    [],
  );

  useFrame((_, dt) => {
    const aiState = useAiStateStore.getState().state;
    const p = params.current;
    const g = groupRef.current;
    
    // Customize particle colors, speeds, sizes based on stage
    let flowVelocity = 0.0;
    let orbitSpeed = 0.05;
    let particleSize = 0.022;
    let colorHex = '#7fe9ff';

    if (aiState === 'thinking' || aiState === 'memory' || aiState === 'knowledge') {
      flowVelocity = -0.8; // Flow inward (thinking ingestion)
      orbitSpeed = 0.2;
      particleSize = 0.016;
      colorHex = '#a78bfa'; // Purple hint
    } else if (aiState === 'executing' || aiState === 'tool' || aiState === 'workflow') {
      flowVelocity = 1.8; // Burst outward (execution sparks)
      orbitSpeed = 0.85;
      particleSize = 0.028;
      colorHex = '#ff8a3d'; // Orange sparks
    } else if (aiState === 'idle') {
      flowVelocity = 0.04; // Slow drifting breath
      orbitSpeed = 0.03;
      colorHex = '#7fe9ff';
    }

    // Update coordinates array in BufferGeometry
    const posAttr = geo.getAttribute('position') as THREE.BufferAttribute;
    const arr = posAttr.array as Float32Array;

    for (let i = 0; i < COUNT; i++) {
      const part = particles[i];
      part.r += flowVelocity * part.speed * dt;
      
      // Warp bounds
      if (part.r < 0.65) {
        part.r = 3.6; // Wrap back to outer orbit
      } else if (part.r > 3.7) {
        part.r = 0.75; // Wrap back to inner core
      }

      arr[i * 3] = part.dirX * part.r;
      arr[i * 3 + 1] = part.dirY * part.r * 0.75; // flattened slightly
      arr[i * 3 + 2] = part.dirZ * part.r;
    }
    posAttr.needsUpdate = true;

    // Orbit coordinates
    g.rotation.y += dt * orbitSpeed;
    g.rotation.x += dt * (orbitSpeed * 0.25);

    // Apply properties
    mat.size = particleSize;
    mat.color.set(colorHex);
    mat.opacity = 0.45 + p.glow * 0.25;
  });

  return <points ref={groupRef} geometry={geo} material={mat} />;
};
export default ParticleField;
