import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { useAiStateStore } from '../../sync/useAiStateStore';
import type { CoreVisualParams } from './coreConfig';

export const ConcentricRings: React.FC<{ params: React.MutableRefObject<CoreVisualParams> }> = ({ params }) => {
  // Ring references
  const outerHudRef = useRef<THREE.Mesh>(null!);
  const segmentedRef1 = useRef<THREE.Mesh>(null!);
  const segmentedRef2 = useRef<THREE.Mesh>(null!);
  const executionRef = useRef<THREE.Mesh>(null!);
  const holographicRef = useRef<THREE.Mesh>(null!);
  
  // Sweep/Scan ring and expanding ripple
  const scanRingRef = useRef<THREE.Mesh>(null!);
  const rippleRef = useRef<THREE.Mesh>(null!);
  const rippleMat = useRef<THREE.MeshBasicMaterial>(null!);

  useFrame((state, dt) => {
    const p = params.current;
    const aiState = useAiStateStore.getState().state;

    // Speeds map
    let speedMul = 1.0;
    let scanSpeed = 1.5;
    
    if (aiState === 'executing' || aiState === 'tool' || aiState === 'workflow') {
      speedMul = 2.5;
      scanSpeed = 3.5;
    } else if (aiState === 'thinking') {
      speedMul = 1.6;
      scanSpeed = 5.0; // very fast scan sweeps during thinking
    } else if (aiState === 'idle') {
      speedMul = 0.55;
      scanSpeed = 1.0;
    }

    // 1. Rotate Outer HUD Ring (Slow, Counter-clockwise)
    if (outerHudRef.current) {
      outerHudRef.current.rotation.z -= dt * 0.12 * speedMul;
    }

    // 2. Rotate Segmented Ring Sectors (Clockwise, Tilted)
    if (segmentedRef1.current && segmentedRef2.current) {
      segmentedRef1.current.rotation.z += dt * 0.4 * speedMul;
      segmentedRef2.current.rotation.z += dt * 0.4 * speedMul;
    }

    // 3. Rotate Execution Ring (Fast, Orange glow, Counter-clockwise)
    if (executionRef.current) {
      executionRef.current.rotation.z -= dt * 0.7 * speedMul;
    }

    // 4. Rotate Holographic Ring (Clockwise, Double segmentations)
    if (holographicRef.current) {
      holographicRef.current.rotation.z += dt * 0.22 * speedMul;
    }

    // 5. Vertical scan sweep for the Scan Ring
    if (scanRingRef.current) {
      scanRingRef.current.position.y = Math.sin(state.clock.elapsedTime * scanSpeed) * 1.15;
    }

    // 6. Expanding energy ripple loop
    if (rippleRef.current) {
      const rippleSpeed = aiState === 'executing' ? 2.8 : 1.4;
      const scaleVal = (state.clock.elapsedTime * rippleSpeed) % 3.0;
      rippleRef.current.scale.setScalar(scaleVal);
      if (rippleMat.current) {
        rippleMat.current.opacity = Math.max(0, (1 - scaleVal / 3.0) * 0.38 * p.glow);
      }
    }
  });

  return (
    <>
      {/* ── 1. OUTER HUD RING ── */}
      <mesh ref={outerHudRef} rotation={[0.6, 0.1, 0.2]}>
        <ringGeometry args={[2.45, 2.47, 64]} />
        <meshBasicMaterial
          color="#4db8ff"
          transparent
          opacity={0.25}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      {/* ── 2. SEGMENTED RINGS (Double sectors) ── */}
      <mesh ref={segmentedRef1} rotation={[0.35, 0, 0.15]}>
        <ringGeometry args={[1.3, 1.34, 64, 1, 0, Math.PI * 0.55]} />
        <meshBasicMaterial
          color="#00f2fe"
          transparent
          opacity={0.6}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
      <mesh ref={segmentedRef2} rotation={[0.35, 0, 0.15]}>
        <ringGeometry args={[1.3, 1.34, 64, 1, Math.PI, Math.PI * 0.55]} />
        <meshBasicMaterial
          color="#00f2fe"
          transparent
          opacity={0.6}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      {/* ── 3. SCAN RING (Vertical laser sweep) ── */}
      <mesh ref={scanRingRef} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[1.42, 0.012, 8, 64]} />
        <meshBasicMaterial
          color="#00f2fe"
          transparent
          opacity={0.55}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      {/* ── 4. EXECUTION RING ── */}
      <mesh ref={executionRef} rotation={[0.5, 0.2, 0]}>
        <ringGeometry args={[1.68, 1.72, 64]} />
        <meshBasicMaterial
          color="#ff8a3d"
          transparent
          opacity={0.8}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      {/* ── 5. HOLOGRAPHIC RING ── */}
      <mesh ref={holographicRef} rotation={[0.2, 0.4, 0.3]}>
        <ringGeometry args={[2.05, 2.1, 64, 1, 0.3, Math.PI * 1.3]} />
        <meshBasicMaterial
          color="#00f2fe"
          transparent
          opacity={0.4}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      {/* ── 6. ENERGY RIPPLE projection ── */}
      <mesh ref={rippleRef} rotation={[0.4, 0.2, 0]}>
        <ringGeometry args={[0.01, 1.75, 64]} />
        <meshBasicMaterial
          ref={rippleMat}
          color="#00f2fe"
          transparent
          opacity={0.35}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
    </>
  );
};
export default ConcentricRings;
