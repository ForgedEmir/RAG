import React, { useRef, useMemo, Suspense } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Float, MeshDistortMaterial } from '@react-three/drei';
import { EffectComposer, Bloom } from '@react-three/postprocessing';
import * as THREE from 'three';

// ── Central Oracle Sphere ─────────────────────────────────────────────────────
// Represents the LoreKeeper knowledge base — glowing, distorted, alive
const OracleOrb = () => {
  const outerRef = useRef();

  useFrame((_, delta) => {
    if (outerRef.current) {
      outerRef.current.rotation.y += delta * 0.12;
      outerRef.current.rotation.x += delta * 0.04;
    }
  });

  return (
    <Float speed={1.6} rotationIntensity={0.15} floatIntensity={0.5}>
      <group>
        {/* Core sphere */}
        <mesh ref={outerRef}>
          <sphereGeometry args={[1.15, 72, 72]} />
          <MeshDistortMaterial
            color="#1a0e00"
            emissive="#F59E0B"
            emissiveIntensity={0.65}
            distort={0.42}
            speed={1.6}
            roughness={0.05}
            metalness={0.9}
          />
        </mesh>

        {/* Thin outer glow shell */}
        <mesh>
          <sphereGeometry args={[1.28, 32, 32]} />
          <meshBasicMaterial
            color="#F59E0B"
            transparent
            opacity={0.035}
            side={THREE.BackSide}
          />
        </mesh>

        {/* Mid atmosphere shell */}
        <mesh>
          <sphereGeometry args={[1.5, 24, 24]} />
          <meshBasicMaterial
            color="#B45309"
            transparent
            opacity={0.012}
            side={THREE.BackSide}
          />
        </mesh>
      </group>
    </Float>
  );
};

// ── Orbiting Document Node ────────────────────────────────────────────────────
// Each node = a document chunk retrieved by the RAG pipeline
// pivotRotX / pivotRotZ define the orbital plane
const DocNode = ({ radius, speed, phase, pivotRotX = 0, pivotRotZ = 0, size = 0.11 }) => {
  const pivotRef = useRef();
  const orbitRef = useRef();
  const crystalRef = useRef();

  useFrame(({ clock }) => {
    const t = clock.elapsedTime * speed + phase;
    if (orbitRef.current) {
      orbitRef.current.position.x = Math.cos(t) * radius;
      orbitRef.current.position.z = Math.sin(t) * radius;
    }
    if (pivotRef.current) {
      pivotRef.current.rotation.x = pivotRotX;
      pivotRef.current.rotation.z = pivotRotZ;
    }
    if (crystalRef.current) {
      crystalRef.current.rotation.x += 0.018;
      crystalRef.current.rotation.y += 0.022;
    }
  });

  return (
    <group ref={pivotRef}>
      <group ref={orbitRef}>
        {/* Crystal icosahedron representing a document chunk */}
        <mesh ref={crystalRef}>
          <icosahedronGeometry args={[size, 0]} />
          <meshStandardMaterial
            color="#F59E0B"
            emissive="#F59E0B"
            emissiveIntensity={2.2}
            roughness={0}
            metalness={0.6}
          />
        </mesh>
        {/* Soft glow halo around the node */}
        <mesh>
          <sphereGeometry args={[size * 2.8, 8, 8]} />
          <meshBasicMaterial color="#F59E0B" transparent opacity={0.055} />
        </mesh>
      </group>
    </group>
  );
};

// ── Orbit Ring ────────────────────────────────────────────────────────────────
// Thin torus showing the path of each orbital plane
const OrbitRing = ({ radius, pivotRotX = 0, pivotRotZ = 0, opacity = 0.07 }) => (
  <group rotation={[pivotRotX, 0, pivotRotZ]}>
    <mesh rotation={[Math.PI / 2, 0, 0]}>
      <torusGeometry args={[radius, 0.0045, 8, 128]} />
      <meshBasicMaterial color="#F59E0B" transparent opacity={opacity} />
    </mesh>
  </group>
);

