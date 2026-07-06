"use client";

import React, { createContext, useContext, useState, useEffect } from 'react';

export type UiMode = 'dark' | 'light' | 'high-contrast';
export type EditorTheme = 'vs-dark' | 'dracula' | 'monokai' | 'light';
export type GraphicsQuality = 'cinematic' | 'balanced' | 'performance';
export type SpeedPreset = 'slow' | 'normal' | 'fast';
export type NodeSize = 'small' | 'medium' | 'large';
export type TextSize = 'small' | 'default' | 'large';

export interface AppSettings {
  // Theme
  uiMode: UiMode;
  editorTheme: EditorTheme;

  // Graphics
  graphicsQuality: GraphicsQuality;

  // Execution Limits
  maxRecursionDepth: number;
  executionTimeoutMs: number;

  // Playback
  animationSpeed: SpeedPreset;
  autoRunOnPaste: boolean;

  // Visualization Display
  showValueLabels: boolean;
  showIndexAnnotations: boolean;
  nodeSize: NodeSize;
  colorBlindSafe: boolean;

  // Accessibility
  reducedMotion: boolean;
  textSize: TextSize;
}

export const defaultSettings: AppSettings = {
  uiMode: 'dark',
  editorTheme: 'vs-dark',
  graphicsQuality: 'balanced',
  maxRecursionDepth: 1000,
  executionTimeoutMs: 10000,
  animationSpeed: 'normal',
  autoRunOnPaste: false,
  showValueLabels: true,
  showIndexAnnotations: true,
  nodeSize: 'medium',
  colorBlindSafe: false,
  reducedMotion: false,
  textSize: 'default',
};

interface SettingsContextType {
  settings: AppSettings;
  updateSettings: (newSettings: Partial<AppSettings>) => void;
  resetSettings: () => void;
}

const SettingsContext = createContext<SettingsContextType>({
  settings: defaultSettings,
  updateSettings: () => {},
  resetSettings: () => {},
});

export const SettingsProvider = ({ children }: { children: React.ReactNode }) => {
  const [settings, setSettings] = useState<AppSettings>(defaultSettings);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem('algolens-settings');
    if (saved) {
      try {
        setSettings({ ...defaultSettings, ...JSON.parse(saved) });
      } catch (e) {
        console.error("Failed to parse settings");
      }
    }
    setIsLoaded(true);
  }, []);

  // Update HTML class for themes
  useEffect(() => {
    if (!isLoaded) return;
    const html = document.documentElement;
    html.classList.remove(
      'dark', 'light', 'high-contrast', 
      'text-sm', 'text-base', 'text-lg', 
      'reduced-motion', 'color-blind-safe',
      'node-size-small', 'node-size-medium', 'node-size-large',
      'hide-value-labels', 'hide-index-annotations'
    );
    
    if (settings.uiMode === 'dark') html.classList.add('dark');
    if (settings.uiMode === 'light') html.classList.add('light');
    if (settings.uiMode === 'high-contrast') html.classList.add('high-contrast', 'dark'); // High contrast is dark based

    if (settings.reducedMotion) html.classList.add('reduced-motion');
    if (settings.colorBlindSafe) html.classList.add('color-blind-safe');
    
    if (!settings.showValueLabels) html.classList.add('hide-value-labels');
    if (!settings.showIndexAnnotations) html.classList.add('hide-index-annotations');
    html.classList.add(`node-size-${settings.nodeSize}`);
    
    // add text size
    if (settings.textSize === 'small') html.classList.add('text-sm');
    if (settings.textSize === 'default') html.classList.add('text-base');
    if (settings.textSize === 'large') html.classList.add('text-lg');

    localStorage.setItem('algolens-settings', JSON.stringify(settings));
  }, [settings, isLoaded]);

  const updateSettings = (newSettings: Partial<AppSettings>) => {
    setSettings((prev) => ({ ...prev, ...newSettings }));
  };

  const resetSettings = () => {
    setSettings(defaultSettings);
  };

  return (
    <SettingsContext.Provider value={{ settings, updateSettings, resetSettings }}>
      {children}
    </SettingsContext.Provider>
  );
};

export const useSettings = () => useContext(SettingsContext);
