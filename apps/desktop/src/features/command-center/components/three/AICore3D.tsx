import { useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';
import { STATE_PARAMS, type CoreVisualParams } from './coreConfig';
import { CameraRig } from './CameraRig';
import { AmbientScene } from './AmbientScene';
import { CoreEnergySphere } from './CoreEnergySphere';
import { ConcentricRings } from './ConcentricRings';
import { ParticleField } from './ParticleField';
import { FloorReactor } from './FloorReactor';
import { ListeningFx } from './ListeningFx';

/**
 * Parent of all 3D core pieces. Owns the single shared `params` ref which is
 * eased toward the target for the current visual state every frame, then read
 * imperatively by children — so state transitions are smooth and never cause
 * React re-renders inside the render loop.
 */
const CoreScene: React.FC = () => {
  const params = useRef<CoreVisualParams>({ ...STATE_PARAMS.idle });

  useFrame((_, dt) => {
    const s = useCommandCenterStore.getState();
    const cs = s.listening ? 'listening' : s.coreState;
    const target = STATE_PARAMS[cs];
    const p = params.current;
    const k = 1 - Math.pow(0.0015, dt);
    p.ringSpeed += (target.ringSpeed - p.ringSpeed) * k;
    p.intensity += (target.intensity - p.intensity) * k;
    p.particleRadius += (target.particleRadius - p.particleRadius) * k;
    p.glow += (target.glow - p.glow) * k;
    p.pulse += (target.pulse - p.pulse) * k;
  });

  return (
    <>
      <CameraRig />
      <CoreEnergySphere params={params} />
      <ConcentricRings params={params} />
      <ParticleField params={params} />
      <FloorReactor params={params} />
      <ListeningFx />
    </>
  );
};

/**
 * FRIDAY AI Core — a living React Three Fiber scene.
 * Lazy-loaded by the Command Center page so heavy 3D code is code-split.
 */
export default function AICore3D() {
  return (
    <Canvas
      dpr={[1, 1.75]}
      camera={{ position: [0, 0.2, 6], fov: 45 }}
      gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
    >
      <AmbientScene />
      <CoreScene />
      <EffectComposer>
        <Bloom intensity={0.9} luminanceThreshold={0.2} luminanceSmoothing={0.35} mipmapBlur radius={0.6} />
      </EffectComposer>
    </Canvas>
  );
}
