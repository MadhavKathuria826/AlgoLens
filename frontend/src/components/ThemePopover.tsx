"use client";

import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useSettings } from '@/contexts/SettingsContext';
import { Palette } from 'lucide-react';

export default function ThemePopover() {
  const [isOpen, setIsOpen] = useState(false);
  const { settings, updateSettings } = useSettings();
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  return (
    <div className="relative" ref={popoverRef}>
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className={`btn-ghost flex items-center gap-2 ${isOpen ? 'text-brand-teal bg-white/5' : ''}`}
      >
        <Palette className="w-4 h-4" />
        Theme
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="absolute top-full right-0 mt-2 w-64 bg-bg-surface border border-white/10 rounded-xl shadow-2xl p-4 z-50 flex flex-col gap-4 text-text-body"
          >
            <div>
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">UI Mode</h4>
              <div className="flex flex-col gap-1">
                {(['dark', 'light', 'high-contrast'] as const).map(mode => (
                  <label key={mode} className="flex items-center gap-3 p-2 rounded hover:bg-white/5 cursor-pointer">
                    <input 
                      type="radio" 
                      name="uiMode" 
                      checked={settings.uiMode === mode}
                      onChange={() => updateSettings({ uiMode: mode })}
                      className="accent-brand-teal"
                    />
                    <span className="text-sm capitalize">{mode.replace('-', ' ')}</span>
                  </label>
                ))}
              </div>
            </div>
            
            <div className="h-px bg-white/10 w-full" />

            <div>
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Editor Theme</h4>
              <div className="flex flex-col gap-1">
                {(['vs-dark', 'dracula', 'monokai', 'light'] as const).map(theme => (
                  <label key={theme} className="flex items-center gap-3 p-2 rounded hover:bg-white/5 cursor-pointer">
                    <input 
                      type="radio" 
                      name="editorTheme" 
                      checked={settings.editorTheme === theme}
                      onChange={() => updateSettings({ editorTheme: theme })}
                      className="accent-brand-teal"
                    />
                    <span className="text-sm capitalize">{theme.replace('-', ' ')}</span>
                  </label>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
