"use client";

import { motion } from 'framer-motion';
import { LayoutGrid, ListTree, GitBranch, Repeat, Terminal, Network } from 'lucide-react';

const MODULES = [
  { id: 1, title: 'Variables Lab', desc: 'Variable assignment, updates, and references. Visualize memory cells.', icon: LayoutGrid, color: 'text-blue-400', bg: 'bg-blue-400/10', border: 'border-blue-400/20' },
  { id: 2, title: 'Lists Lab', desc: 'Append, Insert, Remove, Indexing. Visualize list growth.', icon: ListTree, color: 'text-emerald-400', bg: 'bg-emerald-400/10', border: 'border-emerald-400/20' },
  { id: 3, title: 'Conditions Lab', desc: 'if, elif, else. Show decision branches.', icon: GitBranch, color: 'text-orange-400', bg: 'bg-orange-400/10', border: 'border-orange-400/20' },
  { id: 4, title: 'Loops Lab', desc: 'for loops, while loops. Show iteration visually.', icon: Repeat, color: 'text-purple-400', bg: 'bg-purple-400/10', border: 'border-purple-400/20' },
  { id: 5, title: 'Functions Lab', desc: 'Parameters, Return values, Scope. Visualize function calls.', icon: Terminal, color: 'text-pink-400', bg: 'bg-pink-400/10', border: 'border-pink-400/20' },
  { id: 6, title: 'Recursion Lab', desc: 'Recursive calls, Base cases. Show recursion trees.', icon: Network, color: 'text-red-400', bg: 'bg-red-400/10', border: 'border-red-400/20' },
];

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1 }
  }
};

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 }
};

export default function LearnMode() {
  return (
    <div className="max-w-7xl mx-auto p-8 pt-12">
      <div className="mb-12">
        <h1 className="text-4xl font-bold mb-4">Learn Mode</h1>
        <p className="text-slate-400 text-lg max-w-3xl">
          Master the fundamentals of Python execution before visualizing your own code. 
          Select a lab below to start the interactive lesson.
        </p>
      </div>

      <motion.div 
        variants={container}
        initial="hidden"
        animate="show"
        className="grid md:grid-cols-2 lg:grid-cols-3 gap-6"
      >
        {MODULES.map((mod) => (
          <motion.div key={mod.id} variants={item}>
            <div className={`glass p-6 h-full flex flex-col cursor-pointer transition-all duration-300 hover:scale-[1.02] hover:shadow-2xl border ${mod.border}`}>
              <div className={`w-12 h-12 rounded-lg flex items-center justify-center mb-4 ${mod.bg} ${mod.color}`}>
                <mod.icon size={24} />
              </div>
              <h3 className="text-xl font-semibold mb-2">{mod.title}</h3>
              <p className="text-slate-400 text-sm flex-grow leading-relaxed">
                {mod.desc}
              </p>
              <div className="mt-6 text-sm font-medium text-slate-300 flex items-center">
                Start Lab <span className="ml-2 opacity-50">→</span>
              </div>
            </div>
          </motion.div>
        ))}
      </motion.div>
    </div>
  );
}
