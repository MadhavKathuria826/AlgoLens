import { motion, AnimatePresence } from 'framer-motion';
import { useRef, useEffect } from 'react';

export default function StackVisualizer({ data, locals, currentLineCode }: { data: any, locals: any, currentLineCode?: string }) {
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

  // Change detection for ID preservation (crucial for Pop/Push animations)
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
        // Stack typically changes by 1 at the tail. Let's try to match existing elements.
        const nextTracked = [];
        for (let i = 0; i < newArray.length; i++) {
           if (i < trackedItems.length && JSON.stringify(newArray[i]) === JSON.stringify(prevArrayRef.current[i])) {
              nextTracked.push(trackedItems[i]);
           } else {
              nextTracked.push({ id: `id-${Math.random()}`, value: newArray[i] });
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

  // 1. Initial Semantic Memory Scoring
  if (locals) {
    for (const k of Object.keys(locals)) {
      if (!memory[k]) {
        let score = 0;
        const lowerK = k.toLowerCase();
        if (['i', 'j', 'k', 'idx', 'index', 'ptr', 'top'].some(ig => lowerK.includes(ig))) {
            score += 10;
        }
        memory[k] = { confidence: score, isIterator: score >= 10 };
      }
    }
  }

  // Pointer deduction
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

  // Deduplicate
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
      <div className="flex flex-col items-center h-16 justify-end">
        <div className="text-emerald-400 font-mono text-xl tracking-wider uppercase mb-2">{data.name}</div>
        
        {/* Render "TOP" arrow above the stack if it has elements */}
        <AnimatePresence>
          {trackedItems.length > 0 && (
            <motion.div 
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              className="flex flex-col items-center"
            >
              <span className="text-blue-400 font-mono text-sm tracking-widest font-bold">TOP</span>
              <span className="text-blue-400 text-lg leading-none">↓</span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      
      <div className="flex flex-col-reverse items-center justify-start gap-0 relative min-h-[60px] pb-4">
        {trackedItems.length === 0 && (
          <div className="w-24 h-12 border-2 border-dashed border-slate-600/50 rounded flex items-center justify-center text-slate-500 font-mono text-sm">
            empty
          </div>
        )}

        <AnimatePresence mode="popLayout">
          {trackedItems.map((item: any, idx: number) => {
            const isActivePointer = pointers[idx] && pointers[idx].length > 0;
            const isTop = idx === trackedItems.length - 1;

            return (
              <motion.div
                key={item.id}
                layout
                initial={{ opacity: 0, y: -30, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -30, scale: 0.95 }}
                transition={{ type: "spring", stiffness: 400, damping: 25 }}
                className="relative flex items-center justify-center"
              >
                {/* Side Pointers */}
                {isActivePointer && (
                  <div className="absolute right-full mr-4 flex items-center justify-end whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <div className="flex gap-1.5 flex-wrap justify-end">
                        {pointers[idx].map(ptr => (
                          <motion.div
                            key={ptr}
                            layoutId={`stack-ptr-${ptr}`}
                            className="text-blue-300 bg-blue-900/40 px-2 py-0.5 rounded border border-blue-500/30 shadow-[0_0_10px_rgba(59,130,246,0.2)] font-mono text-xs font-semibold"
                          >
                            {ptr}
                          </motion.div>
                        ))}
                      </div>
                      <span className="text-blue-400 text-sm leading-none ml-1">→</span>
                    </div>
                  </div>
                )}

                {/* Stack Block */}
                <div className={`
                  w-24 h-12 flex items-center justify-center font-mono text-lg font-medium relative
                  ${idx === 0 ? 'rounded-b-md border-b-2' : 'border-b-0'} 
                  ${isTop ? 'rounded-t-md' : ''}
                  border-2 border-emerald-500/50 bg-slate-800 shadow-[0_0_15px_rgba(16,185,129,0.1)]
                  transition-colors duration-300
                `}>
                  <span className="text-slate-100">{item.value !== undefined ? String(item.value) : ''}</span>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
        
        {/* The Base of the Stack */}
        {trackedItems.length > 0 && (
           <div className="w-28 h-2 bg-emerald-500/20 rounded-full mt-1 blur-[2px]"></div>
        )}
      </div>
    </motion.div>
  );
}
