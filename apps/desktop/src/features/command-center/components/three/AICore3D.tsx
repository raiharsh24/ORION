import { useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { EffectComposer, Bloom, Vignette } from '@react-three/postprocessing';
import * as THREE from 'three';
import { useAiStateStore } from '../../sync/useAiStateStore';
import { STATE_PARAMS, type CoreVisualParams } from './coreConfig';
import { makeRadialTexture } from './textures';
import { CameraRig } from './CameraRig';
import { AmbientScene } from './AmbientScene';
import { CoreEnergySphere } from './CoreEnergySphere';
import { ConcentricRings } from './ConcentricRings';
import { ParticleField } from './ParticleField';
import { FloorReactor } from './FloorReactor';
import { ListeningFx } from './ListeningFx';

const CYAN = new THREE.Color('#00f2fe');
const RED = new THREE.Color('#ff5470');
const tmpColor = new THREE.Color();

/** Volumetric core halo — its color/scale track the shared AI state. */
const Halo: React.FC<{ params: React.MutableRefObject<CoreVisualParams> }> = ({ params }) => {
  const ref = useRef<THREE.Sprite>(null!);
  const matRef = useRef<THREE.SpriteMaterial>(null!);
  const tex = useMemo(
    () =>
      makeRadialTexture([
        [0, 'rgba(150,245,255,0.9)'],
        [0.25, 'rgba(0,200,255,0.35)'],
        [0.6, 'rgba(0,120,200,0.08)'],
        [1, 'rgba(0,80,160,0)'],
      ]),
    [],
  );

  useFrame((state) => {
    const p = params.current;
    const t = state.clock.elapsedTime;
    const base = 4.4 + p.halo * 1.8 + Math.sin(t * 1.6) * 0.2 * p.pulse;
    ref.current.scale.set(base, base, 1);
    if (matRef.current) {
      matRef.current.opacity = (0.35 + p.glow * 0.4 + Math.sin(t * 2) * 0.06 * p.pulse) * (0.6 + p.halo * 0.5);
      tmpColor.copy(CYAN).lerp(RED, p.accentT);
      matRef.current.color.copy(tmpColor);
    }
  });

  return (
    <sprite ref={ref} position={[0, 0, -0.4]}>
      <spriteMaterial ref={matRef} map={tex} blending={THREE.AdditiveBlending} transparent depthWrite={false} opacity={0.5} />
    </sprite>
  );
};

/**
 * Parent of all 3D core pieces. Owns the single shared `params` ref eased
 * toward the target for the CURRENT canonical AI state every frame. Reads the
 * state imperatively via getState() so transitions never cause React renders.
 */
const CoreScene: React.FC = () => {
  const params = useRef<CoreVisualParams>({ ...STATE_PARAMS.idle });

  useFrame((_, dt) => {
    const cs = useAiStateStore.getState().state;
    const target = STATE_PARAMS[cs];
    const p = params.current;
    const k = 1 - Math.pow(0.0015, dt);
    p.ringSpeed += (target.ringSpeed - p.ringSpeed) * k;
    p.intensity += (target.intensity - p.intensity) * k;
    p.particleRadius += (target.particleRadius - p.particleRadius) * k;
    p.glow += (target.glow - p.glow) * k;
    p.pulse += (target.pulse - p.pulse) * k;
    p.halo += (target.halo - p.halo) * k;
    p.accentT += (target.accentT - p.accentT) * k;
  });

  return (
    <>
      <CameraRig />
      <Halo params={params} />
      <CoreEnergySphere params={params} />
      <ConcentricRings params={params} />
      <ParticleField params={params} />
      <FloorReactor params={params} />
      <ListeningFx />
    </>
  );
};

/**
 * FRIDAY AI Core — a living React Three Fiber scene, fully driven by the shared
 * AI state. Lazy-loaded by the Command Center page so heavy 3D code is split.
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
        <Bloom intensity={1.15} luminanceThreshold={0.15} luminanceSmoothing={0.4} mipmapBlur radius={0.8} />
        <Vignette eskil={false} offset={0.25} darkness={0.85} />
      </EffectComposer>
    </Canvas>
  );
}
