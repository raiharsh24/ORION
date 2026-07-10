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

/**
 * The intelligence itself: a bright cyan energy sphere with an animated
 * emissive material, internal movement (counter-rotating wireframe core),
 * a translucent shell, and a pulsing point light. Responds to voice level
 * (speaking rhythm) and the active visual state. Clicking it previews states.
 */
export const CoreEnergySphere: React.FC<{ params: React.MutableRefObject<CoreVisualParams> }> = ({ params }) => {
  const coreRef = useRef<THREE.Mesh>(null!);
  const shellRef = useRef<THREE.Mesh>(null!);
  const wireRef = useRef<THREE.Mesh>(null!);
  const lightRef = useRef<THREE.PointLight>(null!);
  const coreMat = useRef<THREE.MeshStandardMaterial>(null!);

  useFrame((state, dt) => {
    const t = state.clock.elapsedTime;
    const p = params.current;
    const voice = useCommandCenterStore.getState().voiceLevel;

    coreMat.current.emissiveIntensity =
      (0.9 + p.intensity * 0.5) + Math.sin(t * 2.2) * 0.12 * p.pulse + voice * 1.4;
    tmpColor.copy(CYAN).lerp(RED, p.accentT);
    coreMat.current.emissive.copy(tmpColor);

    const s = 1 + Math.sin(t * 1.6) * 0.025 + p.pulse * 0.04 + voice * 0.06;
    coreRef.current.scale.setScalar(s);
    coreRef.current.rotation.y += dt * 0.25;
    coreRef.current.rotation.x += dt * 0.12;

    shellRef.current.scale.setScalar(1.22 + Math.sin(t * 0.8) * 0.02);
    shellRef.current.rotation.y -= dt * 0.1;

    wireRef.current.rotation.y -= dt * 0.4;
    wireRef.current.rotation.x += dt * 0.2;

    if (lightRef.current) lightRef.current.intensity = 0.8 + p.intensity * 1.5 + voice * 2;
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
      <mesh ref={coreRef}>
        <sphereGeometry args={[0.9, 64, 64]} />
        <meshStandardMaterial
          ref={coreMat}
          color="#001a22"
          emissive="#00f2fe"
          emissiveIntensity={1.4}
          roughness={0.25}
          metalness={0.2}
        />
      </mesh>

      <mesh ref={wireRef} scale={0.72}>
        <icosahedronGeometry args={[1.05, 1]} />
        <meshBasicMaterial color="#9bf6ff" wireframe transparent opacity={0.15} />
      </mesh>

      <mesh ref={shellRef}>
        <sphereGeometry args={[1, 48, 48]} />
        <meshStandardMaterial
          color="#0a2730"
          emissive="#00f2fe"
          emissiveIntensity={0.25}
          transparent
          opacity={0.18}
          roughness={0.1}
          metalness={0}
        />
      </mesh>

      <pointLight ref={lightRef} color="#00f2fe" intensity={2} distance={7} decay={1.5} />
    </group>
  );
};
