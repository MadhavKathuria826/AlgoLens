import { motion, AnimatePresence } from 'framer-motion';
import { useMemo } from 'react';

export default function SinglyLinkedListVisualizer({ heap, locals }: { heap: any, locals: any }) {
  const isNullPtr = (val: any) => !val || val === 'None' || val === '0x0000' || val === 'nullptr' || val === 'NULL';

  // 1. Detect and extract lists from the heap
  const { lists, pointersByNode, pointerLanes, isDoublyLinked } = useMemo(() => {
    if (!heap) return { lists: [], pointersByNode: {}, pointerLanes: [], isDoublyLinked: false };

    const nodes = Object.keys(heap).filter(k => heap[k].fields && 'next' in heap[k].fields);
    if (nodes.length === 0) return { lists: [], pointersByNode: {}, pointerLanes: [], isDoublyLinked: false };

    const indegree: Record<string, number> = {};
    nodes.forEach(n => indegree[n] = 0);

    nodes.forEach(n => {
      const next = heap[n].fields.next;
      if (!isNullPtr(next) && indegree[next] !== undefined) {
        indegree[next]++;
      }
    });

    let heads = nodes.filter(n => indegree[n] === 0);
    if (heads.length === 0 && nodes.length > 0) {
      heads = [nodes[0]];
    }

    const lists: { nodes: string[], isPerfectCircle: boolean, cycleTarget: string | null }[] = [];
    const globalVisited = new Set<string>();

    heads.forEach(h => {
      if (globalVisited.has(h)) return;
      const list: string[] = [];
      let curr = h;
      while (!isNullPtr(curr) && !globalVisited.has(curr)) {
        list.push(curr);
        globalVisited.add(curr);
        curr = heap[curr]?.fields?.next;
      }
      
      const cycleTarget = !isNullPtr(curr) ? curr : null;
      const isPerfectCircle = list.length > 1 && cycleTarget === h;
      
      lists.push({ nodes: list, isPerfectCircle, cycleTarget });
    });

    // 2. Extract pointers from locals
    const pointersByNode: Record<string, string[]> = {};
    const allActivePointers = new Set<string>();
    if (locals) {
      for (const [k, v] of Object.entries(locals)) {
        if (typeof v === 'string' && heap[v]) {
          if (!pointersByNode[v]) pointersByNode[v] = [];
          pointersByNode[v].push(k);
          allActivePointers.add(k);
        }
      }
    }

    // Sort pointers alphabetically for stable rendering
    for (const id in pointersByNode) {
      pointersByNode[id].sort();
    }
    
    const pointerLanes = Array.from(allActivePointers).sort();

    const isDoublyLinked = nodes.some(k => {
      const prev = heap[k].fields?.prev;
      return !isNullPtr(prev);
    });

    return { lists, pointersByNode, pointerLanes, isDoublyLinked };
  }, [heap, locals]);

  if (lists.length === 0) return null;

  return (
    <div className="flex flex-col items-center gap-16 my-8 w-full overflow-hidden">
      {lists.map(({ nodes: list, isPerfectCircle, cycleTarget }, listIdx) => {
        const targetIdx = cycleTarget ? list.indexOf(cycleTarget) : -1;
        const isCyclic = targetIdx !== -1;
        const cycleLength = isCyclic ? list.length - targetIdx : 0;
        
        const radius = isCyclic ? Math.max(120, cycleLength * 35) : 0;
        const prefixSpacing = 150;
        const startX = 80;
        
        const actualCx = isPerfectCircle ? radius + 100 : startX + targetIdx * prefixSpacing + radius;
        const cy = isCyclic ? radius + 100 : 0;
        
        const containerWidth = isCyclic ? actualCx + radius + 100 : '100%';
        const containerHeight = isCyclic ? 2 * radius + 200 : 'auto';

        return (
        <div key={`list-${listIdx}`} className="flex flex-col items-center gap-2 relative">
          <div className="text-emerald-400 font-mono text-xl tracking-wider uppercase mb-16 font-semibold drop-shadow-md">
            {isPerfectCircle ? 'Circular Linked List' : (isCyclic ? 'Cyclic Linked List' : 'Linked List')} {lists.length > 1 ? listIdx + 1 : ''}
          </div>
          
          <div className={isCyclic ? "relative" : "flex items-center gap-0"} style={isCyclic ? { width: containerWidth, height: containerHeight } : {}}>
            
            {/* SVG Tracks for Cycles */}
            {isCyclic && (() => {
                const getCoord = (idx: number) => {
                   if (idx < targetIdx) {
                      return { x: startX + idx * prefixSpacing, y: cy };
                   } else {
                      const j = idx - targetIdx;
                      const startAngle = isPerfectCircle ? -Math.PI / 2 : Math.PI;
                      const angle = startAngle + (j / cycleLength) * 2 * Math.PI;
                      return { x: actualCx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
                   }
                };

                return (
                  <svg className="absolute inset-0 w-full h-full pointer-events-none z-0 overflow-visible">
                    <defs>
                  <marker id="arrow-marker" markerWidth="20" markerHeight="20" refX="16" refY="10" orient="auto" markerUnits="userSpaceOnUse">
                    <polygon points="4,4 16,10 4,16" className="fill-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.5)]" />
                  </marker>
                </defs>

                    {/* Prefix Edges */}
                    {!isPerfectCircle && Array.from({ length: targetIdx }).map((_, j) => {
                       const A = getCoord(j);
                       const B = getCoord(j + 1);
                       return (
                         <g key={`arrow-prefix-${j}`}>
                            {/* Next Edge */}
                            <line x1={A.x + 45} y1={A.y - (isDoublyLinked ? 6 : 0)} x2={B.x - 50} y2={B.y - (isDoublyLinked ? 6 : 0)} className="stroke-emerald-400 drop-shadow-[0_0_10px_rgba(52,211,153,0.5)]" strokeWidth="4" markerEnd="url(#arrow-marker)" />
                            
                            {/* Prev Edge */}
                            {isDoublyLinked && (
                                <line x1={B.x - 45} y1={B.y + 6} x2={A.x + 50} y2={A.y + 6} className="stroke-emerald-400 drop-shadow-[0_0_10px_rgba(52,211,153,0.5)]" strokeWidth="4" markerEnd="url(#arrow-marker)" />
                            )}
                         </g>
                       );
                    })}

                    {/* Cycle Edges */}
                    {Array.from({ length: cycleLength }).map((_, j) => {
                       const idxA = targetIdx + j;
                       const idxB = targetIdx + (j + 1) % cycleLength;
                       const startAngle = isPerfectCircle ? -Math.PI / 2 : Math.PI;
                       const angleA = startAngle + (j / cycleLength) * 2 * Math.PI;
                       const angleB = startAngle + ((j + 1) / cycleLength) * 2 * Math.PI;
                       
                       // Calculate max angular offset to prevent crossing paths
                       const maxOffset = (angleB - angleA) / 2 - 0.05;
                       
                       // Next Pointer Arc
                       const R_next = radius + (isDoublyLinked ? 15 : 0);
                       const offsetN = Math.min(48 / R_next, maxOffset);
                       const startN = angleA + offsetN;
                       const endN = angleB - offsetN;
                       const x1N = actualCx + R_next * Math.cos(startN);
                       const y1N = cy + R_next * Math.sin(startN);
                       const x2N = actualCx + R_next * Math.cos(endN);
                       const y2N = cy + R_next * Math.sin(endN);
                       
                       // Prev Pointer Arc
                       const R_prev = radius - (isDoublyLinked ? 15 : 0);
                       const offsetP = Math.min(48 / R_prev, maxOffset);
                       const startP = angleB - offsetP;
                       const endP = angleA + offsetP;
                       const x1P = actualCx + R_prev * Math.cos(startP);
                       const y1P = cy + R_prev * Math.sin(startP);
                       const x2P = actualCx + R_prev * Math.cos(endP);
                       const y2P = cy + R_prev * Math.sin(endP);
                       
                       return (
                         <g key={`arrow-cycle-${j}`}>
                            <path d={`M ${x1N} ${y1N} A ${R_next} ${R_next} 0 0 1 ${x2N} ${y2N}`} fill="none" className="stroke-emerald-400 drop-shadow-[0_0_10px_rgba(52,211,153,0.5)]" strokeWidth="4" markerEnd="url(#arrow-marker)" />
                            
                            {isDoublyLinked && (
                                <path d={`M ${x1P} ${y1P} A ${R_prev} ${R_prev} 0 0 0 ${x2P} ${y2P}`} fill="none" className="stroke-emerald-400 drop-shadow-[0_0_10px_rgba(52,211,153,0.5)]" strokeWidth="4" markerEnd="url(#arrow-marker)" />
                            )}
                         </g>
                       );
                    })}
                  </svg>
                );
            })()}

            {list.map((nodeId, idx) => {
              const node = heap[nodeId];
              const val = node.fields.val;
              const hasNext = isCyclic ? true : (idx < list.length - 1 || (node.fields.next !== 'None' && node.fields.next !== null));
              const pointers = pointersByNode[nodeId] || [];

              // Calculate absolute positioning for Circular Layout
              let x = 0, y = 0;
              if (isCyclic) {
                 if (idx < targetIdx) {
                    x = startX + idx * prefixSpacing;
                    y = cy;
                 } else {
                    const j = idx - targetIdx;
                    const startAngle = isPerfectCircle ? -Math.PI / 2 : Math.PI;
                    const angle = startAngle + (j / cycleLength) * 2 * Math.PI;
                    x = actualCx + radius * Math.cos(angle);
                    y = cy + radius * Math.sin(angle);
                 }
              }

              return (
                <div 
                  key={`wrap-${nodeId}`}
                  className={isCyclic ? "absolute z-10" : "flex items-center"}
                  style={isCyclic ? { left: x, top: y, width: 0, height: 0 } : {}}
                >
                  {/* Pure CSS exact centering wrapper to shield from Framer Motion transform overrides */}
                  <div className={isCyclic ? "absolute flex items-center justify-center w-0 h-0" : ""}>
                    <motion.div 
                      layout
                      className={isCyclic ? "flex items-center w-max" : "flex items-center"}
                    >
                      
                      {/* Left NULL for first node (DLL) */}
                      {idx === 0 && isDoublyLinked && node.fields.prev === 'None' && (
                        <div className={isCyclic ? "absolute right-full mr-2" : "flex items-center"}>
                          <div className="text-[10px] text-slate-400 font-mono px-2 mr-1">NULL</div>
                          <div className="w-8 relative h-[52px]">
                            <div className="absolute w-full h-1 bg-slate-400 top-[32px] -translate-y-1/2"></div>
                            <div className="absolute left-0 w-4 h-4 border-b-[4px] border-l-[4px] border-slate-400 rotate-45 top-[32px] -translate-y-1/2 -translate-x-[2px]"></div>
                          </div>
                        </div>
                      )}

                      {/* Node and Pointers Wrapper */}
                      <div className="relative flex flex-col items-center">
                    
                    {/* Pointers Container (Floating above the node) */}
                    <div className="absolute bottom-full mb-3 left-1/2 -translate-x-1/2 flex flex-col items-center z-20">
                    <div className="flex flex-col-reverse items-center gap-1.5 mb-1.5">
                      {pointers.map(ptr => (
                        <motion.div
                          key={ptr}
                          layoutId={`ptr-badge-${ptr}`}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ type: "spring", stiffness: 400, damping: 30 }}
                          className="text-blue-300 bg-blue-900/40 px-2.5 py-1 rounded-md border border-blue-500/30 shadow-[0_0_12px_rgba(59,130,246,0.25)] font-mono text-xs font-semibold whitespace-nowrap"
                        >
                          {ptr}
                        </motion.div>
                      ))}
                    </div>
                    <AnimatePresence>
                      {pointers.length > 0 && (
                        <motion.div
                          layout
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          className="text-blue-400 text-sm leading-none drop-shadow-md"
                        >
                          ▼
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>

                  {/* Node Block */}
                  <div className="relative flex items-center justify-center">
                    <div className="absolute inset-0" style={{ transform: "translate(-50%, -50%)" }}></div>
                    <motion.div 
                      layout
                      layoutId={`node-block-${nodeId}`}
                      className="flex items-center"
                    >
                      <div className="flex bg-slate-800 border-2 border-emerald-500/50 rounded-md overflow-hidden shadow-[0_0_15px_rgba(16,185,129,0.15)] z-10 h-[52px]">
                        {/* Prev Pointer Segment */}
                        {isDoublyLinked && (
                          <div className="px-2 bg-slate-900 border-r border-emerald-500/30 flex items-center justify-center">
                            <div className="w-2 h-2 rounded-full bg-emerald-400/80 translate-y-[6px]"></div>
                          </div>
                        )}
                        {/* Value Segment */}
                        <div className="px-4 flex items-center justify-center min-w-[3rem] border-r border-emerald-500/30">
                          <span className="text-white font-mono text-xl">{val !== undefined ? String(val) : ''}</span>
                        </div>
                        {/* Next Pointer Segment */}
                        <div className="px-2 bg-slate-900 flex items-center justify-center">
                          <div className={`w-2 h-2 rounded-full bg-emerald-400/80 ${isDoublyLinked ? '-translate-y-[6px]' : ''}`}></div>
                        </div>
                      </div>
                    </motion.div>
                  </div>
                  </div>
                  </motion.div>
                  </div>
                  {/* Inline Arrow (Only for Linear Layout) */}
                  {!isCyclic && hasNext && (() => {
                     const nextNodeId = node.fields.next;
                     const nextNode = heap[nextNodeId];
                     return (
                       <div className={`w-16 relative ${isDoublyLinked ? 'h-[52px]' : 'flex items-center'}`}>
                          {/* Next Arrow (A -> B) */}
                          <div className={`absolute w-full h-1 bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.5)] ${isDoublyLinked ? 'top-[20px] -translate-y-1/2' : 'top-1/2 -translate-y-1/2'}`}></div>
                          <div className={`absolute right-0 w-4 h-4 border-t-[4px] border-r-[4px] border-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.5)] rotate-45 ${isDoublyLinked ? 'top-[20px] -translate-y-1/2' : 'top-1/2 -translate-y-1/2'} translate-x-[2px]`}></div>
                          
                          {/* Prev Arrow (B -> A) */}
                          {isDoublyLinked && nextNode && (
                            nextNode.fields.prev === nodeId ? (
                              <>
                                <div className="absolute w-full h-1 bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.5)] top-[32px] -translate-y-1/2"></div>
                                <div className="absolute left-0 w-4 h-4 border-b-[4px] border-l-[4px] border-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.5)] rotate-45 top-[32px] -translate-y-1/2 -translate-x-[2px]"></div>
                              </>
                            ) : nextNode.fields.prev === 'None' ? (
                              <>
                                <div className="absolute right-0 w-6 h-1 bg-slate-400 top-[32px] -translate-y-1/2"></div>
                                <div className="absolute right-6 w-4 h-4 border-b-[4px] border-l-[4px] border-slate-400 rotate-45 top-[32px] -translate-y-1/2 -translate-x-[2px]"></div>
                                <div className="absolute right-12 text-[10px] text-slate-400 font-mono top-[32px] -translate-y-1/2">NULL</div>
                              </>
                            ) : null
                          )}
                       </div>
                     );
                  })()}

                  {/* NULL Terminator */}
                  {!isCyclic && !hasNext && (
                     <>
                       <div className={`w-12 relative ${isDoublyLinked ? 'h-[52px]' : 'flex items-center'}`}>
                          <div className={`absolute w-full h-1 bg-slate-400 ${isDoublyLinked ? 'top-[20px] -translate-y-1/2' : 'top-1/2 -translate-y-1/2'}`}></div>
                          <div className={`absolute right-0 w-4 h-4 border-t-[4px] border-r-[4px] border-slate-400 rotate-45 ${isDoublyLinked ? 'top-[20px] -translate-y-1/2' : 'top-1/2 -translate-y-1/2'} translate-x-[2px]`}></div>
                       </div>
                       <motion.div 
                         initial={{ opacity: 0 }}
                         animate={{ opacity: 1 }}
                         className="flex items-center justify-center px-3 py-2 bg-slate-900/50 border-2 border-dashed border-slate-600/50 rounded-md text-slate-400 font-mono text-sm tracking-wider"
                       >
                         NULL
                       </motion.div>
                     </>
                  )}
                </div>
              );
            })}
          </div>
        </div>
        );
      })}
    </div>
  );
}
