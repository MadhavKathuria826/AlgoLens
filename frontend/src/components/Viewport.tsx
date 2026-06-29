import React, { useRef, useState, useCallback, useEffect } from 'react';
import { Maximize } from 'lucide-react';

interface ViewportProps {
  children: React.ReactNode;
}

export default function Viewport({ children }: ViewportProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  
  const [camera, setCamera] = useState({ x: 0, y: 0, zoom: 1 });
  const [isDragging, setIsDragging] = useState(false);
  const lastMousePos = useRef({ x: 0, y: 0 });

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    // Only left click pans
    if (e.button !== 0) return;
    
    // Ignore clicks on buttons or interactive elements
    const target = e.target as HTMLElement;
    if (target.closest('button') || target.tagName === 'INPUT') return;

    setIsDragging(true);
    lastMousePos.current = { x: e.clientX, y: e.clientY };
    e.currentTarget.setPointerCapture(e.pointerId);
  }, []);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!isDragging) return;

    const dx = e.clientX - lastMousePos.current.x;
    const dy = e.clientY - lastMousePos.current.y;

    setCamera((prev) => ({
      ...prev,
      x: prev.x + dx,
      y: prev.y + dy
    }));

    lastMousePos.current = { x: e.clientX, y: e.clientY };
  }, [isDragging]);

  const handlePointerUp = useCallback((e: React.PointerEvent) => {
    setIsDragging(false);
    e.currentTarget.releasePointerCapture(e.pointerId);
  }, []);

  const resetView = () => {
    setCamera({ x: 0, y: 0, zoom: 1 });
  };

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const onWheel = (e: WheelEvent) => {
      // Ignore wheel events inside scrollable children if we ever have them
      // But for now, we just zoom the canvas
      e.preventDefault();
      
      const zoomSensitivity = 0.001;
      const delta = -e.deltaY * zoomSensitivity;
      
      setCamera((prev) => {
        const newZoom = Math.min(Math.max(0.1, prev.zoom * Math.exp(delta)), 5);
        
        const rect = el.getBoundingClientRect();
        const cursorX = e.clientX - rect.left;
        const cursorY = e.clientY - rect.top;

        const centerX = rect.width / 2;
        const centerY = rect.height / 2;

        const worldX = (cursorX - centerX - prev.x) / prev.zoom;
        const worldY = (cursorY - centerY - prev.y) / prev.zoom;

        const newX = cursorX - centerX - worldX * newZoom;
        const newY = cursorY - centerY - worldY * newZoom;

        return { x: newX, y: newY, zoom: newZoom };
      });
    };

    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  return (
    <div 
      className="flex-1 relative w-full h-full overflow-hidden bg-transparent"
      ref={containerRef}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      style={{ cursor: isDragging ? 'grabbing' : 'grab', touchAction: 'none' }}
    >
      <div 
        className="absolute top-1/2 left-1/2"
        style={{
          transform: `translate(calc(-50% + ${camera.x}px), calc(-50% + ${camera.y}px)) scale(${camera.zoom})`,
          transformOrigin: 'center center',
          transition: isDragging ? 'none' : 'transform 0.1s ease-out'
        }}
      >
        {children}
      </div>

      <div className="absolute bottom-6 right-6 flex gap-2 z-50">
        <button 
          onClick={resetView}
          className="bg-black/50 hover:bg-black/70 text-slate-300 p-2.5 rounded-xl backdrop-blur-md shadow-lg border border-white/10 transition-colors"
          title="Reset View"
        >
          <Maximize size={18} />
        </button>
      </div>
    </div>
  );
}
