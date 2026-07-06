import { useRef, useState, useEffect, useMemo } from 'react';
import * as THREE from 'three';
import { useFrame, useThree } from '@react-three/fiber';
import { Sparkles, SpotLight } from '@react-three/drei';
import { useMotionValue, useSpring, motion } from 'framer-motion';

// Global Pointer Tracker (bypasses canvas pointer-events: none)
export const globalPointer = new THREE.Vector2(0, 0);
let pointerListenerCount = 0;
let globalPointerHandler: ((e: PointerEvent) => void) | null = null;

export function ensureGlobalPointer() {
  if (typeof window === 'undefined') return () => {};
  
  pointerListenerCount++;
  if (pointerListenerCount === 1) {
    globalPointerHandler = (e: PointerEvent) => {
      globalPointer.x = (e.clientX / window.innerWidth) * 2 - 1;
      globalPointer.y = -(e.clientY / window.innerHeight) * 2 + 1;
    };
    window.addEventListener('pointermove', globalPointerHandler);
  }
  
  return () => {
    pointerListenerCount--;
    if (pointerListenerCount === 0 && globalPointerHandler) {
      window.removeEventListener('pointermove', globalPointerHandler);
      globalPointerHandler = null;
    }
  };
}

// 1. Constellation Void (Fragments & Threads)
export function ConstellationVoid({ quality = 'balanced' }: { quality?: string }) {
  useEffect(() => {
    const cleanup = ensureGlobalPointer();
    return cleanup;
  }, []);
  
  const fragmentsRefs = useRef<THREE.Mesh[]>([]);
  
  const fragmentsData = useMemo(() => {
    const count = quality === 'performance' ? 15 : quality === 'cinematic' ? 75 : 45;
    return Array.from({ length: count }).map((_, i) => ({
      id: i,
      position: new THREE.Vector3(
        (Math.random() - 0.5) * 20,
        (Math.random() - 0.5) * 15,
        (Math.random() - 0.5) * 10 - 2
      ),
      rotation: new THREE.Euler(
        Math.random() * Math.PI,
        Math.random() * Math.PI,
        Math.random() * Math.PI
      ),
      velocity: new THREE.Vector3(
        (Math.random() - 0.5) * 0.005,
        (Math.random() - 0.5) * 0.005,
        (Math.random() - 0.5) * 0.005
      ),
      rotVelocity: new THREE.Vector3(
        (Math.random() - 0.5) * 0.01,
        (Math.random() - 0.5) * 0.01,
        (Math.random() - 0.5) * 0.01
      ),
      scale: 0.1 + Math.random() * 0.3,
      type: Math.floor(Math.random() * 3)
    }));
  }, [quality]);

  const spark1 = quality === 'performance' ? 0 : quality === 'cinematic' ? 300 : 150;
  const spark2 = quality === 'performance' ? 0 : quality === 'cinematic' ? 150 : 75;

  return (
    <group>
      {fragmentsData.map((data, i) => (
        <FragmentItem 
          key={data.id} 
          data={data} 
          index={i}
          fragmentsRefs={fragmentsRefs}
          quality={quality}
        />
      ))}
      <ConstellationLines fragmentsRefs={fragmentsRefs} quality={quality} />
      
      {spark1 > 0 && <Sparkles count={spark1} scale={25} size={2} speed={0.2} opacity={0.1} color="#3b00ff" position={[0, 0, -4]} />}
      {spark2 > 0 && <Sparkles count={spark2} scale={20} size={4} speed={0.4} opacity={0.15} color="#5e10d9" position={[0, 0, 2]} />}
    </group>
  );
}