// ── Ambient Particle Cloud ────────────────────────────────────────────────────
// Background "knowledge particles" — vectors in semantic space
const ParticleField = ({ count = 320, rMin = 4, rMax = 9, particleSize = 0.03, opacity = 0.4, speed = 0.025 }) => {
  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      const r = rMin + Math.random() * (rMax - rMin);
      arr[i * 3]     = r * Math.sin(phi) * Math.cos(theta);
      arr[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      arr[i * 3 + 2] = r * Math.cos(phi);
    }
    return arr;
  }, [count, rMin, rMax]);

  const fieldRef = useRef();
  useFrame((_, delta) => {
    if (fieldRef.current) fieldRef.current.rotation.y += delta * speed;
  });

  return (
    <points ref={fieldRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={count}
          array={positions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        color="#F59E0B"
        size={particleSize}
        transparent
        opacity={opacity}
        sizeAttenuation
      />
    </points>
  );
};

// ── Orbital config ────────────────────────────────────────────────────────────
// 3 orbital planes × 2 nodes each = 6 total (= top-k results in RAG)
const NODES = [
  // Plane 0 — horizontal (XZ)
  { radius: 2.2, speed: 0.42, phase: 0,              pivotRotX: 0.15, pivotRotZ: 0,    size: 0.11 },
  { radius: 2.2, speed: 0.42, phase: Math.PI,        pivotRotX: 0.15, pivotRotZ: 0,    size: 0.09 },
  // Plane 1 — 40° tilt
  { radius: 2.75, speed: 0.28, phase: Math.PI / 3,   pivotRotX: 0.72, pivotRotZ: 0.35, size: 0.13 },
  { radius: 2.75, speed: 0.28, phase: Math.PI * 4/3, pivotRotX: 0.72, pivotRotZ: 0.35, size: 0.10 },
  // Plane 2 — 70° tilt (near vertical)
  { radius: 3.2,  speed: 0.18, phase: Math.PI / 6,   pivotRotX: 1.25, pivotRotZ: 0.65, size: 0.085 },
  { radius: 3.2,  speed: 0.18, phase: Math.PI * 7/6, pivotRotX: 1.25, pivotRotZ: 0.65, size: 0.115 },
];

// ── Inner Canvas Scene ────────────────────────────────────────────────────────
const Scene = () => (
  <>
    <ambientLight intensity={0.04} />
    <pointLight position={[4, 3.5, 4]}  color="#F59E0B" intensity={5} />
    <pointLight position={[-5, -3, -4]} color="#7C3800" intensity={2.5} />
    <pointLight position={[0, 6, 0]}    color="#ffffff" intensity={0.4} />

    <OracleOrb />

    {NODES.map((props, i) => (
      <DocNode key={i} {...props} />
    ))}

    {/* Orbit rings matching each plane */}
    <OrbitRing radius={2.2}  pivotRotX={0.15} pivotRotZ={0}    opacity={0.08} />
    <OrbitRing radius={2.75} pivotRotX={0.72} pivotRotZ={0.35} opacity={0.06} />
    <OrbitRing radius={3.2}  pivotRotX={1.25} pivotRotZ={0.65} opacity={0.05} />

    {/* Near particle halo */}
    <ParticleField count={320} rMin={4} rMax={9} particleSize={0.03} opacity={0.38} speed={0.025} />
    {/* Distant starfield */}
    <ParticleField count={500} rMin={10} rMax={22} particleSize={0.018} opacity={0.22} speed={-0.008} />

    <EffectComposer>
      <Bloom
        luminanceThreshold={0.12}
        intensity={2.8}
        mipmapBlur
        radius={0.55}
      />
    </EffectComposer>
  </>
);

// ── Exported Canvas Wrapper ───────────────────────────────────────────────────
export default function OracleScene() {
  return (
    <Canvas
      dpr={[1, 1.8]}
      camera={{ position: [0, 0.8, 9.5], fov: 62 }}
      gl={{ antialias: true, alpha: true }}
      style={{ background: 'transparent' }}
    >
      <Suspense fallback={null}>
        <Scene />
      </Suspense>
    </Canvas>
  );
}
