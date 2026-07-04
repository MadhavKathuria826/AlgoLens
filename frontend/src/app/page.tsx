"use client";

import { useRef, useState, useEffect, Suspense } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { ScrollControls, Scroll, Sparkles, Sphere, Line, useScroll, Environment, MeshTransmissionMaterial, Html } from '@react-three/drei';
import * as THREE from 'three';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMotionValue, animate, motion, useTransform, useMotionTemplate, useScroll as useFramerScroll } from 'framer-motion';
import { Search } from 'lucide-react';
import StudioPage from './studio/page';

type AppState = 'landing' | 'pre-transition' | 'transition-to-studio' | 'studio' | 'transition-to-landing';

function TreeDemo({ appState }: { appState: AppState }) {
  const { scrollYProgress } = useFramerScroll();
  const group = useRef<THREE.Group>(null);
  const rotationY = useMotionValue(0);
  const modeRef = useRef<'scroll' | 'auto'>('scroll');
  const animRef = useRef<any>(null);
  
  // Nodes data
  const nodes = [
    { id: 1, pos: [0, 2, 0], val: 50 },
    { id: 2, pos: [-2, 0, 0], val: 30 },
    { id: 3, pos: [2, 0, 0], val: 70 },
    { id: 4, pos: [-3, -2, 0], val: 20 },
    { id: 5, pos: [-1, -2, 0], val: 40 },
    { id: 6, pos: [1, -2, 0], val: 60 },
    { id: 7, pos: [3, -2, 0], val: 80 },
  ];
  const edges = [
    [0, 1], [0, 2], [1, 3], [1, 4], [2, 5], [2, 6]
  ];

  useFrame((state, delta) => {
    if (!group.current) return;
    const offset = scrollYProgress.get(); // 0 to 1

    // Tree grows on scroll
    // Let's say offset 0 to 0.7 handles growth
    const growthProgress = Math.min(offset / 0.7, 1);
    const scale = 0.5 + 0.5 * growthProgress;
    group.current.scale.set(scale, scale, scale);

    const targetScrollAngle = growthProgress * Math.PI * 0.5;

    // Handle Rotation Hand-offs
    if (offset > 0.7) {
      if (modeRef.current === 'scroll') {
        modeRef.current = 'auto';
        if (animRef.current) {
          animRef.current.stop();
          animRef.current = null;
        }
      }
      
      // Auto mode: increment shared value continuously
      const idleProgress = (offset - 0.7) / 0.3;
      rotationY.set(rotationY.get() + 0.01 * idleProgress);
    } else {
      if (modeRef.current === 'auto') {
        modeRef.current = 'scroll';
        
        // Shortest Angle Delta (180-degree / PI symmetry)
        const current = rotationY.get();
        const PI = Math.PI;
        let diff = ((targetScrollAngle - current) % PI + PI) % PI;
        if (diff > PI / 2) diff -= PI;
        const targetRawAngle = current + diff;
        
        // Springed catch-up fallback over shortest path
        animRef.current = animate(rotationY, targetRawAngle, {
          type: "spring",
          stiffness: 250,
          damping: 25,
          onComplete: () => { animRef.current = null; }
        });
        animRef.current.customTarget = targetScrollAngle;
      }
      
      // Scroll mode: track scroll strictly (or retarget spring if animating)
      if (modeRef.current === 'scroll') {
        if (animRef.current) {
          // If target changed significantly while catching up, retarget the spring
          if (Math.abs(animRef.current.customTarget - targetScrollAngle) > 0.01) {
            animRef.current.stop();
            
            const current = rotationY.get();
            const PI = Math.PI;
            let diff = ((targetScrollAngle - current) % PI + PI) % PI;
            if (diff > PI / 2) diff -= PI;
            const targetRawAngle = current + diff;

            animRef.current = animate(rotationY, targetRawAngle, {
              type: "spring",
              stiffness: 250,
              damping: 25,
              onComplete: () => { animRef.current = null; }
            });
            animRef.current.customTarget = targetScrollAngle;
          }
        } else {
          // Maintain the continuous raw value winding number while tracking scroll strictly
          // This prevents massive velocity spikes that Framer Motion would otherwise inherit
          const current = rotationY.get();
          const PI = Math.PI;
          let diff = ((targetScrollAngle - current) % PI + PI) % PI;
          if (diff > PI / 2) diff -= PI;
          rotationY.set(current + diff);
        }
      }
    }
    
    // Apply single source of truth rotation
    group.current.rotation.y = rotationY.get();

    // Kept centered in viewport
    group.current.position.y = 0;
    group.current.position.x = 2; // Offset slightly to the right to leave space for text
    
    // Dolly camera in/out based on transition state
    if (appState === 'transition-to-studio' || appState === 'studio') {
      state.camera.position.z = THREE.MathUtils.lerp(state.camera.position.z, 2, 0.05);
    } else {
      state.camera.position.z = THREE.MathUtils.lerp(state.camera.position.z, 10, 0.05);
    }
  });

  return (
    <group ref={group} position={[2, 0, 0]}>
      {nodes.map((node) => (
        <Sphere key={node.id} position={node.pos as [number, number, number]} args={[0.5, 32, 32]}>
          <MeshTransmissionMaterial 
            backside 
            samples={4} 
            thickness={2} 
            chromaticAberration={1} 
            anisotropy={0.3} 
            distortion={0.5} 
            distortionScale={0.5} 
            temporalDistortion={0.1} 
            iridescence={1} 
            iridescenceIOR={1} 
            iridescenceThicknessRange={[0, 1400]}
            color="#09fbd3"
          />
        </Sphere>
      ))}
      {edges.map((edge, i) => {
        const start = nodes[edge[0]].pos as [number, number, number];
        const end = nodes[edge[1]].pos as [number, number, number];
        return (
          <Line 
            key={i} 
            points={[start, end]} 
            color="#00e5ff" 
            lineWidth={3}
            transparent
            opacity={0.8}
          />
        );
      })}
    </group>
  );
}