function FragmentItem({ data, index, fragmentsRefs }: any) {
  const meshRef = useRef<THREE.Mesh>(null);
  const materialRef = useRef<THREE.MeshPhysicalMaterial>(null);
  const { camera } = useThree();
  const logged = useRef(false);

  useEffect(() => {
    if (meshRef.current) {
      fragmentsRefs.current[index] = meshRef.current;
    }
  }, [index, fragmentsRefs]);

  useFrame(() => {
    if (!logged.current) {
      console.log('FragmentItem useFrame executing');
      logged.current = true;
    }
    if (!meshRef.current) return;
    
    // Base drift
    meshRef.current.position.add(data.velocity);
    meshRef.current.rotation.x += data.rotVelocity.x;
    meshRef.current.rotation.y += data.rotVelocity.y;
    meshRef.current.rotation.z += data.rotVelocity.z;
    
    // Bounds wrapping
    if (meshRef.current.position.x > 12) meshRef.current.position.x = -12;
    if (meshRef.current.position.x < -12) meshRef.current.position.x = 12;
    if (meshRef.current.position.y > 10) meshRef.current.position.y = -10;
    if (meshRef.current.position.y < -10) meshRef.current.position.y = 10;
    if (meshRef.current.position.z > 5) meshRef.current.position.z = -10;
    if (meshRef.current.position.z < -10) meshRef.current.position.z = 5;

    // Cursor interaction (using globalPointer instead of R3F pointer)
    const vec = new THREE.Vector3(globalPointer.x, globalPointer.y, 0.5);
    vec.unproject(camera);
    const dir = vec.sub(camera.position).normalize();
    const distance = (meshRef.current.position.z - camera.position.z) / dir.z;
    const cursorPos = camera.position.clone().add(dir.multiplyScalar(distance));
    
    const distToCursor = meshRef.current.position.distanceTo(cursorPos);
    
    // Proximity glow (dimmer max intensity so it never outshines the BST)
    if (materialRef.current) {
      const targetEmissive = distToCursor < 4 ? 0.35 : 0.02;
      materialRef.current.emissiveIntensity = THREE.MathUtils.lerp(
        materialRef.current.emissiveIntensity, targetEmissive, 0.1
      );
    }
    
    // Gentle displacement (repulsion)
    if (distToCursor < 3) {
      const pushDir = meshRef.current.position.clone().sub(cursorPos).normalize();
      meshRef.current.position.add(pushDir.multiplyScalar(0.01 * (3 - distToCursor)));
    }
  });

  return (
    <mesh ref={meshRef} position={data.position} rotation={data.rotation} scale={data.scale}>
      {data.type === 0 && <icosahedronGeometry args={[1, 0]} />}
      {data.type === 1 && <dodecahedronGeometry args={[1, 0]} />}
      {data.type === 2 && <octahedronGeometry args={[1, 0]} />}
      <meshPhysicalMaterial 
        ref={materialRef}
        color="#05070a" // Dim slate/graphite glass tone
        emissive="#2a0a5e" // Deep violet glow
        emissiveIntensity={0.02}
        transparent
        opacity={0.6}
        roughness={0.2}
        metalness={0.9}
        clearcoat={1}
        wireframe={data.type === 2} // Orbs are wireframes for variety
      />
    </mesh>
  );
}

function ConstellationLines({ fragmentsRefs, quality = 'balanced' }: { fragmentsRefs: React.MutableRefObject<THREE.Mesh[]>, quality?: string }) {
  const lineGeometryRef = useRef<THREE.BufferGeometry>(null);
  const { camera } = useThree();
  const maxThreads = 12;
  // Pre-allocate typed array to prevent GC spikes (Step 14: VERIFY PERFORMANCE)
  const positionsArray = useRef(new Float32Array(maxThreads * 6));
  
  useFrame(() => {
    if (!lineGeometryRef.current) return;
    
    const meshes = fragmentsRefs.current.filter(m => m !== null);
    
    // Cursor position in world space at approx z=0 (using globalPointer)
    const vec = new THREE.Vector3(globalPointer.x, globalPointer.y, 0.5);
    vec.unproject(camera);
    const dir = vec.sub(camera.position).normalize();
    const distance = (0 - camera.position.z) / dir.z;
    const cursorPos = camera.position.clone().add(dir.multiplyScalar(distance));
    
    let threadCount = 0;
    let idx = 0;
    const positions = positionsArray.current;

    for (let i = 0; i < meshes.length; i++) {
      const p1 = meshes[i].position;
      
      // Cursor to fragment
      if (p1.distanceTo(cursorPos) < 4 && threadCount < maxThreads) {
        positions[idx++] = p1.x; positions[idx++] = p1.y; positions[idx++] = p1.z;
        positions[idx++] = cursorPos.x; positions[idx++] = cursorPos.y; positions[idx++] = cursorPos.z;
        threadCount++;
      }
      
      // Fragment to fragment
      for (let j = i + 1; j < meshes.length; j++) {
        const p2 = meshes[j].position;
        if (p1.distanceTo(p2) < 3.5 && threadCount < maxThreads) {
          positions[idx++] = p1.x; positions[idx++] = p1.y; positions[idx++] = p1.z;
          positions[idx++] = p2.x; positions[idx++] = p2.y; positions[idx++] = p2.z;
          threadCount++;
        }
      }
    }
    
    // Reusing BufferAttribute prevents continuous reallocation
    lineGeometryRef.current.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    lineGeometryRef.current.setDrawRange(0, threadCount * 2);
  });

  return (
    <lineSegments>
      <bufferGeometry ref={lineGeometryRef} />
      <lineBasicMaterial color="#38107a" transparent opacity={0.15} blending={THREE.AdditiveBlending} />
    </lineSegments>
  );
}

