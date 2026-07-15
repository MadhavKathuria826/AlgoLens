import { motion, AnimatePresence } from 'framer-motion';
import { useRef, useEffect } from 'react';

export default function ArrayVisualizer({ data, locals, isCurrentlyIterated, isDimmed, currentLineCode, visualType }: { data: any, locals: any, isCurrentlyIterated?: boolean, isDimmed?: boolean, currentLineCode?: string, visualType?: string }) {
  const prevLocalsRef = useRef<any>({});
  
  useEffect(() => {
    prevLocalsRef.current = locals || {};
  }, [locals]);

  const prevLocals = prevLocalsRef.current;

  type PointerIdentity = { confidence: number; isIterator: boolean; };
  const semanticMemoryRef = useRef<Record<string, PointerIdentity>>({});

  useEffect(() => {
    if (locals) {
       for (const k of Object.keys(semanticMemoryRef.current)) {
          if (locals[k] === undefined) {
             delete semanticMemoryRef.current[k];
          }
       }
    }
  }, [locals]);

  const memory = semanticMemoryRef.current;

  const isMatrix = Array.isArray(data.value) && data.value.length > 0 && Array.isArray(data.value[0]);

  const containerRef = useRef<HTMLDivElement>(null);

  const prevArrayRef = useRef<any[]>([]);
  const trackedItemsRef = useRef<{id: string, value: any}[]>([]);

  let newArray = data.value || [];
  let trackedItems = trackedItemsRef.current;

  let arrayChanged = false;
  if (newArray.length !== prevArrayRef.current.length) {
     arrayChanged = true;
  } else {
     for (let i = 0; i < newArray.length; i++) {
        if (JSON.stringify(newArray[i]) !== JSON.stringify(prevArrayRef.current[i])) {
           arrayChanged = true;
           break;
        }
     }
  }

  if (arrayChanged) {
     if (newArray.length !== prevArrayRef.current.length) {
        trackedItems = newArray.map((val: any) => ({ id: `id-${Math.random()}`, value: val }));
     } else {
        const nextTracked = [...trackedItems];
        const mismatchedIndices = [];
        for (let i = 0; i < newArray.length; i++) {
          if (JSON.stringify(newArray[i]) !== JSON.stringify(prevArrayRef.current[i])) {
             mismatchedIndices.push(i);
          }
        }
        
        const unmatchedNew = mismatchedIndices.map(i => ({ val: newArray[i], idx: i }));
        const unmatchedOld = mismatchedIndices.map(i => ({ ...nextTracked[i], oldIdx: i }));
        
        for (const newItem of unmatchedNew) {
           const matchIndex = unmatchedOld.findIndex(old => JSON.stringify(old.value) === JSON.stringify(newItem.val));
           if (matchIndex !== -1) {
              const matchedOld = unmatchedOld[matchIndex];
              nextTracked[newItem.idx] = { id: matchedOld.id, value: newItem.val };
              unmatchedOld.splice(matchIndex, 1);
           } else {
              nextTracked[newItem.idx] = { id: `id-${Math.random()}`, value: newItem.val };
           }
        }
        trackedItems = nextTracked;
     }
     
     prevArrayRef.current = [...newArray];
     trackedItemsRef.current = trackedItems;
  }

  // 1. Initial Semantic Memory Scoring
  if (locals) {
    for (const k of Object.keys(locals)) {
      if (!memory[k]) {
        let score = 0;
        const lowerK = k.toLowerCase();
        // Temporary naming heuristic fallback
        if (['i', 'j', 'k', 'left', 'right', 'mid', 'idx', 'index', 'ptr'].some(ig => lowerK.includes(ig))) {
            score += 10;
        }
        // Known values/accumulators penalty
        if (['n', 'm', 'length', 'size', 'len', 'total', 'sum', 'count', 'result', 'res', 'ans', 'temp', 'aux', 'target', 'val', 'value', 'item', 'element', 'key', 'max_val', 'min_val', 'maxval', 'minval'].includes(lowerK)) {
            score -= 50;
        }
        memory[k] = { confidence: score, isIterator: score >= 10 };
      }
    }
  }

  // 2. Discover Iterator Identity from Expressions
  if (currentLineCode) {
    const regex = new RegExp(`${data.name}\\[([^\\]]+)\\]`, 'g');
    let match;
    while ((match = regex.exec(currentLineCode)) !== null) {
      const expr = match[1].trim();
      const words = Array.from(new Set(expr.match(/[a-zA-Z_]\w*/g) || []));
      for (const word of words) {
        if (memory[word] && memory[word].confidence < 100) {
          memory[word].confidence += 50;
          if (memory[word].confidence >= 10) {
             memory[word].isIterator = true;
          }
        }
      }
    }
    
    if (isMatrix) {
       const matrixRegex = new RegExp(`${data.name}\\[([^\\]]+)\\]\\[([^\\]]+)\\]`, 'g');
       let mMatch;
       while ((mMatch = matrixRegex.exec(currentLineCode)) !== null) {
          const words = Array.from(new Set([...(mMatch[1].match(/[a-zA-Z_]\w*/g) || []), ...(mMatch[2].match(/[a-zA-Z_]\w*/g) || [])]));
          for (const word of words) {
            if (memory[word] && memory[word].confidence < 100) {
              memory[word].confidence += 50;
              if (memory[word].confidence >= 10) {
                 memory[word].isIterator = true;
              }
            }
          }
       }
    }
  }

  // Map of index -> array of pointer names
  const pointers: Record<string | number, string[]> = {};
  const accumulators: { name: string; value: string; changed: boolean }[] = [];
  const accessedIndices = new Set<string | number>();

  // 3. Pointer Extraction (Execution State as Source of Truth)
  if (locals) {
    for (const [k, v] of Object.entries(locals)) {
      if ((typeof v === 'string' && !v.startsWith('<')) || typeof v === 'number') {
        const numVal = typeof v === 'number' ? v : parseInt(v as string, 10);
        if (!isNaN(numVal)) {
          if (memory[k]?.isIterator) {
            if (isMatrix) {
              let foundInMatrix = false;
              for (let r = 0; r < data.value.length; r++) {
                for (let c = 0; c < data.value[r].length; c++) {
                  if (parseInt(data.value[r][c], 10) === numVal) {
                    const key = `${r}-${c}`;
                    if (!pointers[key]) pointers[key] = [];
                    pointers[key].push(k);
                    foundInMatrix = true;
                  }
                }
              }
              if (!foundInMatrix) {
                 accumulators.push({
                   name: k,
                   value: String(v),
                   changed: prevLocals[k] !== undefined && prevLocals[k] !== v
                 });
              }
            } else {
              if (numVal >= 0 && numVal < data.value.length) {
                if (!pointers[numVal]) pointers[numVal] = [];
                pointers[numVal].push(k);
              } else {
                accumulators.push({
                  name: k,
                  value: String(v),
                  changed: prevLocals[k] !== undefined && prevLocals[k] !== v
                });
              }
            }
          } else {
            accumulators.push({
              name: k,
              value: String(v),
              changed: prevLocals[k] !== undefined && prevLocals[k] !== v
            });
          }
        }
      }
    }
  }

  // Parse currentLineCode for explicit array access like arr[j + 1]
  if (currentLineCode) {
    const regex = new RegExp(`${data.name}\\[([^\\]]+)\\]`, 'g');
    let match;
    while ((match = regex.exec(currentLineCode)) !== null) {
      const expr = match[1].trim();
      let parsedExpr = expr;
      
      parsedExpr = parsedExpr.replace(/len\([^)]+\)/g, data.value.length.toString());
      
      if (locals) {
        for (const [k, v] of Object.entries(locals)) {
          if ((typeof v === 'string' && !v.startsWith('<')) || typeof v === 'number') {
             const numVal = typeof v === 'number' ? v : parseInt(v as string, 10);
             if (!isNaN(numVal)) {
                const varRegex = new RegExp(`\\b${k}\\b`, 'g');
                parsedExpr = parsedExpr.replace(varRegex, String(v));
             }
          }
        }
      }
      
      try {
        if (/^[0-9\s\+\-\*\/\(\)]+$/.test(parsedExpr)) {
          const result = Math.floor(new Function(`return ${parsedExpr}`)());
          if (!isNaN(result) && result >= 0 && result < data.value.length) {
            if (!pointers[result]) pointers[result] = [];
            pointers[result].push(expr);
            accessedIndices.add(result);
          }
        }
      } catch (e) {}
    }
  }

  // Deduplicate pointer names per index
  for (const idx in pointers) {
    pointers[idx] = Array.from(new Set(pointers[idx]));
  }

  return (
    <motion.div 
      ref={containerRef}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: isDimmed ? 0.3 : 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3 }}
      className={`flex flex-col items-center gap-12 my-8 w-full relative ${isDimmed ? 'grayscale-[50%]' : ''}`}
    >
      <div className="flex flex-col items-center gap-1">
        <div className="text-emerald-400 font-mono text-xl tracking-wider uppercase">
          {data.name}
        </div>
        <div className="text-[10px] text-slate-500 font-mono uppercase tracking-widest">
          Array
        </div>
      </div>
      
      {isMatrix ? (
        <div className="flex flex-col items-center gap-2 relative min-h-[140px]">
          {trackedItems.map((rowItem: any, rIdx: number) => (
            <div key={`row-slot-${rIdx}`} className="flex items-start gap-3">
              {rowItem.value.map((cell: any, cIdx: number) => {
                const key = `${rIdx}-${cIdx}`;
                const isCompared = accessedIndices.has(key);
                
                const cellBgClass = isCompared 
                  ? 'border-blue-400 bg-blue-500/40 shadow-[0_0_20px_rgba(96,165,250,0.6)]' 
                  : 'border-emerald-500/50 bg-emerald-500/20 shadow-[0_0_20px_rgba(16,185,129,0.2)]';

                const slotBorderClass = isCompared 
                  ? 'border-blue-500/30' 
                  : 'border-emerald-500/20';

                return (
                  <div key={key} data-cell-coord={`${rIdx}-${cIdx}`} className="flex flex-col items-center relative">
                    {/* Index Label */}
                    <div className="text-[10px] text-slate-500 font-mono mb-1">{rIdx},{cIdx}</div>
                    {/* Fixed Background Cell Slot */}
                    <div className={`w-16 h-16 cell-slot rounded border-2 border-dashed ${slotBorderClass} bg-black/10 flex items-center justify-center relative`}>
                      <motion.div
                        layout={true}
                        className={`absolute inset-0 border-2 flex items-center justify-center text-2xl font-mono text-white rounded z-10 transition-colors duration-300 ${cellBgClass}`}
                      >
                        {cell}
                      </motion.div>
                    </div>
                    
                    <div className="absolute top-[85px] left-1/2 -translate-x-1/2 flex flex-col items-center z-20">
                      <AnimatePresence>
                        {pointers[key] && pointers[key].length > 0 && (
                          <motion.div
                            layout
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="text-blue-400 text-sm leading-none -mt-1 mb-1"
                          >
                            ▲
                          </motion.div>
                        )}
                      </AnimatePresence>
                      <div className="flex flex-col items-center gap-1">
                        {pointers[key] && pointers[key].map((ptr: string) => (
                          <motion.div
                            key={ptr}
                            layout
                            layoutId={`ptr-label-${data.name}-${ptr}`}
                            initial={{ opacity: 0, y: -10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ type: "spring", stiffness: 400, damping: 30 }}
                            className="text-blue-300 bg-blue-900/40 px-1.5 py-0.5 rounded border border-blue-500/30 shadow-[0_0_10px_rgba(59,130,246,0.2)] font-mono text-xs font-semibold whitespace-nowrap"
                          >
                            {ptr}
                          </motion.div>
                        ))}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      ) : (
        <div className="flex items-start gap-3 relative min-h-[140px]">
          {trackedItems.map((item: any, idx: number) => {
            const isCompared = accessedIndices.has(idx);
            
            const cellBgClass = isCompared 
              ? 'border-blue-400 bg-blue-500/40 shadow-[0_0_20px_rgba(96,165,250,0.6)]' 
              : 'border-emerald-500/50 bg-emerald-500/20 shadow-[0_0_20px_rgba(16,185,129,0.2)]';

            const slotBorderClass = isCompared 
              ? 'border-blue-500/30' 
              : 'border-emerald-500/20';

            return (
              <div key={`slot-${idx}`} data-cell-idx={idx} className="flex flex-col items-center relative">
                {/* Index Label */}
                <div className="text-[10px] text-slate-500 font-mono mb-1">{idx}</div>
                {/* Fixed Background Cell Slot */}
                <div className={`w-16 h-16 cell-slot rounded border-2 border-dashed ${slotBorderClass} bg-black/10 flex items-center justify-center relative`}>
                  {/* Movable Value Entity */}
                  <motion.div
                    key={`value-${item.id}`}
                    layout={true}
                    layoutId={`val-${data.name}-${item.id}`}
                    transition={{ type: "spring", stiffness: 400, damping: 30 }}
                    className={`absolute inset-0 border-2 flex items-center justify-center text-2xl font-mono text-white rounded z-10 transition-colors duration-300 ${cellBgClass}`}
                  >
                    {item.value}
                  </motion.div>
                </div>
                
                {/* Pointers Container */}
                <div className="absolute top-[85px] left-1/2 -translate-x-1/2 flex flex-col items-center z-20">
                  <AnimatePresence>
                    {pointers[idx] && pointers[idx].length > 0 && (
                      <motion.div
                        layout
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="text-blue-400 text-sm leading-none -mt-1 mb-1"
                      >
                        ▲
                      </motion.div>
                    )}
                  </AnimatePresence>
                  <div className="flex flex-col items-center gap-1">
                    {pointers[idx] && pointers[idx].map((ptr: string) => (
                      <motion.div
                        key={ptr}
                        layout
                        layoutId={`ptr-label-${data.name}-${ptr}`}
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ type: "spring", stiffness: 400, damping: 30 }}
                        className="text-blue-300 bg-blue-900/40 px-1.5 py-0.5 rounded border border-blue-500/30 shadow-[0_0_10px_rgba(59,130,246,0.2)] font-mono text-xs font-semibold whitespace-nowrap"
                      >
                        {ptr}
                      </motion.div>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Accumulators Section */}
      {isCurrentlyIterated && accumulators.length > 0 && (
        <div className="mt-8 flex flex-col items-center border-t border-white/5 pt-8 w-full max-w-lg">
          <div className="text-xs text-slate-500 uppercase tracking-widest mb-6">Running State</div>
          <div className="flex flex-wrap justify-center gap-6">
            {accumulators.map((acc) => (
              <motion.div
                key={acc.name}
                initial={{ scale: 1 }}
                animate={acc.changed ? { 
                  scale: [1, 1.1, 1],
                  backgroundColor: ['rgba(16, 185, 129, 0.1)', 'rgba(16, 185, 129, 0.4)', 'rgba(16, 185, 129, 0.1)'],
                  borderColor: ['rgba(16, 185, 129, 0.2)', 'rgba(16, 185, 129, 0.8)', 'rgba(16, 185, 129, 0.2)']
                } : {}}
                transition={{ duration: 0.5 }}
                className="flex flex-col items-center bg-emerald-500/10 border border-emerald-500/20 px-6 py-4 rounded-xl shadow-lg relative overflow-hidden"
              >
                {acc.changed && (
                  <motion.div 
                    initial={{ opacity: 0.8, scale: 1 }}
                    animate={{ opacity: 0, scale: 2 }}
                    transition={{ duration: 0.6 }}
                    className="absolute inset-0 bg-emerald-400/20 rounded-xl"
                  />
                )}
                <span className="text-emerald-500/70 font-mono text-xs mb-1 uppercase tracking-wider">{acc.name}</span>
                <span className="text-emerald-50 font-mono text-3xl tracking-tight">{acc.value}</span>
              </motion.div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}
