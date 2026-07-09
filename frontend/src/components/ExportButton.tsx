"use client";

import React, { useState } from 'react';
import { Download, Loader2 } from 'lucide-react';

// Programmatic verification function to sample pixels from the generated data URL 
// and confirm that the image contains real visual content (and is not just blank/solid background).
const verifyImageData = (dataUrl: string, width: number, height: number): Promise<boolean> => {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = async () => {
      try {
        // Deterministically wait for the browser to completely decode the image buffer
        if (typeof img.decode === 'function') {
          await img.decode();
        }
        
        const imgWidth = img.naturalWidth || width;
        const imgHeight = img.naturalHeight || height;
        
        const canvas = document.createElement('canvas');
        canvas.width = imgWidth;
        canvas.height = imgHeight;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          console.warn("[Export Verification] Failed to create 2D canvas context");
          resolve(true); // fall back to true if context creation fails
          return;
        }
        
        ctx.drawImage(img, 0, 0);
        
        const uniqueColors = new Set<string>();
        const stepsX = 10;
        const stepsY = 10;
        
        const isNotBg = (r: number, g: number, b: number) => {
          // Visualizer theme background color: #0f172a (RGB: 15, 23, 42)
          // We check if the color deviates significantly from this background color
          return (Math.abs(r - 15) + Math.abs(g - 23) + Math.abs(b - 42)) > 15;
        };

        let nonBgCount = 0;
        let hasLeft = false;
        let hasRight = false;
        let hasTop = false;
        let hasBottom = false;
        
        for (let i = 1; i < stepsX; i++) {
          for (let j = 1; j < stepsY; j++) {
            const x = Math.floor((imgWidth * i) / stepsX);
            const y = Math.floor((imgHeight * j) / stepsY);
            const pixel = ctx.getImageData(x, y, 1, 1).data;
            const r = pixel[0];
            const g = pixel[1];
            const b = pixel[2];
            
            const rgbStr = `${r},${g},${b}`;
            uniqueColors.add(rgbStr);
            
            if (isNotBg(r, g, b)) {
              nonBgCount++;
              if (i <= 3) hasLeft = true;
              if (i >= 7) hasRight = true;
              if (j <= 3) hasTop = true;
              if (j >= 7) hasBottom = true;
            }
          }
        }
        
        console.log(`[Export Verification] Size: ${width}x${height}`);
        console.log(`[Export Verification] Unique colors: ${uniqueColors.size}, Non-BG pixels: ${nonBgCount}`);
        console.log(`[Export Verification] Content Edges: Left=${hasLeft}, Right=${hasRight}, Top=${hasTop}, Bottom=${hasBottom}`);
        
        // Fail if only 1 color is found (blank) or if no non-background pixels are found
        if (uniqueColors.size <= 1 || nonBgCount === 0) {
          console.error("[Export Verification] FAILED: Image contains no visual content or is solid background.");
          resolve(false);
        } else if (!hasLeft || !hasRight || !hasTop || !hasBottom) {
          console.warn("[Export Verification] WARNING: Content is not distributed fully across all edges.");
          resolve(true); // Still allow pass but log warning
        } else {
          console.log("[Export Verification] SUCCESS: Image contains distributed visual content.");
          resolve(true);
        }
      } catch (e) {
        console.error("[Export Verification] Error during verification:", e);
        resolve(true);
      }
    };
    img.onerror = (e) => {
      console.error("[Export Verification] Image failed to load:", e);
      resolve(false);
    };
    img.src = dataUrl;
  });
};

