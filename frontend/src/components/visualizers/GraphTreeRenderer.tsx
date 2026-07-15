import { motion, AnimatePresence } from 'framer-motion';
import React, { useMemo, useEffect } from 'react';

export type GraphNode = {
  id: string;
  x: number | string;
  y: number | string;
  val: any;
  isLanded?: boolean;
  isCurrentTarget?: boolean;
  isActivePath?: boolean;
  isVisited?: boolean;
  isHovered?: boolean;
  tooltipComponent?: React.ReactNode;
  onMouseEnter?: () => void;
  onMouseLeave?: () => void;
  balanceFactor?: number;
  isNew?: boolean;
  isUnbalanced?: boolean;
  isRotationPivot?: boolean;
};

export type GraphEdge = {
  id: string;
  sourceId: string;
  targetId: string;
  isActivePath?: boolean;
  isVisited?: boolean;
};

export type GraphPointer = {
  name: string;
  targetId: string;
};

export type GraphFlow = {
  id: string;
  sourceId: string;
  targetId: string;
};

export type GraphTreeRendererProps = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  pointers: GraphPointer[];
  activeFlows: GraphFlow[];
  layoutWidth: number | string;
  layoutHeight: number | string;
};

export default function GraphTreeRenderer({
  nodes,
  edges,
  pointers,
  activeFlows,
  layoutWidth,
  layoutHeight
}: GraphTreeRendererProps) {
  
  const nodeMap = useMemo(() => {
    const map = new Map<string, GraphNode>();
    for (const n of nodes) map.set(n.id, n);
    return map;
  }, [nodes]);
  const prevCoords = React.useRef<Record<string, {x: any, y: any}>>({});
  const hasMovedMap = useMemo(() => {
    const map = new Map<string, boolean>();
    nodes.forEach(node => {
      const prev = prevCoords.current[node.id];
      const hasMoved = !prev || prev.x !== node.x || prev.y !== node.y;
      map.set(node.id, hasMoved);
      if (hasMoved) {
         console.log(`[GraphTreeRenderer] MOVED ${node.id}: x(${prev?.x} -> ${node.x}), y(${prev?.y} -> ${node.y})`);
      }
    });
    return map;
  }, [nodes]);

  useEffect(() => {
    nodes.forEach(node => {
      prevCoords.current[node.id] = { x: node.x, y: node.y };
    });
  }, [nodes]);

  useEffect(() => {
    console.log('[GraphTreeRenderer] MOUNTED');
    return () => console.log('[GraphTreeRenderer] UNMOUNTED');
  }, []);

  console.log(`[GraphTreeRenderer] RENDER: nodes=${nodes.length}, layoutWidth=${layoutWidth}, layoutHeight=${layoutHeight}`);

  // Pointers mapping per node
  const nodePointers = useMemo(() => {
    const map: Record<string, string[]> = {};
    for (const p of pointers) {
      if (!map[p.targetId]) map[p.targetId] = [];
      map[p.targetId].push(p.name);
    }
    for (const p of Object.values(map)) p.sort();
    return map;
  }, [pointers]);

  return (
    <div className="relative w-full h-full flex justify-center items-center overflow-visible" style={{ minHeight: layoutHeight, minWidth: layoutWidth }}>
      
      {/* Edges Layer */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 0 }}>
        {edges.map(edge => {
          const src = nodeMap.get(edge.sourceId);
          const dst = nodeMap.get(edge.targetId);
          if (!src || !dst) return null;

          return (
            <motion.line
              key={edge.id}
              initial={{
                x1: src.x, y1: src.y,
                x2: src.x, y2: src.y,
                stroke: '#475569',
                strokeWidth: 2,
                strokeOpacity: 0
              }}
              animate={{
                x1: src.x, y1: src.y,
                x2: dst.x, y2: dst.y,
                stroke: edge.isActivePath ? '#38bdf8' : (edge.isVisited ? '#4338ca' : '#475569'),
                strokeWidth: edge.isActivePath ? 3 : 2,
                strokeOpacity: edge.isActivePath ? 1 : (edge.isVisited ? 0.4 : 1)
              }}
              transition={{ duration: 0.4, type: "spring", stiffness: 300, damping: 20 }}
            />
          );
        })}

        {/* Active Flow Animations */}
        <AnimatePresence>
          {activeFlows.map(flow => {
            const src = nodeMap.get(flow.sourceId);
            const dst = nodeMap.get(flow.targetId);
            if (!src || !dst) return null;
            return (
              <motion.circle
                key={flow.id}
                r="6"
                fill="#22d3ee"
                initial={{ cx: src.x, cy: src.y, opacity: 1 }}
                animate={{ cx: dst.x, cy: dst.y, opacity: 0 }}
                transition={{ duration: 0.6, ease: "easeOut" }}
              />
            );
          })}
        </AnimatePresence>
      </svg>

      {/* Nodes Layer */}
      <div className="absolute inset-0 w-full h-full pointer-events-none">
        <AnimatePresence>
          {nodes.map(node => {
            let bgClass = 'bg-slate-800 border-slate-500 text-slate-300';
            if (node.isNew) {
              bgClass = 'bg-emerald-600 border-emerald-400 text-white shadow-[0_0_15px_rgba(52,211,153,0.6)]';
            } else if (node.isUnbalanced) {
              bgClass = 'bg-rose-600 border-rose-400 text-white shadow-[0_0_15px_rgba(244,63,94,0.6)]';
            } else if (node.isRotationPivot) {
              bgClass = 'bg-amber-600 border-amber-400 text-white shadow-[0_0_15px_rgba(251,191,36,0.6)]';
            } else if (node.isHovered) {
              bgClass = 'bg-sky-600 border-sky-400 text-white shadow-[0_0_15px_rgba(56,189,248,0.5)]';
            } else if (node.isActivePath) {
              bgClass = 'bg-sky-600 border-sky-400 text-white shadow-[0_0_15px_rgba(56,189,248,0.5)]';
            } else if (node.isVisited) {
              bgClass = 'bg-indigo-950/60 border-indigo-900 text-indigo-400/80';
            }

            const isStringPos = typeof node.x === 'string';
            const positionProps = isStringPos 
              ? { left: node.x, top: node.y, x: '-50%', y: '-50%' }
              : { x: (node.x as number) - 24, y: (node.y as number) - 24 };

            const hasMoved = hasMovedMap.get(node.id) ?? true;

            return (
              <motion.div
                key={node.id}
                initial={{ opacity: 0, scale: 0, ...positionProps }}
                animate={{ 
                  opacity: 1, 
                  ...positionProps,
                  scale: node.isLanded ? [1.3, node.isHovered ? 1.2 : 1] : (node.isHovered ? 1.2 : 1),
                  boxShadow: node.isLanded ? ['0 0 25px rgba(34,211,238,0.8)', '0 0 0px rgba(34,211,238,0)'] : 
                             node.isCurrentTarget ? '0 0 15px rgba(56,189,248,0.6)' : 'none',
                  zIndex: node.isHovered ? 50 : 10
                }}
                exit={{ opacity: 0, scale: 0 }}
                transition={hasMoved ? { duration: 0.4, type: "spring", stiffness: 300, damping: 20 } : { duration: 0 }}
                className={`absolute w-12 h-12 rounded-full flex items-center justify-center font-mono font-bold border-2 pointer-events-auto cursor-pointer transition-colors duration-500 ${bgClass}`}
                onMouseEnter={node.onMouseEnter}
                onMouseLeave={node.onMouseLeave}
              >
                {node.val !== undefined ? String(node.val) : ''}
                {node.balanceFactor !== undefined && (
                  <span className="absolute -top-3 -right-3 text-[9px] bg-slate-800 text-cyan-400 px-1.5 py-0.5 rounded-full border border-cyan-500/50 font-sans font-extrabold shadow-[0_0_8px_rgba(34,211,238,0.3)]">
                    BF:{node.balanceFactor}
                  </span>
                )}
                {node.tooltipComponent}
              </motion.div>
            );
          })}
        </AnimatePresence>

        {/* Pointers Layer */}
        <AnimatePresence>
          {pointers.map((pointer) => {
            const targetNode = nodeMap.get(pointer.targetId);
            if (!targetNode) return null;

            const pointersOnThisNode = nodePointers[pointer.targetId] || [];
            const pointerIndex = pointersOnThisNode.indexOf(pointer.name);

            const isStringPos = typeof targetNode.x === 'string';
            const positionProps = isStringPos 
              ? { left: targetNode.x, top: targetNode.y, x: '-50%', y: '-100%' }
              : { x: targetNode.x as number, y: targetNode.y as number };

            return (
              <motion.div
                key={`ptr-${pointer.name}`}
                initial={{ opacity: 0, scale: 0.5, ...positionProps }}
                animate={{
                  opacity: 1,
                  scale: 1,
                  ...positionProps
                }}
                exit={{ opacity: 0, scale: 0.5 }}
                transition={{ duration: 0.4, ease: "circOut" }}
                className="absolute flex justify-center items-end pointer-events-none z-20"
                style={isStringPos 
                  ? { width: 100, height: 100 } 
                  : { width: 100, height: 100, marginLeft: -50, marginTop: -100 }}
              >
                <div
                  style={{ marginBottom: 32 + pointerIndex * 22 }}
                  className="text-cyan-100 bg-cyan-950/80 px-2 py-0.5 rounded text-[11px] uppercase tracking-wider font-bold border border-cyan-500/50 shadow-[0_0_12px_rgba(34,211,238,0.4)]"
                >
                  {pointer.name}
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}