// 2. Cursor-Reactive Lighting
export function CursorLight() {
  useEffect(() => ensureGlobalPointer(), []);
  const lightRef = useRef<THREE.SpotLight>(null);
  const targetRef = useRef<THREE.Object3D>(new THREE.Object3D());
  const { viewport, scene } = useThree();
  const logged = useRef(false);

  useEffect(() => {
    const cleanup = ensureGlobalPointer();
    scene.add(targetRef.current);
    if (lightRef.current) {
      lightRef.current.target = targetRef.current;
    }
    return () => {
      cleanup();
      scene.remove(targetRef.current);
    };
  }, [scene]);

  useFrame(() => {
    if (!logged.current) {
      console.log('CursorLight useFrame executing');
      logged.current = true;
    }
    if (!lightRef.current || !targetRef.current) return;
    
    // Using globalPointer to bypass pointer-events: none
    const targetX = (globalPointer.x * viewport.width) / 2;
    const targetY = (globalPointer.y * viewport.height) / 2;
    
    lightRef.current.position.x = THREE.MathUtils.lerp(lightRef.current.position.x, targetX, 0.1);
    lightRef.current.position.y = THREE.MathUtils.lerp(lightRef.current.position.y, targetY, 0.1);
    
    targetRef.current.position.set(
      lightRef.current.position.x,
      lightRef.current.position.y,
      0
    );
  });

  return (
    <SpotLight
      ref={lightRef}
      position={[0, 0, 8]}
      distance={20}
      angle={0.6}
      attenuation={6}
      anglePower={4}
      intensity={3}
      color="#00e5ff"
      penumbra={1}
      volumetric={false}
    />
  );
}

// 3. Custom Cursor (HTML Overlay)
export function CustomCursor() {
  useEffect(() => { console.log('Cursor mounted'); }, []);
  const cursorX = useMotionValue(-100);
  const cursorY = useMotionValue(-100);
  
  const springConfig = { damping: 25, stiffness: 200, mass: 0.5 };
  const cursorXSpring = useSpring(cursorX, springConfig);
  const cursorYSpring = useSpring(cursorY, springConfig);
  
  const scale = useMotionValue(1);
  const scaleSpring = useSpring(scale, springConfig);

  useEffect(() => {
    const moveCursor = (e: PointerEvent) => {
      cursorX.set(e.clientX - 16);
      cursorY.set(e.clientY - 16);
    };
    
    const handlePointerOver = (e: PointerEvent) => {
      const target = e.target as HTMLElement;
      if (target.closest('a, button, [role="button"], .group')) {
        scale.set(1.8);
      } else {
        scale.set(1);
      }
    };
    
    const handlePointerDown = () => scale.set(0.8);
    const handlePointerUp = () => scale.set(1);

    window.addEventListener('pointermove', moveCursor);
    window.addEventListener('pointerover', handlePointerOver);
    window.addEventListener('pointerdown', handlePointerDown);
    window.addEventListener('pointerup', handlePointerUp);
    
    return () => {
      window.removeEventListener('pointermove', moveCursor);
      window.removeEventListener('pointerover', handlePointerOver);
      window.removeEventListener('pointerdown', handlePointerDown);
      window.removeEventListener('pointerup', handlePointerUp);
    };
  }, []);

  return (
    <motion.div
      className="fixed top-0 left-0 w-8 h-8 rounded-full pointer-events-none z-[9999]"
      style={{
        x: cursorXSpring,
        y: cursorYSpring,
        scale: scaleSpring,
        border: '2px solid rgba(9, 251, 211, 0.8)',
        boxShadow: '0 0 15px rgba(9, 251, 211, 0.5)',
        backgroundColor: 'rgba(9, 251, 211, 0.1)',
      }}
    />
  );
}

// 4. Shader Background
import { BackgroundShaderMaterial } from './shaders';
import { extend } from '@react-three/fiber';

// Explicitly register material here to prevent Next.js/Turbopack tree-shaking
extend({ BackgroundShaderMaterial });

declare module '@react-three/fiber' {
  interface ThreeElements {
    backgroundShaderMaterial: any;
  }
}

export function ShaderBackground({ quality = 'balanced' }: { quality?: string }) {
  useEffect(() => { console.log('Background mounted'); }, []);
  const materialRef = useRef<any>(null);
  const logged = useRef(false);

  useFrame((state) => {
    if (quality === 'performance') return;
    if (!logged.current) {
      console.log('ShaderBackground useFrame executing');
      logged.current = true;
    }
    if (!materialRef.current) return;
    materialRef.current.uTime = state.clock.elapsedTime;
    
    // Map global pointer (-1 to 1) to UV space (0 to 1)
    materialRef.current.uCursor.set(
      globalPointer.x * 0.5 + 0.5,
      globalPointer.y * 0.5 + 0.5
    );
  });

  if (quality === 'performance') return null;

  return (
    <mesh position={[0, 0, -10]}>
      <planeGeometry args={[100, 100]} />
      <backgroundShaderMaterial ref={materialRef} />
    </mesh>
  );
}
