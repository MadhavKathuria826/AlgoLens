import { motion, AnimatePresence } from 'framer-motion';
import { useRef, useEffect } from 'react';

export default function DequeVisualizer({ data, locals, currentLineCode, operations }: { data: any, locals: any, currentLineCode?: string, operations?: any }) {
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
  const prevArrayRef = useRef<any[]>([]);
  const trackedItemsRef = useRef<{id: string, value: any}[]>([]);

  let newArray = data.value || [];
  let trackedItems = trackedItemsRef.current;

  // Change detection for ID preservation (crucial for Dequeue/Enqueue animations)
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
        const nextTracked = [];
        
        let isDequeue = false; // front remove
        if (newArray.length === prevArrayRef.current.length - 1) {
            let shiftLeftMatches = true;
            for (let i = 0; i < newArray.length; i++) {
                if (JSON.stringify(newArray[i]) !== JSON.stringify(prevArrayRef.current[i+1])) {
                    shiftLeftMatches = false;
                    break;
                }
            }
            if (shiftLeftMatches) isDequeue = true;
        }

        let isFrontInsert = false;
        if (newArray.length === prevArrayRef.current.length + 1) {
            let shiftRightMatches = true;
            for (let i = 0; i < prevArrayRef.current.length; i++) {
                if (JSON.stringify(newArray[i+1]) !== JSON.stringify(prevArrayRef.current[i])) {
                    shiftRightMatches = false;
                    break;
                }
            }
            if (shiftRightMatches) isFrontInsert = true;
        }

        if (isDequeue) {
            for (let i = 0; i < newArray.length; i++) {
                nextTracked.push(trackedItems[i+1]);
            }
        } else if (isFrontInsert) {
            nextTracked.push({ id: `id-${Math.random()}`, value: newArray[0] });
            for (let i = 0; i < trackedItems.length; i++) {
                nextTracked.push(trackedItems[i]);
            }
        } else {
            // General matching (handles Enqueue at the end)
            for (let i = 0; i < newArray.length; i++) {
               if (i < trackedItems.length && JSON.stringify(newArray[i]) === JSON.stringify(prevArrayRef.current[i])) {
                  nextTracked.push(trackedItems[i]);
               } else {
                  nextTracked.push({ id: `id-${Math.random()}`, value: newArray[i] });
               }
            }
        }
        trackedItems = nextTracked;
     } else {
        const nextTracked = [...trackedItems];
        for (let i = 0; i < newArray.length; i++) {
          if (JSON.stringify(newArray[i]) !== JSON.stringify(prevArrayRef.current[i])) {
            nextTracked[i] = { id: `id-${Math.random()}`, value: newArray[i] };
          }
        }
        trackedItems = nextTracked;
     }
     
     prevArrayRef.current = [...newArray];
     trackedItemsRef.current = trackedItems;
  }

  if (locals) {
    for (const k of Object.keys(locals)) {
      if (!memory[k]) {
        let score = 0;
        const lowerK = k.toLowerCase();
        if (['i', 'j', 'k', 'idx', 'index', 'ptr', 'front', 'rear', 'head', 'tail'].some(ig => lowerK.includes(ig))) {
            score += 10;
        }
        memory[k] = { confidence: score, isIterator: score >= 10 };
      }
    }
  }

  const pointers: Record<string, string[]> = {};
  if (locals) {
    for (const [k, v] of Object.entries(locals)) {
      if ((typeof v === 'string' && !v.startsWith('<')) || typeof v === 'number') {
        const numVal = typeof v === 'number' ? v : parseInt(v as string, 10);
        if (!isNaN(numVal) && numVal >= 0 && numVal < data.value.length) {
          if (memory[k] && memory[k].isIterator) {
            if (!pointers[numVal]) pointers[numVal] = [];
            pointers[numVal].push(k);
          }
        }
      }
    }
  }

  for (const idx in pointers) {
    pointers[idx] = Array.from(new Set(pointers[idx]));
  }

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3 }}
      className="flex flex-col items-center gap-6 my-8 w-full relative"
    >
      <div className="text-indigo-400 font-mono text-xl tracking-wider uppercase">{data.name}</div>
      
      <div className="flex flex-col items-center justify-center relative min-h-[100px] w-full px-12">
        {trackedItems.length === 0 && (
          <div className="w-24 h-12 border-2 border-dashed border-indigo-600/50 rounded flex items-center justify-center text-indigo-500 font-mono text-sm">
            empty
          </div>
        )}

        <div className="flex items-center justify-center gap-2 mt-8 py-2 min-w-[200px] relative">
          {/* Open Portal Brackets */}
          {trackedItems.length > 0 && (
             <>
               <span className="text-5xl text-indigo-500/30 font-thin absolute -left-6">⟨</span>
               <span className="text-5xl text-indigo-500/30 font-thin absolute -right-6">⟩</span>
             </>
          )}

          <AnimatePresence mode="popLayout">
            {trackedItems.map((item: any, idx: number) => {
              const isActivePointer = pointers[idx] && pointers[idx].length > 0;
              
              return (
                <motion.div
                  key={item.id}
                  layout
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  transition={{ type: "spring", stiffness: 400, damping: 30 }}
                  className="relative flex flex-col items-center mx-1"
                >
                  {/* Top Pointers */}
                  {isActivePointer && (
                    <div className="absolute bottom-full mb-3 flex flex-col items-center justify-end whitespace-nowrap">
                      <div className="flex flex-col items-center gap-1">
                        <div className="flex gap-1.5 flex-wrap justify-center">
                          {pointers[idx].map(ptr => (
                            <motion.div
                              key={ptr}
                              layoutId={`deque-ptr-${ptr}`}
                              className="text-indigo-300 bg-indigo-900/40 px-2 py-0.5 rounded border border-indigo-500/30 shadow-[0_0_10px_rgba(99,102,241,0.2)] font-mono text-xs font-semibold"
                            >
                              {ptr}
                            </motion.div>
                          ))}
                        </div>
                        <span className="text-indigo-400 text-sm leading-none mt-1">↓</span>
                      </div>
                    </div>
                  )}

                  {/* Deque Block */}
                  <div className="w-16 h-16 flex items-center justify-center font-mono text-lg font-medium rounded-md border-2 border-indigo-500/50 bg-slate-800 shadow-[0_0_15px_rgba(99,102,241,0.15)] transition-colors duration-300">
                    <span className="text-slate-100">{item.value !== undefined ? String(item.value) : ''}</span>
                  </div>

                  {/* Bottom Indicators (FRONT/REAR) */}
                  {(idx === 0 || idx === trackedItems.length - 1) && (
                     <div className="absolute top-full mt-3 flex flex-col items-center justify-start whitespace-nowrap font-mono text-sm tracking-widest font-bold">
                        <span className="text-lg leading-none mb-1 text-slate-400">↑</span>
                        <div className="flex gap-2">
                           {idx === 0 && <span className="text-indigo-400">⇄ FRONT</span>}
                           {idx === trackedItems.length - 1 && <span className="text-purple-400">REAR ⇄</span>}
                        </div>
                     </div>
                  )}
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}
