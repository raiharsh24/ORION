import { useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';

/**
 * Subtle, premium camera parallax driven by the pointer.
 * Tiny movement only — never distracting. Lazily eases toward a target
 * offset derived from normalized pointer coordinates.
 */
export const CameraRig: React.FC = () => {
  const { camera, pointer } = useThree();
  const target = useRef(new THREE.Vector3(0, 0.2, 6));

  useFrame((_, dt) => {
    const ease = 1 - Math.pow(0.0025, dt);
    target.current.set(pointer.x * 0.35, 0.2 + pointer.y * 0.22, 6);
    camera.position.x += (target.current.x - camera.position.x) * ease;
    camera.position.y += (target.current.y - camera.position.y) * ease;
    camera.position.z += (target.current.z - camera.position.z) * ease;
    camera.lookAt(0, 0, 0);
  });

  return null;
};
