"use client";

import React, { useState } from 'react';
import { Download, Loader2 } from 'lucide-react';
import { toPng } from 'html-to-image';

export default function ExportButton({ disabled }: { disabled: boolean }) {
  const [isExporting, setIsExporting] = useState(false);

  const handleExport = async () => {
    const el = document.getElementById('export-visualization-panel');
    if (!el) return;

    try {
      setIsExporting(true);
      
      // Temporarily add a background color so it doesn't export transparent/black when outside the main dark theme
      const dataUrl = await toPng(el, {
        cacheBust: true,
        backgroundColor: '#0a0a0a', // A standard dark background matching the theme
        style: {
          borderRadius: '0px',
        }
      });
      
      const link = document.createElement('a');
      link.download = `algolens-visualization-${Date.now()}.png`;
      link.href = dataUrl;
      link.click();
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="relative group/export">
      <button 
        onClick={handleExport}
        disabled={disabled || isExporting}
        className={`btn-ghost flex items-center gap-2 ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
        title={disabled ? "Run your code first" : "Export as PNG"}
      >
        {isExporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
        Export
      </button>
      {disabled && (
        <div className="absolute top-full mt-2 right-0 bg-gray-900 text-white text-xs px-2 py-1 rounded shadow-lg opacity-0 group-hover/export:opacity-100 transition-opacity whitespace-nowrap z-50 pointer-events-none">
          Run your code first
        </div>
      )}
    </div>
  );
}
