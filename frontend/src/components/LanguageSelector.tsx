"use client";

import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useSettings, LanguageMode } from '@/contexts/SettingsContext';
import { Code2, ChevronDown } from 'lucide-react';

export interface LanguageOption {
  id: LanguageMode;
  name: string;
  extension: string;
}

export const SUPPORTED_LANGUAGES: LanguageOption[] = [
  { id: 'python', name: 'Python', extension: '.py' },
  { id: 'cpp', name: 'C++', extension: '.cpp' },
];

export default function LanguageSelector({ onChange }: { onChange?: (lang: LanguageMode) => void }) {
  const [isOpen, setIsOpen] = useState(false);
  const { settings, updateSettings } = useSettings();
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentLanguage = SUPPORTED_LANGUAGES.find(l => l.id === settings.language) || SUPPORTED_LANGUAGES[0];

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const handleSelect = (langId: LanguageMode) => {
    updateSettings({ language: langId });
    if (onChange) {
      onChange(langId);
    }
    setIsOpen(false);
  };

  return (
    <div className="relative" ref={dropdownRef} id="language-selector-wrapper">
      <button
        id="language-selector-button"
        data-testid="language-selector-button"
        onClick={() => setIsOpen(!isOpen)}
        className={`btn-ghost flex items-center gap-2 transition-colors ${isOpen ? 'text-brand-teal bg-white/5' : ''}`}
        title="Select Programming Language"
      >
        <Code2 className="w-4 h-4 text-brand-teal" />
        <span className="font-medium">{currentLanguage.name}</span>
        <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            id="language-selector-dropdown"
            data-testid="language-selector-dropdown"
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="absolute top-full right-0 mt-2 w-48 bg-bg-surface border border-white/10 rounded-xl shadow-2xl p-2 z-50 flex flex-col gap-1 text-text-body"
          >
            <div className="px-2 py-1 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
              Language
            </div>
            {SUPPORTED_LANGUAGES.map(lang => (
              <button
                key={lang.id}
                data-testid={`lang-option-${lang.id}`}
                onClick={() => handleSelect(lang.id)}
                className={`flex items-center justify-between p-2 rounded-lg text-sm text-left transition-colors cursor-pointer ${
                  settings.language === lang.id
                    ? 'bg-brand-teal/15 text-brand-teal font-semibold border border-brand-teal/30'
                    : 'hover:bg-white/5 text-text-body'
                }`}
              >
                <span>{lang.name}</span>
                <span className="text-xs font-mono opacity-50">{lang.extension}</span>
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
