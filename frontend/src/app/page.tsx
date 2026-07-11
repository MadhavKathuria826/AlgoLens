"use client"

import React, { useState, useEffect, useRef } from 'react';
import { Search, ArrowRight, Code, Eye, BookOpen } from 'lucide-react';
import { motion } from 'motion/react';
import { Inter } from 'next/font/google';
import PixelDrift from '@/components/PixelDrift';
import { animate, createScope, stagger } from 'animejs';
import Studio from './studio/page';
import SocialButton from '@/components/kokonutui/social-button';
import { Component as EtheralShadow } from "@/components/ui/etheral-shadow";

const sans = Inter({ 
  subsets: ['latin'],
  weight: ['400', '700'],
  variable: '--font-sans',
});

export default function Home() {
  const [showStudio, setShowStudio] = useState(false);
  const [renderLanding, setRenderLanding] = useState(true);
  const [renderStudio, setRenderStudio] = useState(false);
  const [animateStudioVisual, setAnimateStudioVisual] = useState(false);
  const pageScopeRef = useRef<HTMLDivElement>(null);
  
  // Manage display states deferred to match mechanical shutter transition timings (600ms)
  useEffect(() => {
    let rafId1: number;
    let rafId2: number;

    if (showStudio) {
      setRenderStudio(true); // 1. Instantly render container in DOM
      
      // 2. Wait two frames for layout registration, then start visual fade-in/shutter clip
      rafId1 = requestAnimationFrame(() => {
        rafId2 = requestAnimationFrame(() => {
          setAnimateStudioVisual(true);
        });
      });
      
      setRenderLanding(true); // Keep landing visible during transition
      const t = setTimeout(() => {
        setRenderLanding(false);
      }, 600);
      
      return () => {
        cancelAnimationFrame(rafId1);
        cancelAnimationFrame(rafId2);
        clearTimeout(t);
      };
    } else {
      setAnimateStudioVisual(false); // 1. Instantly trigger visual fade-out/shutter close
      setRenderLanding(true);
      
      const t = setTimeout(() => {
        setRenderStudio(false); // 2. Hide container in DOM after transition
      }, 600);
      
      return () => clearTimeout(t);
    }
  }, [showStudio]);

  // Magnetic button state
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  // 3D Clay Card tilt state
  const clayCardRef = useRef<HTMLDivElement>(null);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });

  const handleMouseMove = (e: React.MouseEvent) => {
    const btn = buttonRef.current;
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    const dx = e.clientX - centerX;
    const dy = e.clientY - centerY;
    const dist = Math.sqrt(dx * dx + dy * dy);
    
    if (dist < 120) { // pull radius
      const pullX = (dx / dist) * Math.min(12, dist * 0.1);
      const pullY = (dy / dist) * Math.min(12, dist * 0.1);
      setMousePos({ x: pullX, y: pullY });
    } else {
      setMousePos({ x: 0, y: 0 });
    }
  };

  const handleMouseLeave = () => {
    setMousePos({ x: 0, y: 0 });
  };

  const handleClayMouseMove = (e: React.MouseEvent) => {
    const card = clayCardRef.current;
    if (!card) return;
    const rect = card.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;
    const mouseX = e.clientX - rect.left - width / 2;
    const mouseY = e.clientY - rect.top - height / 2;
    const rotateX = -(mouseY / (height / 2)) * 6; // max 6 degrees
    const rotateY = (mouseX / (width / 2)) * 6;
    setTilt({ x: rotateX, y: rotateY });
  };

  const handleClayMouseLeave = () => {
    setTilt({ x: 0, y: 0 });
  };

  // Studio launch transition trigger
  const handleLaunch = () => {
    setShowStudio(true);
  };

  // anime.js v4 timeline animations on mount
  useEffect(() => {
    if (showStudio) return; // skip if studio is open
    const scope = createScope({ root: pageScopeRef });
    scope.add(() => {
      // 1. Animate Navbar
      animate('.nav-reveal', {
        opacity: [0, 1],
        translateY: [-20, 0],
        duration: 800,
        easing: 'easeOutQuad'
      });

      // 2. Animate Wordmark
      animate('.wordmark-reveal', {
        opacity: [0, 1],
        translateY: [25, 0],
        duration: 900,
        delay: 150,
        easing: 'easeOutQuad'
      });

      // 3. Animate Headline
      animate('.headline-reveal', {
        opacity: [0, 1],
        translateY: [25, 0],
        duration: 900,
        delay: 300,
        easing: 'easeOutQuad'
      });

      // 4. Animate CTA Button
      animate('.cta-reveal', {
        opacity: [0, 1],
        translateY: [25, 0],
        duration: 900,
        delay: 450,
        easing: 'easeOutQuad'
      });
    });

    return () => {
      scope.revert();
    };
  }, [showStudio]);

  const featureVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: (i: number) => ({
      opacity: 1,
      y: 0,
      transition: {
        delay: i * 0.15,
        duration: 0.6,
        ease: "easeOut" as const
      }
    })
  };

  const steps = [
    {
      num: "01 / FLOW",
      label: "TRACE",
      title: "Paste & Execute.",
      desc: "Paste any function, class, or LeetCode solution. AlgoLens steps through the real execution line by line, no console.log needed."
    },
    {
      num: "02 / DATA",
      label: "INSPECT",
      title: "Watch State Mutate.",
      desc: "Watch variables, arrays, trees, and heap structures update live as the code runs. Every state change is visualized as it happens."
    },
    {
      num: "03 / INSIGHT",
      label: "UNDERSTAND",
      title: "Trace Explanations.",
      desc: "See the shape of the algorithm, not just the output. Recursion, pointers, and traversal patterns become visible instead of imagined."
    }
  ];

  return (
    <div 
      ref={pageScopeRef} 
      className="relative w-screen h-screen overflow-hidden text-[#8e8e95] selection:bg-[#bc7155]/20"
    >
      {/* Raw HTML style tag injection to force absolute body resets and scrollbar death */}
      <style dangerouslySetInnerHTML={{ __html: `
        html, body {
          width: 100vw !important;
          height: 100vh !important;
          max-height: 100vh !important;
          overflow: hidden !important;
          margin: 0 !important;
          padding: 0 !important;
          position: fixed !important;
          background-color: #000d10 !important; /* Force root dark base here */
        }
        ::-webkit-scrollbar {
          display: none !important;
          width: 0px !important;
        }
      ` }} />

      {/* GLOBAL ETHEREAL BACKGROUND LAYER */}
      <EtheralShadow 
        color="rgba(214, 94, 56, 0.5)" 
        animation={{ scale: 120, speed: 50 }} 
        noise={{ opacity: 0.18, scale: 1.2 }} 
        sizing="fill" 
        className="absolute inset-0 -z-10 pointer-events-none select-none"
      />

      {/* LANDING LAYER */}
      <div 
        style={{ 
          display: renderLanding ? 'block' : 'none',
          pointerEvents: showStudio ? 'none' : 'auto'
        }} 
        className={`absolute inset-0 z-10 w-full bg-transparent ${showStudio ? 'h-screen max-h-screen overflow-hidden' : 'h-full overflow-y-auto overflow-x-hidden custom-scrollbar'}`}
      >
        <div className="w-full min-h-full flex flex-col gap-20">
          
          {/* Navbar */}
          <header 
            style={{
              transform: showStudio ? 'translateY(-100px) scale(0.95)' : 'translateY(0) scale(1)',
              opacity: showStudio ? 0 : 1,
              transition: 'all 500ms cubic-bezier(0.85, 0, 0.15, 1)',
            }}
            className="nav-reveal relative z-50 w-[calc(100%-2rem)] max-w-5xl mx-auto px-4 py-2 flex justify-between items-center border border-[#d5d3d4]/10 bg-transparent backdrop-blur-sm rounded-[1000px] mt-4 sm:px-6 sm:py-4 sm:mt-6 select-none opacity-0"
          >
            <div className="flex items-center">
              <div className="text-lg sm:text-xl font-bold tracking-[-1.5px] text-white flex items-center select-none">
                Alg
                <span className="relative inline-flex items-center justify-center mx-[2px] w-[1em] h-[1em] text-white">
                  <Search className="w-full h-full" strokeWidth={3} />
                </span>
                Lens
              </div>
            </div>

            <div className="flex items-center gap-3 sm:gap-6">
              <SocialButton className="flex" />
              <button 
                onClick={handleLaunch}
                className="hidden sm:block px-4 py-1.5 sm:px-6 sm:py-2 border border-white text-white text-base sm:text-[18px] font-bold rounded-[1000px] hover:bg-white hover:text-[#000d10] transition-all duration-150"
              >
                Studio
              </button>
            </div>
          </header>

          {/* Hero Section - Centered Vertically */}
          <main className="w-full max-w-5xl mx-auto px-4 sm:px-6 flex flex-col justify-center items-center min-h-[60vh] md:min-h-[calc(100vh-150px)]">
            <div 
              style={{
                transform: showStudio ? 'scale(1.1) rotate(-1deg)' : 'scale(1) rotate(0deg)',
                filter: showStudio ? 'blur(8px)' : 'blur(0px)',
                opacity: showStudio ? 0 : 1,
                transition: 'all 500ms cubic-bezier(0.34, 1.56, 0.64, 1)',
              }}
              className="w-full flex flex-col items-center text-center border-b border-[#d5d3d4]/10 pb-10 sm:pb-16 gap-6 sm:gap-10"
            >
              {/* Quiet Luxury Index Tag */}
              <span className="text-xs font-mono text-[#8e8e95] tracking-[3px] uppercase block opacity-70">INDEX // 01 REASONING ENGINE</span>

              {/* Top: Pixel Drift Particle Typography (Centered) */}
              <div className="wordmark-reveal w-full max-w-3xl select-none h-[120px] sm:h-[180px] md:h-[220px] flex items-center justify-center opacity-0">
                <PixelDrift
                  text="AlgoLens"
                  colors={["#ffffff", "#8e8e95", "#ffffff"]}
                  mode="onHover"
                  fontSize={140}
                  autoFit={true}
                  particleCount={35}
                  particleSize={6}
                  mouseRadius={120}
                  mouseForce={25}
                  style={{ width: "100%", height: "100%" }}
                />
              </div>
              
              {/* Headline & Magnetic CTA (Centered) */}
              <div className="flex flex-col items-center gap-6 max-w-2xl">
                <h1 className="headline-reveal text-[24px] sm:text-[32px] md:text-[42px] font-bold leading-[0.95] tracking-[-1.5px] text-slate-300 opacity-0">
                  See Code Execute.
                </h1>
                <div className="cta-reveal opacity-0">
                  <motion.button
                    ref={buttonRef}
                    onMouseMove={handleMouseMove}
                    onMouseLeave={handleMouseLeave}
                    animate={{ x: mousePos.x, y: mousePos.y }}
                    transition={{ type: "spring", stiffness: 150, damping: 15 }}
                    onClick={handleLaunch}
                    className="inline-flex items-center gap-2 px-6 py-3 sm:px-8 sm:py-3.5 border border-white text-white font-bold rounded-[1000px] hover:bg-white hover:text-[#000d10] transition-colors duration-150 text-base sm:text-[18px]"
                  >
                    Launch Studio
                    <ArrowRight className="w-5 h-5" />
                  </motion.button>
                </div>
              </div>
            </div>
          </main>

          {/* Lower Page Elements Group (Feature Grid, Sandbox, details, footer) */}
          <div
            style={{
              transform: showStudio ? 'translateY(150px) scale(0.9)' : 'translateY(0) scale(1)',
              opacity: showStudio ? 0 : 1,
              transition: 'all 500ms cubic-bezier(0.85, 0, 0.15, 1)',
            }}
            className="w-full flex flex-col gap-20"
          >
            {/* Feature Grid: 2-column, Dark Canvas */}
            <section className="w-full max-w-5xl mx-auto px-4 sm:px-6 py-4 flex flex-col gap-8 sm:gap-12">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-16 gap-y-8 sm:gap-y-12">
                {steps.map((step, idx) => (
                  <motion.div
                    key={step.label}
                    custom={idx}
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true, margin: "-50px" }}
                    variants={featureVariants}
                    className={`border-t border-[#d5d3d4]/10 hover:border-white/30 pt-6 flex flex-col gap-3 sm:gap-4 transition-all duration-300 group hover:-translate-y-1 ${idx === 2 ? 'md:col-span-2' : ''}`}
                  >
                    <div className="flex items-center justify-between text-[#8e8e95] font-mono text-xs">
                      <div className="flex items-center gap-2">
                        <span>{step.num}</span>
                        {step.label === "TRACE" && <Code className="w-3.5 h-3.5 group-hover:text-white group-hover:translate-x-0.5 transition-all duration-200" />}
                        {step.label === "INSPECT" && <Eye className="w-3.5 h-3.5 group-hover:text-white group-hover:translate-x-0.5 transition-all duration-200" />}
                        {step.label === "UNDERSTAND" && <BookOpen className="w-3.5 h-3.5 group-hover:text-white group-hover:translate-x-0.5 transition-all duration-200" />}
                      </div>
                      <span className="group-hover:text-white transition-colors duration-200">{step.label}</span>
                    </div>
                    <h3 className="text-lg sm:text-xl sm:text-[23px] font-bold tracking-tight text-white group-hover:text-white transition-colors duration-200">
                      {step.title}
                    </h3>
                    <p className={`text-base sm:text-[18px] leading-[26px] sm:leading-[29px] text-[#8e8e95] group-hover:text-slate-300 transition-colors duration-200 font-light ${idx === 2 ? 'max-w-3xl' : ''}`}>
                      {step.desc}
                    </p>
                  </motion.div>
                ))}
              </div>
            </section>

            {/* LeetCode Sandbox - transparent, no band */}
            <section className="w-full max-w-5xl mx-auto px-4 sm:px-6 py-4 overflow-hidden" style={{ perspective: 1000 }}>
              <motion.div 
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-50px" }}
                transition={{ duration: 0.7, ease: "easeOut" }}
                className="w-full"
              >
                <motion.div
                  ref={clayCardRef}
                  onMouseMove={handleClayMouseMove}
                  onMouseLeave={handleClayMouseLeave}
                  animate={{ rotateX: tilt.x, rotateY: tilt.y }}
                  transition={{ type: "spring", stiffness: 150, damping: 15 }}
                  style={{ transformStyle: "preserve-3d" }}
                  className="w-full bg-white/5 backdrop-blur-sm text-[#eff1f5] p-6 sm:p-10 md:p-16 rounded-2xl flex flex-col md:flex-row items-start md:items-center justify-between gap-6 sm:gap-8 border border-[#ffa116]/10 hover:border-[#ffa116]/40 hover:brightness-[1.02] transition-all duration-150 cursor-pointer"
                >
                  <div className="max-w-xl" style={{ transform: "translateZ(30px)" }}>
                    <span className="text-xs font-mono font-bold uppercase tracking-[2px] text-[#ffa116]">04 // LeetCode Sandbox</span>
                    <h2 className="text-2xl sm:text-3xl md:text-[42px] font-bold tracking-tight mt-2 leading-none text-white">
                      Run solutions directly in-browser.
                    </h2>
                    <p className="text-base sm:text-[18px] leading-[26px] sm:leading-[29px] mt-2 sm:mt-4 text-[#8e8e95] font-light">
                      Import any LeetCode problem, paste your solution, and witness variables, pointers, and iterations morph into visual state trees in real-time.
                    </p>
                  </div>
                  <div className="flex-shrink-0" style={{ transform: "translateZ(40px)" }}>
                    <button 
                      onClick={handleLaunch}
                      className="px-6 py-3 sm:px-8 sm:py-4 bg-[#ffa116] text-[#181818] text-base sm:text-[18px] font-bold rounded-[1000px] hover:bg-[#ffa116]/90 border border-[#ffa116] transition-all duration-150"
                    >
                      Try in Studio
                    </button>
                  </div>
                </motion.div>
              </motion.div>
            </section>

            {/* Live Tracing Details: Restructured to White text on Dark Canvas */}
            <section className="w-full max-w-5xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
              <motion.div 
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-50px" }}
                transition={{ duration: 0.7, ease: "easeOut" }}
                className="flex justify-center md:justify-end w-full"
              >
                <div className="max-w-xl text-center items-center md:text-right md:items-end flex flex-col gap-4">
                  <span className="text-xs font-mono text-[#8e8e95] tracking-[2px]">05 // DYNAMIC EVALUATION</span>
                  <h2 className="text-3xl sm:text-4xl md:text-[56px] font-bold tracking-tight leading-none text-white">
                    Live Interpretation.
                  </h2>
                  <p className="text-base sm:text-[18px] leading-[26px] sm:leading-[29px] text-[#8e8e95] font-light mt-1 sm:mt-2">
                    AlgoLens runs a secure custom Python interpreter in the backend. As you step through code, it traces local scopes, registers operations, and feeds state mutations directly to the visual canvas.
                  </p>
                </div>
              </motion.div>
            </section>

            {/* Terminal Footer - pinned to bottom, transparent */}
            <motion.footer 
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, ease: "easeOut" }}
              className="mt-auto w-full text-[#8e8e95] font-mono text-xs py-6 sm:py-8 px-4 sm:px-6 border-t border-[#d5d3d4]/10 select-none"
            >
              <div className="max-w-5xl mx-auto flex flex-col sm:flex-row justify-between items-center gap-4">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-white/40" />
                  <span>SYSTEM: ACTIVE</span>
                </div>
                <div>algolens --version 1.2.0 | © {new Date().getFullYear()}</div>
              </div>
            </motion.footer>
          </div>

        </div>
      </div>

      {/* STUDIO LAYER */}
      <div 
        style={{ 
          display: renderStudio ? 'block' : 'none',
          opacity: animateStudioVisual ? 1 : 0,
          clipPath: animateStudioVisual 
            ? 'polygon(0 0, 100% 0, 100% 100%, 0 100%)' 
            : 'polygon(0 50%, 100% 50%, 100% 50%, 0 50%)',
          transition: 'clip-path 600ms cubic-bezier(0.86, 0, 0.07, 1), opacity 400ms linear',
          pointerEvents: showStudio ? 'auto' : 'none'
        }} 
        className="absolute inset-0 z-20 w-full h-screen max-h-screen overflow-hidden"
      >
        <Studio onBack={() => setShowStudio(false)} />
      </div>

    </div>
  );
}
