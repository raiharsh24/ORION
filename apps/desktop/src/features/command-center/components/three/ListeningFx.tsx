import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';

/**
 * Listening-only FX: two expanding wave rings radiating outward and a row of
 * blinking microphone indicator lights. Hidden unless the core is listening.
 */
export const ListeningFx: React.FC = () => {
  const wave1 = useRef<THREE.Mesh>(null!);
  const wave2 = useRef<THREE.Mesh>(null!);
  const dots = useRef<THREE.Group>(null!);
  const t1 = useRef(0);
  const t2 = useRef(0.5);

  useFrame((state, dt) => {
    const listening = useCommandCenterStore.getState().listening;

    if (listening) {
      t1.current = (t1.current + dt * 0.8) % 1;
      t2.current = (t2.current + dt * 0.8) % 1;
      wave1.current.visible = true;
      wave2.current.visible = true;
      const s1 = 1.2 + t1.current * 2.6;
      wave1.current.scale.set(s1, s1, s1);
      (wave1.current.material as THREE.MeshBasicMaterial).opacity = (1 - t1.current) * 0.5;
      const s2 = 1.2 + t2.current * 2.6;
      wave2.current.scale.set(s2, s2, s2);
      (wave2.current.material as THREE.MeshBasicMaterial).opacity = (1 - t2.current) * 0.5;
    } else {
      wave1.current.visible = false;
      wave2.current.visible = false;
    }

    if (dots.current) {
      dots.current.visible = listening;
      const o = 0.4 + 0.6 * Math.abs(Math.sin(state.clock.elapsedTime * 4));
      dots.current.children.forEach((c) => {
        ((c as THREE.Mesh).material as THREE.MeshBasicMaterial).opacity = o;
      });
    }
  });

  return (
    <group>
      <mesh ref={wave1} rotation={[-Math.PI / 2, 0, 0]} visible={false}>
        <ringGeometry args={[1.0, 1.08, 64]} />
        <meshBasicMaterial color="#00f2fe" transparent opacity={0.4} side={THREE.DoubleSide} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
      <mesh ref={wave2} rotation={[-Math.PI / 2, 0, 0]} visible={false}>
        <ringGeometry args={[1.0, 1.08, 64]} />
        <meshBasicMaterial color="#00f2fe" transparent opacity={0.4} side={THREE.DoubleSide} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
      <group ref={dots} position={[0, 1.35, 0]} visible={false}>
        {[-0.28, 0, 0.28].map((x, i) => (
          <mesh key={i} position={[x, 0, 0]}>
            <sphereGeometry args={[0.045, 12, 12]} />
            <meshBasicMaterial color="#34d399" transparent opacity={0.8} />
          </mesh>
        ))}
      </group>
    </group>
  );
};
