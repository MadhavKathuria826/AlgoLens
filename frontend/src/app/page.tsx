"use client";

import { motion } from 'framer-motion';
import Link from 'next/link';
import { Play, Code2, ArrowRight } from 'lucide-react';

export default function Home() {
  return (
    <div className="min-h-[calc(100vh-5rem)] flex flex-col items-center justify-center p-8 relative overflow-hidden">
      {/* Background gradients */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-[120px]" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-emerald-500/10 rounded-full blur-[120px]" />

      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
        className="text-center mb-16 z-10"
      >
        <h1 className="text-5xl md:text-7xl font-bold mb-6 tracking-tight">
          <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-emerald-400 to-teal-400">
            Figma for understanding code.
          </span>
        </h1>
        <p className="text-xl text-slate-400 max-w-2xl mx-auto font-light">
          A visual reasoning engine. Watch your Python code execute step-by-step, 
          see memory update live, and truly understand what happens under the hood.
        </p>
      </motion.div>

      <div className="grid md:grid-cols-2 gap-8 w-full max-w-6xl z-10">
        <motion.div
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          <Link href="/learn" className="block h-full">
            <div className="glass p-8 h-full flex flex-col relative overflow-hidden group">
              <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="h-12 w-12 rounded-xl bg-blue-500/20 flex items-center justify-center mb-6 text-blue-400">
                <Play size={24} />
              </div>
              <h2 className="text-3xl font-semibold mb-4">Learn Mode</h2>
              <p className="text-slate-400 mb-8 flex-grow">
                Interactive educational modules. Understand how variables, loops, and recursion work before you write your own code.
              </p>
              
              <div className="bg-[#0f111a] rounded-lg p-6 mb-8 border border-white/5 relative overflow-hidden">
                <motion.div 
                  className="w-16 h-16 bg-blue-500/20 rounded-lg border border-blue-500/50 flex items-center justify-center text-xl font-mono text-blue-400"
                  animate={{ 
                    x: [0, 100, 0],
                    rotate: [0, 10, 0]
                  }}
                  transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                >
                  x = 5
                </motion.div>
              </div>

              <div className="flex items-center text-blue-400 font-medium">
                Enter Learn Mode <ArrowRight className="ml-2 w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </div>
            </div>
          </Link>
        </motion.div>

        <motion.div
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          <Link href="/studio" className="block h-full">
            <div className="glass p-8 h-full flex flex-col relative overflow-hidden group">
              <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
              <div className="h-12 w-12 rounded-xl bg-emerald-500/20 flex items-center justify-center mb-6 text-emerald-400">
                <Code2 size={24} />
              </div>
              <h2 className="text-3xl font-semibold mb-4">Visualization Studio</h2>
              <p className="text-slate-400 mb-8 flex-grow">
                The core engine. Paste any Python code, run it through our tracer, and watch the execution unfold across the canvas.
              </p>

              <div className="bg-[#0f111a] rounded-lg p-6 mb-8 border border-white/5 flex gap-4">
                <div className="flex-1 border-r border-white/10 pr-4">
                  <div className="h-2 w-3/4 bg-white/10 rounded mb-2" />
                  <div className="h-2 w-1/2 bg-white/10 rounded mb-2" />
                  <div className="h-2 w-5/6 bg-emerald-500/50 rounded mb-2" />
                  <div className="h-2 w-2/3 bg-white/10 rounded" />
                </div>
                <div className="flex-1 pl-2 flex items-center">
                  <motion.div 
                    className="w-full h-12 bg-emerald-500/20 rounded border border-emerald-500/30"
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 1, repeat: Infinity, repeatType: "reverse" }}
                  />
                </div>
              </div>

              <div className="flex items-center text-emerald-400 font-medium">
                Open Visualization Studio <ArrowRight className="ml-2 w-5 h-5 group-hover:translate-x-1 transition-transform" />
              </div>
            </div>
          </Link>
        </motion.div>
      </div>
    </div>
  );
}
