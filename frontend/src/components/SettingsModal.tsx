"use client";

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Settings as SettingsIcon, X } from 'lucide-react';
import { useSettings } from '@/contexts/SettingsContext';

export default function SettingsModal() {
  const [isOpen, setIsOpen] = useState(false);
  const { settings, updateSettings, resetSettings } = useSettings();

  return (
    <>
      <button 
        onClick={() => setIsOpen(true)}
        className="btn-ghost flex items-center gap-2"
      >
        <SettingsIcon className="w-4 h-4" />
        Settings
      </button>

      <AnimatePresence>
        {isOpen && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
              onClick={() => setIsOpen(false)}
            />
            
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              className="relative w-full max-w-2xl bg-bg-surface border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
            >
              <div className="flex items-center justify-between p-6 border-b border-white/10">
                <h2 className="text-xl font-bold text-text-heading">Settings</h2>
                <button 
                  onClick={() => setIsOpen(false)}
                  className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-white/5 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-6 space-y-8 custom-scrollbar text-text-body">
                
                {/* UI Theme */}
                <section>
                  <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">UI Theme</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {(['void', 'slate', 'obsidian'] as const).map(mode => (
                      <button
                        key={mode}
                        onClick={() => updateSettings({ uiMode: mode })}
                        className={`p-4 rounded-xl border text-left transition-all ${settings.uiMode === mode ? 'border-brand-teal bg-brand-teal/10' : 'border-white/10 hover:border-white/20 hover:bg-white/5'}`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <div className="font-medium capitalize text-text-heading">{mode}</div>
                          {/* Swatches */}
                          <div className="flex items-center gap-1">
                            <span className="w-3.5 h-3.5 rounded-full border border-white/10" style={{ backgroundColor: mode === 'void' ? '#000d10' : mode === 'slate' ? '#0a0e12' : '#060608' }} />
                            <span className="w-3.5 h-3.5 rounded-full" style={{ backgroundColor: mode === 'void' ? '#bc7155' : mode === 'slate' ? '#4ca6b8' : '#d4833b' }} />
                          </div>
                        </div>
                        <div className="text-xs text-slate-400">
                          {mode === 'void' && 'Deep space base with Constellation Void accents.'}
                          {mode === 'slate' && 'Cooler blue-gray base with desaturated cyan/steel accents.'}
                          {mode === 'obsidian' && 'True near-black base with warmer amber/bronze accents.'}
                        </div>
                      </button>
                    ))}
                  </div>
                </section>

                {/* Graphics Quality */}
                <section>
                  <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">Graphics Quality</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {(['cinematic', 'balanced', 'performance'] as const).map(quality => (
                      <button
                        key={quality}
                        onClick={() => updateSettings({ graphicsQuality: quality })}
                        className={`p-4 rounded-xl border text-left transition-all ${settings.graphicsQuality === quality ? 'border-brand-teal bg-brand-teal/10' : 'border-white/10 hover:border-white/20 hover:bg-white/5'}`}
                      >
                        <div className="font-medium capitalize mb-1 text-text-heading">{quality}</div>
                        <div className="text-xs text-slate-400">
                          {quality === 'cinematic' && 'Max particles, refraction, and bloom.'}
                          {quality === 'balanced' && 'Moderate particles, standard glow.'}
                          {quality === 'performance' && 'Minimal effects, highest FPS.'}
                        </div>
                      </button>
                    ))}
                  </div>
                </section>

                {/* Execution Limits */}
                <section>
                  <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">Execution Limits</h3>
                  <div className="space-y-4">
                    <div>
                      <label className="flex flex-col gap-1">
                        <span className="text-sm font-medium">Max Recursion Depth</span>
                        <input 
                          type="number" 
                          min={10} 
                          max={10000} 
                          value={settings.maxRecursionDepth}
                          onChange={e => updateSettings({ maxRecursionDepth: parseInt(e.target.value) || 1000 })}
                          className="w-full bg-black/40 border border-white/10 rounded-lg p-2 text-sm focus:border-brand-teal outline-none text-text-body"
                        />
                      </label>
                      <p className="text-xs text-slate-400 mt-1">Prevents infinite recursion from crashing the visualizer.</p>
                    </div>
                  </div>
                </section>

                {/* Playback */}
                <section>
                  <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">Playback</h3>
                  <div className="space-y-4">
                    <label className="flex items-center justify-between">
                      <span className="text-sm font-medium">Default Animation Speed</span>
                      <select 
                        value={settings.animationSpeed}
                        onChange={e => updateSettings({ animationSpeed: e.target.value as any })}
                        className="bg-black/40 border border-white/10 rounded-lg p-2 text-sm outline-none text-text-body"
                      >
                        <option value="slow">Slow</option>
                        <option value="normal">Normal</option>
                        <option value="fast">Fast</option>
                      </select>
                    </label>
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input 
                        type="checkbox" 
                        checked={settings.autoRunOnPaste}
                        onChange={e => updateSettings({ autoRunOnPaste: e.target.checked })}
                        className="accent-brand-teal w-4 h-4"
                      />
                      <span className="text-sm font-medium">Auto-run on code paste</span>
                    </label>
                  </div>
                </section>

                {/* Visualization Display */}
                <section>
                  <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">Visualization Display</h3>
                  <div className="space-y-3">
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input 
                        type="checkbox" 
                        checked={settings.showValueLabels}
                        onChange={e => updateSettings({ showValueLabels: e.target.checked })}
                        className="accent-brand-teal w-4 h-4"
                      />
                      <span className="text-sm font-medium">Show node value labels</span>
                    </label>
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input 
                        type="checkbox" 
                        checked={settings.showIndexAnnotations}
                        onChange={e => updateSettings({ showIndexAnnotations: e.target.checked })}
                        className="accent-brand-teal w-4 h-4"
                      />
                      <span className="text-sm font-medium">Show array indices / depth annotations</span>
                    </label>
                    <label className="flex items-center justify-between mt-4">
                      <span className="text-sm font-medium">Node Size</span>
                      <select 
                        value={settings.nodeSize}
                        onChange={e => updateSettings({ nodeSize: e.target.value as any })}
                        className="bg-black/40 border border-white/10 rounded-lg p-2 text-sm outline-none text-text-body"
                      >
                        <option value="small">Small</option>
                        <option value="medium">Medium</option>
                        <option value="large">Large</option>
                      </select>
                    </label>
                    <label className="flex items-center gap-3 cursor-pointer mt-4 pt-2">
                      <input 
                        type="checkbox" 
                        checked={settings.colorBlindSafe}
                        onChange={e => updateSettings({ colorBlindSafe: e.target.checked })}
                        className="accent-brand-teal w-4 h-4"
                      />
                      <span className="text-sm font-medium text-brand-teal">Color-blind safe palette</span>
                    </label>
                  </div>
                </section>
                
                {/* Accessibility */}
                <section>
                  <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">Accessibility</h3>
                  <div className="space-y-4">
                    <label className="flex items-center gap-3 cursor-pointer">
                      <input 
                        type="checkbox" 
                        checked={settings.reducedMotion}
                        onChange={e => updateSettings({ reducedMotion: e.target.checked })}
                        className="accent-brand-teal w-4 h-4"
                      />
                      <span className="text-sm font-medium">Reduce Motion (Disable animations)</span>
                    </label>
                    <label className="flex items-center justify-between">
                      <span className="text-sm font-medium">Text Size</span>
                      <select 
                        value={settings.textSize}
                        onChange={e => updateSettings({ textSize: e.target.value as any })}
                        className="bg-black/40 border border-white/10 rounded-lg p-2 text-sm outline-none text-text-body"
                      >
                        <option value="small">Small</option>
                        <option value="default">Default</option>
                        <option value="large">Large</option>
                      </select>
                    </label>
                  </div>
                </section>

                {/* Data */}
                <section className="pt-4 border-t border-white/10">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-text-heading mb-1">Reset to Defaults</h3>
                      <p className="text-xs text-slate-400">Settings are stored locally in your browser.</p>
                    </div>
                    <button 
                      onClick={resetSettings}
                      className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-sm font-medium transition-colors"
                    >
                      Reset All
                    </button>
                  </div>
                </section>

              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </>
  );
}
