"use client";

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Play } from 'lucide-react';

interface TestCaseModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmitMethod: (method: string) => void;
  onSubmitTestCase: (testCaseStr: string) => void;
  candidates: string[] | null;
  params: string[] | null;
  error: string | null;
  mode: 'disambiguation' | 'params' | null;
}

export default function TestCaseModal({ isOpen, onClose, onSubmitMethod, onSubmitTestCase, candidates, params, error, mode }: TestCaseModalProps) {
  const [paramValues, setParamValues] = useState<Record<string, string>>({});

  useEffect(() => {
    if (isOpen) {
      setParamValues({});
    }
  }, [isOpen]);

  const handleRunTestCase = () => {
    if (!params) return;
    const testCaseLines: string[] = [];
    for (const p of params) {
      const val = paramValues[p]?.trim();
      if (val) {
        testCaseLines.push(`${p} = ${val}`);
      }
    }
    onSubmitTestCase(testCaseLines.join('\n'));
  };

  return (
    <AnimatePresence>
      {isOpen && mode && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onClose}
          />
          
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            className="relative w-full max-w-lg bg-bg-surface border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col"
          >
            <div className="flex items-center justify-between p-6 border-b border-white/10">
              <h2 className="text-xl font-bold text-text-heading">
                {mode === 'disambiguation' ? 'Select Method to Run' : 'Configure Test Case'}
              </h2>
              <button 
                onClick={onClose}
                className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-6 text-text-body">
              {error && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm font-mono break-all">
                  {error}
                </div>
              )}

              {mode === 'disambiguation' && candidates && (
                <div className="space-y-4">
                  <p className="text-sm text-slate-400">Multiple entry points detected. Which method would you like to visualize?</p>
                  <div className="flex flex-wrap gap-3">
                    {candidates.map(c => (
                      <button
                        key={c}
                        onClick={() => onSubmitMethod(c)}
                        className="px-4 py-2 rounded-full border border-white/10 hover:border-brand-teal hover:bg-brand-teal/10 hover:text-brand-teal transition-all font-mono text-sm"
                      >
                        {c}
                      </button>
                    ))}
                  </div>
                  <div className="flex justify-end gap-3 pt-4 border-t border-white/10 mt-6">
                    <button onClick={onClose} className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-sm font-medium transition-colors">
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {mode === 'params' && params && (
                <div className="space-y-4">
                  <p className="text-sm text-slate-400">Provide Python literals for the following parameters:</p>
                  
                  {params.map(p => (
                    <div key={p}>
                      <label className="flex flex-col gap-1">
                        <span className="text-sm font-mono text-slate-300">{p} =</span>
                        <input 
                          type="text" 
                          value={paramValues[p] || ''}
                          onChange={e => setParamValues(prev => ({ ...prev, [p]: e.target.value }))}
                          placeholder="e.g. [1, 2, 3] or 'hello'"
                          className="w-full bg-black/40 border border-white/10 rounded-lg p-2 font-mono text-sm focus:border-brand-teal outline-none text-text-body placeholder:text-white/20"
                          onKeyDown={e => {
                            if (e.key === 'Enter') handleRunTestCase();
                          }}
                        />
                      </label>
                    </div>
                  ))}

                  <div className="flex justify-end gap-3 pt-4 border-t border-white/10 mt-6">
                    <button onClick={onClose} className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-sm font-medium transition-colors">
                      Cancel
                    </button>
                    <button onClick={handleRunTestCase} className="btn-primary gap-2 text-sm !px-4 !py-2">
                      <Play className="w-4 h-4" /> Run
                    </button>
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
