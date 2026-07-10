import { Sparkles } from '@react-three/drei';

/**
 * The immersive command-room environment.
 * Volumetric-feeling fog, cool blue ambient lighting, subtle orange accent,
 * and far-field sparkles for depth. Designed to sit behind the HUD, never
 * competing with it for attention.
 */
export const AmbientScene: React.FC = () => (
  <>
    <fogExp2 attach="fog" args={['#05070d', 0.14]} />

    <ambientLight intensity={0.35} color="#2a4a7a" />
    <pointLight position={[0, 2, 4]} intensity={1.2} color="#00f2fe" distance={14} decay={1.2} />
    <pointLight position={[-4, -1, -2]} intensity={0.85} color="#ff8a3d" distance={14} decay={1.2} />
    <pointLight position={[4, 1, 2]} intensity={0.9} color="#4db8ff" distance={14} decay={1.2} />

    {/* Far-field floating particles for cinematic depth */}
    <Sparkles count={70} scale={[14, 9, 9]} size={2.2} speed={0.18} color="#1f4a6b" opacity={0.45} />
  </>
);
