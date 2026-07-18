import { useRef } from 'react';
import { useFrame, type ThreeEvent } from '@react-three/fiber';
import * as THREE from 'three';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';
import { useAiStateStore } from '../../sync/useAiStateStore';
import { VISUAL_ORDER } from './coreConfig';
import type { CoreVisualParams } from './coreConfig';

const CYAN = new THREE.Color('#00f2fe');
const RED = new THREE.Color('#ff5470');
const tmpColor = new THREE.Color();

export const CoreEnergySphere: React.FC<{ params: React.MutableRefObject<CoreVisualParams> }> = ({ params }) => {
  const coreRef = useRef<THREE.Mesh>(null!);
  const shellRef = useRef<THREE.Mesh>(null!);
  const wireRef1 = useRef<THREE.Mesh>(null!);
  const wireRef2 = useRef<THREE.Mesh>(null!);
  const lightRef = useRef<THREE.PointLight>(null!);
  const coreMat = useRef<THREE.MeshStandardMaterial>(null!);

  useFrame((state, dt) => {
    const t = state.clock.elapsedTime;
    const p = params.current;
    const voice = useCommandCenterStore.getState().voiceLevel;
    const aiState = useAiStateStore.getState().state;

    // State-bound pulse frequency and rotation speeds
    let pulseSpeed = 2.2;
    let rotationSpeed = 0.25;
    
    if (aiState === 'thinking' || aiState === 'memory' || aiState === 'knowledge') {
      pulseSpeed = 6.0; // fast thinking pulse
      rotationSpeed = 0.65;
    } else if (aiState === 'executing' || aiState === 'tool' || aiState === 'workflow') {
      pulseSpeed = 9.0; // intense execution pulse
      rotationSpeed = 1.4;
    } else if (aiState === 'idle') {
      pulseSpeed = 1.4; // calm idle breathing
      rotationSpeed = 0.15;
    }

    // Emissive intensity pulsing
    coreMat.current.emissiveIntensity =
      (0.95 + p.intensity * 0.55) + Math.sin(t * pulseSpeed) * 0.15 * p.pulse + voice * 1.5;
    
    tmpColor.copy(CYAN).lerp(RED, p.accentT);
    coreMat.current.emissive.copy(tmpColor);

    // Scale pulsations
    const s = 1 + Math.sin(t * pulseSpeed) * 0.035 + p.pulse * 0.04 + voice * 0.07;
    coreRef.current.scale.setScalar(s);
    coreRef.current.rotation.y += dt * rotationSpeed;
    coreRef.current.rotation.x += dt * (rotationSpeed * 0.5);

    // Inner wireframe counter-rotations
    wireRef1.current.rotation.y -= dt * (rotationSpeed * 1.5);
    wireRef1.current.rotation.x += dt * (rotationSpeed * 0.8);

    wireRef2.current.rotation.y += dt * (rotationSpeed * 1.2);
    wireRef2.current.rotation.z -= dt * (rotationSpeed * 0.6);

    // Outer translucent shell pulsations
    shellRef.current.scale.setScalar(1.25 + Math.sin(t * (pulseSpeed * 0.4)) * 0.03);
    shellRef.current.rotation.y -= dt * (rotationSpeed * 0.4);

    if (lightRef.current) {
      lightRef.current.intensity = 0.9 + p.intensity * 1.6 + voice * 2.2;
    }
  });

  const onClick = (e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    const s = useAiStateStore.getState();
    const cur = s.state;
    const next = VISUAL_ORDER[(VISUAL_ORDER.indexOf(cur) + 1) % VISUAL_ORDER.length];
    s.transition(next);
  };

  return (
    <group onClick={onClick}>
      {/* 1. Core energy nucleus */}
      <mesh ref={coreRef}>
        <sphereGeometry args={[0.85, 64, 64]} />
        <meshStandardMaterial
          ref={coreMat}
          color="#00141c"
          emissive="#00f2fe"
          emissiveIntensity={1.4}
          roughness={0.2}
          metalness={0.4}
        />
      </mesh>

      {/* 2. Inner wireframe layer 1 */}
      <mesh ref={wireRef1} scale={0.65}>
        <icosahedronGeometry args={[1.05, 1]} />
        <meshBasicMaterial color="#9bf6ff" wireframe transparent opacity={0.16} />
      </mesh>

      {/* 3. Inner wireframe layer 2 (counter-rotating) */}
      <mesh ref={wireRef2} scale={0.78}>
        <octahedronGeometry args={[1.05, 2]} />
        <meshBasicMaterial color="#00f2fe" wireframe transparent opacity={0.12} />
      </mesh>

      {/* 4. Outer translucent shield */}
      <mesh ref={shellRef}>
        <sphereGeometry args={[0.96, 48, 48]} />
        <meshStandardMaterial
          color="#061b24"
          emissive="#00f2fe"
          emissiveIntensity={0.28}
          transparent
          opacity={0.2}
          roughness={0.08}
          metalness={0.1}
        />
      </mesh>

      {/* 5. Point Light */}
      <pointLight ref={lightRef} color="#00f2fe" intensity={2} distance={7} decay={1.5} />
    </group>
  );
};
export default CoreEnergySphere;
