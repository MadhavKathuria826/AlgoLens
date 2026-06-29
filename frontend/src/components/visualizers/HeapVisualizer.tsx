import { motion, AnimatePresence } from 'framer-motion';
import { useState, useEffect } from 'react';
import GraphTreeRenderer, { GraphNode, GraphEdge } from './GraphTreeRenderer';

type HeapVisualizerProps = {
  data: { name: string; value: any[] };
  locals: any;
  currentLineCode: string;
};

export default function HeapVisualizer({ data, locals, currentLineCode }: HeapVisualizerProps) {
  useEffect(() => {
    console.log(`[HeapVisualizer] MOUNTED with key/name ${data.name}`);
    return () => console.log(`[HeapVisualizer] UNMOUNTED with key/name ${data.name}`);
  }, []);

  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const values = data.value || [];

  // Tree layout dimensions
  const treeHeight = 320;
  const arrayHeight = 140;

  // Stable ID generator for physical layout animations
  const idMapTree = new Map<any, number>();
  const idMapArray = new Map<any, number>();
  
  const getStableIdTree = (val: any) => {
     const count = idMapTree.get(val) || 0;
     idMapTree.set(val, count + 1);
     return `heap-node-${val}-${count}`;
  };

  const getStableIdArray = (val: any) => {
     const count = idMapArray.get(val) || 0;
     idMapArray.set(val, count + 1);
     return `heap-array-${val}-${count}`;
  };
  
  const HORIZONTAL_SPACING = 60;
  const VERTICAL_SPACING = 80;

  const resX: number[] = [];
  const resY: number[] = [];
  let currentX = 0;

  const traverse = (i: number, depth: number) => {
    if (i >= values.length) return;
    const left = 2 * i + 1;
    const right = 2 * i + 2;

    traverse(left, depth + 1);

    resX[i] = currentX;
    resY[i] = depth * VERTICAL_SPACING;
    currentX += HORIZONTAL_SPACING;

    traverse(right, depth + 1);
  };

  if (values.length > 0) {
    traverse(0, 0);
  }

  let minX = Infinity, maxX = -Infinity;
  let minY = Infinity, maxY = -Infinity;
  for (let i = 0; i < values.length; i++) {
    minX = Math.min(minX, resX[i]);
    maxX = Math.max(maxX, resX[i]);
    minY = Math.min(minY, resY[i]);
    maxY = Math.max(maxY, resY[i]);
  }

  const finalX: number[] = [];
  const finalY: number[] = [];
  for (let i = 0; i < values.length; i++) {
    finalX[i] = resX[i] - minX + 80;
    finalY[i] = resY[i] - minY + 80;
  }

  const layoutWidth = values.length > 0 ? maxX - minX + 160 : '100%';
  const computedTreeHeight = values.length > 0 ? maxY - minY + 160 : 320;

  // Generate IDs linearly to maintain stability
  const nodeIds = values.map(val => {
     const count = idMapTree.get(val) || 0;
     idMapTree.set(val, count + 1);
     return `heap-node-${val}-${count}`;
  });

  const arrayIds = values.map(val => {
     const count = idMapArray.get(val) || 0;
     idMapArray.set(val, count + 1);
     return `heap-array-${val}-${count}`;
  });

  const graphNodes: GraphNode[] = values.map((val, i) => {
    return {
      id: nodeIds[i],
      x: finalX[i],
      y: finalY[i],
      val: val,
      isHovered: hoveredIndex === i,
      onMouseEnter: () => setHoveredIndex(i),
      onMouseLeave: () => setHoveredIndex(null),
      tooltipComponent: hoveredIndex === i ? (
         <div className="absolute bottom-full mb-3 bg-black/90 border border-white/20 text-white text-[10px] whitespace-nowrap p-2 rounded shadow-xl pointer-events-none flex flex-col gap-1">
            <div><span className="text-slate-400">Index:</span> {i}</div>
            {i > 0 && <div><span className="text-slate-400">Parent:</span> {Math.floor((i - 1) / 2)}</div>}
            {2*i + 1 < values.length && <div><span className="text-slate-400">Left:</span> {2*i + 1}</div>}
            {2*i + 2 < values.length && <div><span className="text-slate-400">Right:</span> {2*i + 2}</div>}
         </div>
      ) : undefined
    };
  });

  const graphEdges: GraphEdge[] = [];
  values.forEach((_, i) => {
    const left = 2 * i + 1;
    const right = 2 * i + 2;
    if (left < values.length) {
      graphEdges.push({
        id: `heap-edge-${i}-${left}`,
        sourceId: nodeIds[i],
        targetId: nodeIds[left]
      });
    }
    if (right < values.length) {
      graphEdges.push({
        id: `heap-edge-${i}-${right}`,
        sourceId: nodeIds[i],
        targetId: nodeIds[right]
      });
    }
  });

  return (
    <div className="w-full h-full flex flex-col items-center justify-between p-8 bg-slate-900/50 rounded-xl border border-slate-700/50 overflow-y-auto custom-scrollbar">
      
      {/* Top View: Tree Representation */}
      <div className="relative w-full flex-1 flex justify-center items-center overflow-visible" style={{ minHeight: treeHeight }}>
        <div className="absolute top-0 left-0 bg-emerald-500/20 border border-emerald-500/50 text-emerald-400 text-xs px-2 py-1 rounded shadow-[0_0_10px_rgba(16,185,129,0.3)] font-bold tracking-wider uppercase z-20">
          MIN HEAP
        </div>

        <GraphTreeRenderer
          nodes={graphNodes}
          edges={graphEdges}
          pointers={[]}
          activeFlows={[]}
          layoutWidth={layoutWidth}
          layoutHeight={computedTreeHeight}
        />
      </div>

      {/* Bottom View: Array Representation */}
      <div className="w-full flex flex-col items-center justify-end mt-4 pt-8 border-t border-slate-700/50" style={{ minHeight: arrayHeight }}>
        <div className="flex flex-wrap justify-center gap-2 relative w-full">
          <AnimatePresence>
            {values.map((val, i) => {
              const isHovered = hoveredIndex === i;
              
              return (
                <div key={`cell-wrap-${i}`} className="flex flex-col items-center gap-2">
                  <span className={`text-[10px] font-mono transition-colors ${isHovered ? 'text-sky-400 font-bold' : 'text-slate-500'}`}>
                    {i}
                  </span>
                  <motion.div
                    layoutId={arrayIds[i]}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0, scale: isHovered ? 1.1 : 1 }}
                    exit={{ opacity: 0, scale: 0.8 }}
                    transition={{ duration: 0.4, type: "spring", stiffness: 300, damping: 20 }}
                    className={`w-12 h-12 flex items-center justify-center border rounded-md font-mono text-lg font-medium cursor-pointer transition-colors duration-300 ${
                      isHovered
                        ? 'bg-sky-500/20 border-sky-400 text-sky-300 shadow-[0_0_15px_rgba(56,189,248,0.5)]'
                        : 'bg-slate-800/80 border-slate-600/80 text-slate-300'
                    }`}
                    onMouseEnter={() => setHoveredIndex(i)}
                    onMouseLeave={() => setHoveredIndex(null)}
                  >
                    {String(val)}
                  </motion.div>
                </div>
              );
            })}
          </AnimatePresence>
        </div>
        <div className="mt-6 text-[10px] font-mono text-slate-500 flex gap-6 bg-black/30 px-4 py-2 rounded-lg border border-white/5">
           <span><span className="text-emerald-400">parent</span> = (i - 1) // 2</span>
           <span><span className="text-sky-400">left</span> = 2*i + 1</span>
           <span><span className="text-purple-400">right</span> = 2*i + 2</span>
        </div>
      </div>
      
    </div>
  );
}