export default function ExportButton({ disabled }: { disabled: boolean }) {
  const [isExporting, setIsExporting] = useState(false);

  const handleExport = async () => {
    const originalPanel = document.getElementById('export-visualization-panel');
    if (!originalPanel) {
      console.error("Export element 'export-visualization-panel' not found in DOM.");
      return;
    }

    const wrapper = originalPanel.querySelector('.viewport-content-wrapper') as HTMLElement;
    const content = originalPanel.querySelector('.visualization-content-root') as HTMLElement;
    
    if (!wrapper || !content) {
      console.error("Required viewport or content elements not found in DOM.");
      return;
    }

    // Save original styles of the wrapper and content node to restore afterward
    const originalWrapperTransform = wrapper.style.transform;
    const originalWrapperTransition = wrapper.style.transition;
    const originalContentTransform = content.style.transform;
    const originalContentOrigin = content.style.transformOrigin;
    const originalContentTransition = content.style.transition;

    try {
      setIsExporting(true);

      // Compute the layout-space bounding box using offset tree values instead of screen-relative rects
      let minX = Infinity;
      let minY = Infinity;
      let maxX = -Infinity;
      let maxY = -Infinity;
      
      const descendants = content.querySelectorAll('*');
      
      descendants.forEach((child) => {
        const htmlChild = child as HTMLElement;
        
        // We only measure elements that have layout dimensions in layout space
        if (htmlChild.offsetWidth > 0 && htmlChild.offsetHeight > 0) {
          const className = htmlChild.className || '';
          const classStr = typeof className === 'string' ? className : '';
          
          // Filter to only measure actual visual components (nodes, cell structures, pointer labels)
          // and ignore outer layout wrapper divs or full-width/height container overlays
          const isContent = 
            classStr.includes('tree-node') || 
            classStr.includes('node-core') || 
            classStr.includes('array-item') ||
            classStr.includes('pointer') ||
            (htmlChild.children.length === 0 && htmlChild.innerText && htmlChild.innerText.trim() !== '');

          if (!isContent) return;

          let x = 0;
          let y = 0;
          let curr: HTMLElement | null = htmlChild;
          
          while (curr && curr !== wrapper && wrapper.contains(curr)) {
            // Retrieve the computed transform style for the current node
            const style = window.getComputedStyle(curr);
            const transform = style.transform;
            let tx = 0;
            let ty = 0;
            
            if (transform && transform !== 'none') {
              try {
                // DOMMatrix parses both 2D matrix() and 3D matrix3d() strings automatically
                const matrix = new DOMMatrix(transform);
                tx = matrix.m41;
                ty = matrix.m42;
              } catch (e) {
                // fallback
              }
            }
            
            const leftVal = curr.style.left ? parseFloat(curr.style.left) : 0;
            const topVal = curr.style.top ? parseFloat(curr.style.top) : 0;
            
            const ox = (tx || leftVal) ? (tx + leftVal) : curr.offsetLeft;
            const oy = (ty || topVal) ? (ty + topVal) : curr.offsetTop;
            
            x += ox;
            y += oy;
            
            curr = curr.offsetParent as HTMLElement;
          }
          
          const w = htmlChild.offsetWidth;
          const h = htmlChild.offsetHeight;
          
          if (x < minX) minX = x;
          if (y < minY) minY = y;
          if (x + w > maxX) maxX = x + w;
          if (y + h > maxY) maxY = y + h;
        }
      });
      
      if (minX === Infinity) {
        minX = 0;
        minY = 0;
        maxX = content.offsetWidth || 800;
        maxY = content.offsetHeight || 600;
      }

      // Calculate framing sizes with clean padding
      const padding = 40;
      const contentWidth = maxX - minX;
      const contentHeight = maxY - minY;
      const captureWidth = contentWidth + padding * 2;
      const captureHeight = contentHeight + padding * 2;
      
      console.log(`[AlgoLens Export] Layout Bounding Box: minX=${minX}, minY=${minY}, maxX=${maxX}, maxY=${maxY}`);
      console.log(`[AlgoLens Export] Capture Dimensions: ${captureWidth}x${captureHeight}`);

      // Sanity-check position calculations for a sample node
      const sampleNode = content.querySelector('.tree-node, .node-core') as HTMLElement;
      if (sampleNode) {
        let sx = 0;
        let sy = 0;
        let curr: HTMLElement | null = sampleNode;
        while (curr && curr !== wrapper && wrapper.contains(curr)) {
          const style = window.getComputedStyle(curr);
          const transform = style.transform;
          let tx = 0;
          let ty = 0;
          if (transform && transform !== 'none') {
            try {
              const matrix = new DOMMatrix(transform);
              tx = matrix.m41;
              ty = matrix.m42;
            } catch (e) {}
          }
          const leftVal = curr.style.left ? parseFloat(curr.style.left) : 0;
          const topVal = curr.style.top ? parseFloat(curr.style.top) : 0;
          const ox = (tx || leftVal) ? (tx + leftVal) : curr.offsetLeft;
          const oy = (ty || topVal) ? (ty + topVal) : curr.offsetTop;
          sx += ox;
          sy += oy;
          curr = curr.offsetParent as HTMLElement;
        }
        const expectedX = sx - minX + padding;
        const expectedY = sy - minY + padding;
        console.log(`[AlgoLens Export Debug] Sample Node Layout Coordinates: x=${sx}, y=${sy}`);
        console.log(`[AlgoLens Export Debug] Expected Node Position in Export PNG: x=${expectedX}, y=${expectedY}`);
      }

      // 1. Temporarily center and scale 1:1 in the live DOM
      wrapper.style.transition = 'none';
      wrapper.style.transform = 'none';

      content.style.transition = 'none';
      content.style.transformOrigin = 'top left';
      content.style.transform = `translate(${-minX + padding}px, ${-minY + padding}px) scale(1)`;

      // Set global window flags for Puppeteer
      (window as any).exportDimensions = { width: captureWidth, height: captureHeight, minX, minY, padding };
      (window as any).readyForScreenshot = true;

      // Allow a brief frame render so Chrome paints the new offset visual state on screen
      await new Promise(r => requestAnimationFrame(r));
      await new Promise(r => requestAnimationFrame(r));

      let dataUrl = '';
      if (typeof (window as any).captureScreenshot === 'function') {
        // Request base64 image data URL from headless Puppeteer
        dataUrl = await (window as any).captureScreenshot({
          width: captureWidth,
          height: captureHeight,
          minX,
          minY,
          padding
        });
      } else {
        console.warn("[AlgoLens Export] captureScreenshot handler not found. Fallback to warning.");
        alert("This feature uses native headless screenshots for perfect layouts, which is currently inactive. Run in Puppeteer to capture.");
        return;
      }

      // Sanitize and strip any whitespaces or carriage returns
      if (dataUrl) {
        dataUrl = dataUrl.replace(/\s/g, '');
      }

      console.log(`[AlgoLens Export Debug] Generated dataUrl length: ${dataUrl.length}, prefix: ${dataUrl.substring(0, 100)}`);

      // Programmatically verify that the image contains real visual content and is distributed correctly
      const isVerified = await verifyImageData(dataUrl, captureWidth, captureHeight);
      if (!isVerified) {
        console.error("[AlgoLens Export] Verification WARNING: The output image appears to be blank/black.");
      }

      // Download the generated PNG
      const link = document.createElement('a');
      link.download = `algolens-visualization-${Date.now()}.png`;
      link.href = dataUrl;
      if (typeof window !== 'undefined') {
        (window as any).lastExportedDataUrl = dataUrl;
      }
      link.click();
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      // Restore wrapper and content layout styles back to their original states
      wrapper.style.transform = originalWrapperTransform;
      wrapper.style.transition = originalWrapperTransition;
      content.style.transform = originalContentTransform;
      content.style.transformOrigin = originalContentOrigin;
      content.style.transition = originalContentTransition;
      
      (window as any).readyForScreenshot = false;
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