function Scene({ reducedMotion, appState }: { reducedMotion: boolean, appState: AppState }) {
  return (
    <>
      <color attach="background" args={['#020204']} />
      <ambientLight intensity={0.5} />
      <spotLight position={[10, 10, 10]} angle={0.25} penumbra={1} intensity={2} color="#00e5ff" />
      <spotLight position={[-10, -10, -10]} angle={0.25} penumbra={1} intensity={2} color="#fe53bb" />
      
      {!reducedMotion && <Sparkles count={300} scale={15} size={2} speed={0.4} opacity={0.3} color="#09fbd3" />}
      
      <TreeDemo appState={appState} />
      <Environment preset="city" />
    </>
  );
}

function ReadyEvent({ onReady }: { onReady: () => void }) {
  useEffect(() => {
    onReady();
  }, [onReady]);
  return null;
}

export default function Home() {
  const [isClient, setIsClient] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [appState, setAppState] = useState<AppState>('landing');
  const [webglSupported, setWebglSupported] = useState(true);
  const [sceneReady, setSceneReady] = useState(false);

  const [irisOrigin, setIrisOrigin] = useState({ x: 0, y: 0 });
  const lensRef = useRef<HTMLSpanElement>(null);
  
  const irisRadius = useMotionValue(0);
  const getMaxRadius = () => typeof window !== 'undefined' ? Math.max(window.innerWidth, window.innerHeight) * 1.5 : 3000;
  
  const landingBlur = useTransform(irisRadius, [0, 3000], [0, 12]);
  const landingGrayscale = useTransform(irisRadius, [0, 3000], [0, 60]);
  const landingFilter = useMotionTemplate`blur(${landingBlur}px) grayscale(${landingGrayscale}%)`;
  
  const ringSize = useMotionTemplate`calc(${irisRadius}px * 2)`;
  const ringX = useMotionTemplate`calc(${irisOrigin.x}px - ${irisRadius}px)`;
  const ringY = useMotionTemplate`calc(${irisOrigin.y}px - ${irisRadius}px)`;
  const irisClipPath = useMotionTemplate`circle(${irisRadius}px at ${irisOrigin.x}px ${irisOrigin.y}px)`;

  const handleBack = () => {
    if (reducedMotion) {
      setAppState('landing');
      window.history.pushState({}, '', '/');
      return;
    }
    
    if (lensRef.current) {
      const rect = lensRef.current.getBoundingClientRect();
      setIrisOrigin({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 });
    }
    
    setAppState('transition-to-landing');
    window.history.pushState({}, '', '/');
    
    animate(irisRadius, 12, {
      duration: 3.0,
      ease: [0.34, 1.1, 0.64, 1], // overshoot settle
      onComplete: () => {
        setAppState('landing');
        irisRadius.set(0);
      }
    });
  };

  useEffect(() => {
    const handlePopState = () => {
      if (window.location.pathname === '/' && appState === 'studio') {
        handleBack();
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [appState]);

  useEffect(() => {
    setIsClient(true);
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReducedMotion(mediaQuery.matches);
    
    try {
      const canvas = document.createElement('canvas');
      const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
      if (!gl) setWebglSupported(false);
    } catch (e) {
      setWebglSupported(false);
    }
  }, []);

  const handleStudioLaunch = () => {
    if (appState !== 'landing') return;

    if (reducedMotion) {
      setAppState('studio');
      window.history.pushState({}, '', '/studio');
      return;
    }
    
    if (lensRef.current) {
      const rect = lensRef.current.getBoundingClientRect();
      setIrisOrigin({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 });
    } else {
      setIrisOrigin({ x: window.innerWidth / 2, y: window.innerHeight / 2 });
    }
    
    setAppState('pre-transition');
    irisRadius.set(12); // Start at the radius of the "O"
    
    setTimeout(() => {
      setAppState('transition-to-studio');
      animate(irisRadius, getMaxRadius(), {
        duration: 3.5, // Cinematic slow pace
        ease: [0.34, 1.1, 0.64, 1],
        onComplete: () => {
          setAppState('studio');
          window.history.pushState({}, '', '/studio');
        }
      });
    }, 150);
  };

  const Content = () => (
    <>
      {/* Page 1: Hero */}
      <div className="h-screen w-full flex items-center px-[10vw]">
        <div className="w-[90%] md:w-1/2 flex flex-col gap-6 z-10 pointer-events-auto">
          <h1 className="text-5xl md:text-[5vw] leading-[1.1] font-bold text-white tracking-tighter drop-shadow-[0_4px_20px_rgba(0,0,0,0.8)]">
            See Your Algorithms <span className="text-transparent bg-clip-text bg-gradient-to-r from-brand-teal to-brand-violet drop-shadow-[0_0_20px_rgba(9,251,211,0.4)]">Think.</span>
          </h1>
          <p className="text-lg md:text-xl text-slate-300 font-medium leading-relaxed max-w-lg drop-shadow-[0_2px_10px_rgba(0,0,0,0.8)]">
            A visual reasoning engine. Watch your code execute step-by-step and truly understand what happens under the hood.
          </p>
          <div className="flex gap-4 mt-6">
            <button onClick={handleStudioLaunch} className="btn-primary-glow">Launch Studio</button>
          </div>
        </div>
      </div>

      {/* Page 2: Scroll growth explainer */}
      <div className="h-screen w-full flex items-center justify-start px-[10vw]">
        <div className="w-[90%] md:w-1/3 flex flex-col gap-6 z-10 pointer-events-auto">
          <div className="panel-surface !bg-black/40 !backdrop-blur-2xl border-white/10">
            <h2 className="text-3xl font-bold text-white tracking-tight mb-4 drop-shadow-[0_0_15px_rgba(255,255,255,0.3)]">
              Visual Scale
            </h2>
            <p className="text-base md:text-lg text-slate-300 leading-relaxed">
              As algorithms process, they expand. Complexity becomes legible. See the shape of your logic unfold natively in 3D space.
            </p>
          </div>
        </div>
      </div>

      {/* Page 3: The Invitation */}
      <div className="h-screen w-full flex items-center justify-center flex-col text-center px-[10vw]">
        <h2 className="text-4xl md:text-[4vw] font-bold text-white tracking-tight mb-8 drop-shadow-[0_0_30px_rgba(0,229,255,0.6)]">
          Transform code into understanding.
        </h2>
        <button onClick={handleStudioLaunch} className="btn-primary-glow !h-16 !px-10 !text-xl !rounded-2xl">
          Launch Studio
        </button>
      </div>
    </>
  );

  return (
    <div className="w-full min-h-screen bg-bg-app text-white font-sans selection:bg-brand-teal/30 relative">
      
      {/* Fallback Background (Cross-fades out when WebGL is ready) */}
      <div 
        className={`fixed inset-0 z-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-brand-teal/10 via-bg-app to-bg-app transition-opacity duration-1000 pointer-events-none ${
          isClient && webglSupported && sceneReady ? 'opacity-0' : 'opacity-100'
        }`}
      />

      {/* Studio Iris Reveal Overlay */}
      {appState !== 'landing' && !reducedMotion && (
        <motion.div 
          className="fixed inset-0 z-[200] pointer-events-auto overflow-hidden bg-bg-app"
          style={{ clipPath: irisClipPath }}
        >
          <StudioPage onBack={handleBack} />
        </motion.div>
      )}

      {/* Refraction Edge Ring (The actual visible lens rim) */}
      {appState !== 'landing' && appState !== 'studio' && !reducedMotion && (
        <motion.div
          className="fixed pointer-events-none rounded-full z-[201]"
          style={{
            width: ringSize,
            height: ringSize,
            left: ringX,
            top: ringY,
            border: '3px solid rgba(9, 251, 211, 0.8)',
            backdropFilter: 'blur(8px) brightness(1.2)',
            WebkitMaskImage: 'radial-gradient(circle, transparent calc(100% - 20px), black 100%)',
            maskImage: 'radial-gradient(circle, transparent calc(100% - 20px), black 100%)',
            boxShadow: '0 0 30px rgba(9,251,211,0.5), inset 0 0 30px rgba(9,251,211,0.5)',
          }}
        />
      )}

      {/* Landing Page Content (Blurred during transition, native scrolling) */}
      <motion.div className="w-full relative z-10" style={{ filter: landingFilter }}>
        <Content />
      </motion.div>

      <div className="fixed top-8 left-1/2 -translate-x-1/2 w-[90%] md:w-full max-w-[900px] z-50 flex justify-between items-center pointer-events-none">
        
        {/* Piece 1: Logo */}
        <motion.div 
          animate={{ y: [0, -3, 0] }} 
          transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
          className="pointer-events-auto flex items-center transition-colors group cursor-pointer will-change-transform"
        >
          <div className="text-xl md:text-2xl font-bold tracking-tight text-white drop-shadow-[0_0_12px_rgba(255,255,255,0.4)] flex items-center">
            Alg
            <span 
              ref={lensRef}
              className={`relative inline-flex items-center justify-center mx-[1px] w-[1em] h-[1em] transition-all duration-150 ${appState === 'pre-transition' ? 'text-brand-teal scale-125 drop-shadow-[0_0_20px_#09fbd3]' : 'group-hover:text-brand-teal'}`}
            >
              <span className="absolute top-[12.5%] left-[12.5%] w-[66.6%] h-[66.6%] rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-300 shadow-[inset_0_0_8px_rgba(9,251,211,0.6)]" style={{ backdropFilter: 'blur(3px) brightness(1.2) contrast(1.1)' }}></span>
              <Search 
                className={`absolute inset-0 w-full h-full z-10 transition-transform duration-[2000ms] ease-out origin-bottom-right ${appState !== 'landing' ? 'opacity-0 scale-50' : 'opacity-100 scale-100'}`} 
                strokeWidth={3} 
              />
            </span>
            Lens
          </div>
        </motion.div>

        {/* Piece 2: Nav Links */}
        <motion.div 
          animate={{ y: [0, 4, 0] }} 
          transition={{ duration: 7, repeat: Infinity, ease: "easeInOut", delay: 1 }}
          className="pointer-events-auto hidden md:flex items-center gap-6 text-[15px] font-bold text-slate-300 drop-shadow-[0_2px_4px_rgba(0,0,0,0.8)] will-change-transform"
        >
          <Link href="#visualizations" className="relative group/link hover:text-white transition-all duration-300 hover:tracking-[0.02em]">
            Visualizations
            <span className="absolute -bottom-1 left-0 w-full h-[2px] bg-brand-teal scale-x-0 origin-right transition-transform duration-300 ease-out group-hover/link:scale-x-100 group-hover/link:origin-left shadow-[0_0_8px_rgba(9,251,211,0.8)] rounded-full"></span>
          </Link>
          
          <span className="w-[4px] h-[4px] rounded-full bg-white/30 shadow-[0_0_5px_rgba(255,255,255,0.5)]"></span>
          
          <Link href="https://github.com" className="relative group/link hover:text-white transition-all duration-300 hover:tracking-[0.02em]">
            GitHub
            <span className="absolute -bottom-1 left-0 w-full h-[2px] bg-brand-teal scale-x-0 origin-right transition-transform duration-300 ease-out group-hover/link:scale-x-100 group-hover/link:origin-left shadow-[0_0_8px_rgba(9,251,211,0.8)] rounded-full"></span>
          </Link>
        </motion.div>

        {/* Piece 3: CTA */}
        <motion.div 
          animate={{ y: [0, -3, 0] }} 
          transition={{ duration: 5, repeat: Infinity, ease: "easeInOut", delay: 2 }}
          className="pointer-events-auto will-change-transform"
        >
          <button onClick={handleStudioLaunch} className="relative group/cta text-brand-teal font-bold text-base md:text-lg tracking-wide transition-all duration-300 hover:tracking-[0.02em] hover:text-white outline-none">
            <span className="drop-shadow-[0_0_12px_rgba(9,251,211,0.8)] group-hover/cta:drop-shadow-[0_0_20px_rgba(255,255,255,0.9)] transition-all duration-300">
              Launch Studio
            </span>
            <span className="absolute -bottom-1 left-0 w-full h-[2px] bg-brand-teal scale-x-0 origin-right transition-transform duration-300 ease-out group-hover/cta:scale-x-100 group-hover/cta:origin-left shadow-[0_0_12px_rgba(9,251,211,1)] rounded-full group-hover/cta:bg-white group-hover/cta:shadow-[0_0_12px_rgba(255,255,255,1)]"></span>
          </button>
        </motion.div>
      </div>

      {/* 3D Background Canvas */}
      {isClient && webglSupported && (
        <div className="fixed inset-0 z-0 pointer-events-none">
          <Canvas camera={{ position: [0, 0, 10], fov: 45 }} gl={{ antialias: true, alpha: false }}>
            <Suspense fallback={null}>
              <Scene reducedMotion={reducedMotion} appState={appState} />
              <ReadyEvent onReady={() => setSceneReady(true)} />
            </Suspense>
          </Canvas>
        </div>
      )}
    </div>
  );
}
