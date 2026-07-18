import { motion, AnimatePresence } from 'framer-motion';

interface DPVisualizerProps {
  data: any;
  steps: any[];
  currentStepIdx: number;
  locals: any;
  currentLineCode?: string;
  recurrenceRelations?: string[];
}

export default function DPVisualizer({ data, steps, currentStepIdx, locals, currentLineCode, recurrenceRelations = [] }: DPVisualizerProps) {
  const isTabulation = data.dimensions !== undefined || data.table_shape !== undefined;
  
  if (isTabulation) {
    return (
      <TabulationVisualizer 
        data={data}
        steps={steps}
        currentStepIdx={currentStepIdx}
        recurrenceRelations={recurrenceRelations}
      />
    );
  } else {
    return (
      <MemoizationVisualizer 
        data={data}
        steps={steps}
        currentStepIdx={currentStepIdx}
        recurrenceRelations={recurrenceRelations}
      />
    );
  }
}

function TabulationVisualizer({ data, steps, currentStepIdx, recurrenceRelations = [] }: { data: any, steps: any[], currentStepIdx: number, recurrenceRelations?: string[] }) {
  const name = data.name;
  const dimensions = data.dimensions || 1;
  const tableShape = data.table_shape || [10];
  
  // 1. Scan history to find all revealed indices up to currentStepIdx
  const revealedSet = new Set<string>();
  for (let i = 0; i <= currentStepIdx; i++) {
    const step = steps[i];
    if (step && step.visualizations) {
      for (const vis of step.visualizations) {
        if (vis.type === 'DP_TABLE' && vis.details.name === name) {
          if (vis.details.target) {
            const tgt = vis.details.target;
            revealedSet.add(tgt.join(','));
          }
        }
      }
    }
  }
  
  const currentTarget = data.target ? data.target.join(',') : null;
  const currentSources = new Set<string>();
  if (data.sources) {
    for (const src of data.sources) {
      currentSources.add(src.join(','));
    }
  }
  
  const currentValue = data.value || [];
  
  if (dimensions === 1) {
    const size = tableShape[0];
    const cells = [];
    for (let idx = 0; idx < size; idx++) {
      const isRevealed = revealedSet.has(String(idx));
      const isTarget = currentTarget === String(idx);
      const isSource = currentSources.has(String(idx));
      const val = currentValue[idx];
      
      cells.push(
        <div key={idx} className="flex flex-col items-center relative">
          <div className="text-[10px] text-slate-500 font-mono mb-1">{idx}</div>
          <div className="w-16 h-16 cell-slot rounded border border-white/5 bg-black/10 flex items-center justify-center relative">
            <motion.div
              layoutId={`cell-${name}-${idx}`}
              className={`absolute inset-0 border flex items-center justify-center text-2xl font-mono rounded transition-colors duration-300 ${
                isTarget
                  ? 'border-indigo-400 bg-indigo-600 shadow-[0_0_20px_rgba(129,140,248,0.8)] text-white z-20 font-bold'
                  : isSource
                    ? 'border-emerald-400 bg-emerald-600 text-white z-10 font-bold'
                    : isRevealed
                      ? 'border-slate-600 bg-slate-800 text-slate-200'
                      : 'border-slate-800 bg-slate-950/40 text-slate-600 opacity-40'
              }`}
              animate={isTarget ? { scale: [1, 1.15, 1] } : {}}
            >
              {isRevealed || isTarget ? String(val !== null && val !== undefined ? val : '') : ''}
            </motion.div>
          </div>
        </div>
      );
    }
    
    return (
      <div className="flex flex-col items-center gap-6 my-8 w-full relative">
        <div className="absolute top-0 right-4 text-[9px] font-mono text-slate-600 bg-white/5 px-2 py-0.5 rounded border border-white/5 select-none z-30">
          BUILD-22
        </div>
        <div className="flex flex-col items-center gap-1">
          <div className="text-indigo-400 font-mono text-xl tracking-wider uppercase">{name}</div>
          <div className="text-[10px] text-slate-500 font-mono uppercase tracking-widest font-semibold">Tabulation 1D</div>
        </div>

        {recurrenceRelations && recurrenceRelations.length > 0 && (
          <div className="w-full max-w-lg bg-bg-surface border border-white/5 rounded-xl p-4 flex flex-col gap-2 shadow-sm font-sans">
            <div className="text-[10px] text-slate-500 uppercase tracking-widest font-mono font-semibold">Recurrence Relation</div>
            <div className="flex flex-col gap-1.5 font-mono text-xs text-amber-400 bg-black/20 p-3 rounded-lg border border-white/5">
              {recurrenceRelations.map((rel, idx) => (
                <div key={idx} className="flex items-start gap-2">
                  <span className="text-slate-500 select-none">•</span>
                  <span>{rel}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex items-start gap-3 flex-wrap justify-center max-w-4xl p-4 bg-bg-surface/50 border border-white/5 rounded-2xl">
          {cells}
        </div>
      </div>
    );
  } else {
    const rows = tableShape[0];
    const cols = tableShape[1];
    
    const matrixRows = [];
    for (let r = 0; r < rows; r++) {
      const cells = [];
      for (let c = 0; c < cols; c++) {
        const key = `${r},${c}`;
        const isRevealed = revealedSet.has(key);
        const isTarget = currentTarget === key;
        const isSource = currentSources.has(key);
        const val = currentValue[r] ? currentValue[r][c] : null;
        
        cells.push(
          <div key={c} className="flex flex-col items-center relative">
            <div className="w-14 h-14 cell-slot rounded border border-white/5 bg-black/10 flex items-center justify-center relative">
              <motion.div
                className={`absolute inset-0 border flex items-center justify-center text-xl font-mono rounded transition-colors duration-300 ${
                  isTarget
                    ? 'border-indigo-400 bg-indigo-600 shadow-[0_0_20px_rgba(129,140,248,0.8)] text-white z-20 font-bold'
                    : isSource
                      ? 'border-emerald-400 bg-emerald-600 text-white z-10 font-bold'
                      : isRevealed
                        ? 'border-slate-600 bg-slate-800 text-slate-200'
                        : 'border-slate-800 bg-slate-950/40 text-slate-600 opacity-40'
                }`}
                animate={isTarget ? { scale: [1, 1.15, 1] } : {}}
              >
                {isRevealed || isTarget ? String(val !== null && val !== undefined ? val : '') : ''}
              </motion.div>
            </div>
          </div>
        );
      }
      
      matrixRows.push(
        <div key={r} className="flex items-center gap-2">
          <div className="w-8 text-right pr-2 text-slate-600 font-mono text-xs">{r}</div>
          <div className="flex items-center gap-2">{cells}</div>
        </div>
      );
    }
    
    return (
      <div className="flex flex-col items-center gap-6 my-8 w-full relative">
        <div className="absolute top-0 right-4 text-[9px] font-mono text-slate-600 bg-white/5 px-2 py-0.5 rounded border border-white/5 select-none z-30">
          BUILD-22
        </div>
        <div className="flex flex-col items-center gap-1">
          <div className="text-indigo-400 font-mono text-xl tracking-wider uppercase">{name}</div>
          <div className="text-[10px] text-slate-500 font-mono uppercase tracking-widest font-semibold">Tabulation 2D Matrix</div>
        </div>

        {recurrenceRelations && recurrenceRelations.length > 0 && (
          <div className="w-full max-w-lg bg-bg-surface border border-white/5 rounded-xl p-4 flex flex-col gap-2 shadow-sm font-sans">
            <div className="text-[10px] text-slate-500 uppercase tracking-widest font-mono font-semibold">Recurrence Relation</div>
            <div className="flex flex-col gap-1.5 font-mono text-xs text-amber-400 bg-black/20 p-3 rounded-lg border border-white/5">
              {recurrenceRelations.map((rel, idx) => (
                <div key={idx} className="flex items-start gap-2">
                  <span className="text-slate-500 select-none">•</span>
                  <span>{rel}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-col gap-2 p-6 bg-bg-surface/50 border border-white/5 rounded-2xl overflow-auto max-w-full">
          <div className="flex items-center gap-2">
            <div className="w-8" />
            <div className="flex items-center gap-2">
              {Array.from({ length: cols }).map((_, c) => (
                <div key={c} className="w-14 text-center text-slate-600 font-mono text-xs">{c}</div>
              ))}
            </div>
          </div>
          {matrixRows}
        </div>
      </div>
    );
  }
}

function MemoizationVisualizer({ data, steps, currentStepIdx, recurrenceRelations = [] }: { data: any, steps: any[], currentStepIdx: number, recurrenceRelations?: string[] }) {
  const cacheEntries: { key: string, value: any }[] = [];
  const cacheMap = new Map<string, number>();
  const activeCallStack: string[] = [];
  
  const currentStep = steps[currentStepIdx];
  const currentVis = currentStep?.visualizations?.find((v: any) => v.type === 'MEMOIZATION');
  const currentEvent = currentVis?.details?.event;
  const currentKey = currentVis?.details?.key;
  
  for (let i = 0; i <= currentStepIdx; i++) {
    const step = steps[i];
    if (step && step.visualizations) {
      const vis = step.visualizations.find((v: any) => v.type === 'MEMOIZATION');
      if (vis) {
        const d = vis.details;
        const depth = d.call_depth || 1;
        if (d.event === 'call') {
          activeCallStack.splice(depth - 1);
          activeCallStack[depth - 1] = d.key;
        } else if (d.event === 'cache_write') {
          activeCallStack.splice(depth - 1);
          if (!cacheMap.has(d.key)) {
            cacheMap.set(d.key, cacheEntries.length);
            cacheEntries.push({ key: d.key, value: d.value });
          }
        } else if (d.event === 'cache_hit') {
          activeCallStack.splice(depth - 1);
        }
      }
    }
  }
  
  return (
    <div className="flex flex-col items-center gap-6 my-8 w-full max-w-lg relative">
      <div className="absolute top-0 right-0 text-[9px] font-mono text-slate-600 bg-white/5 px-2 py-0.5 rounded border border-white/5 select-none z-30">
        BUILD-22
      </div>
      <div className="flex flex-col items-center gap-1">
        <div className="text-indigo-400 font-mono text-xl tracking-wider uppercase">Memoization Cache</div>
        <div className="text-[10px] text-slate-500 font-mono uppercase tracking-widest font-semibold">Recursive Event Log</div>
      </div>

      {recurrenceRelations && recurrenceRelations.length > 0 && (
        <div className="w-full bg-bg-surface border border-white/5 rounded-xl p-4 flex flex-col gap-2 shadow-sm font-sans text-left align-start">
          <div className="text-[10px] text-slate-500 uppercase tracking-widest font-mono font-semibold">Recurrence Relation (Recursive)</div>
          <div className="flex flex-col gap-1.5 font-mono text-xs text-amber-400 bg-black/20 p-3 rounded-lg border border-white/5">
            {recurrenceRelations.map((rel, idx) => (
              <div key={idx} className="flex items-start gap-2">
                <span className="text-slate-500 select-none">•</span>
                <span>{rel}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      
      <div className="w-full bg-slate-950/40 border border-white/5 rounded-xl p-4 flex flex-col gap-2">
        <div className="text-[10px] text-slate-500 uppercase tracking-widest font-mono font-semibold">Active Recursion Path</div>
        <div className="flex items-center gap-2 flex-wrap font-mono text-sm">
          {activeCallStack.length === 0 ? (
            <span className="text-slate-600 italic">Empty</span>
          ) : (
            activeCallStack.map((key, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <span className="bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded">
                  {key}
                </span>
                {idx < activeCallStack.length - 1 && <span className="text-slate-600">→</span>}
              </div>
            ))
          )}
        </div>
      </div>
      
      <div className="w-full flex flex-col gap-3 min-h-[200px] max-h-[400px] overflow-y-auto p-4 bg-bg-surface/50 border border-white/5 rounded-2xl">
        <div className="text-[10px] text-slate-500 uppercase tracking-widest font-mono font-semibold border-b border-white/5 pb-2 mb-2">Stored Cache Entries</div>
        <div className="flex flex-col gap-2">
          {cacheEntries.length === 0 ? (
            <div className="text-slate-600 italic text-center py-8 text-sm">No entries written yet</div>
          ) : (
            cacheEntries.map((entry) => {
              const isHit = currentEvent === 'cache_hit' && currentKey === entry.key;
              
              return (
                <motion.div
                  key={entry.key}
                  initial={{ opacity: 0, x: -20 }}
                  animate={
                    isHit 
                      ? { 
                          scale: [1, 1.08, 0.97, 1.03, 1],
                          borderColor: ["rgba(255,255,255,0.05)", "#fbbf24", "rgba(255,255,255,0.05)"],
                          backgroundColor: ["rgba(255,255,255,0.01)", "rgba(245,158,11,0.25)", "rgba(255,255,255,0.01)"],
                          boxShadow: ["0 0 0 rgba(245,158,11,0)", "0 0 25px rgba(245,158,11,0.6)", "0 0 0 rgba(245,158,11,0)"]
                        }
                      : { opacity: 1, scale: 1, x: 0 }
                  }
                  transition={isHit ? { duration: 0.8 } : { duration: 0.3 }}
                  className={`flex items-center justify-between p-3 rounded-xl border bg-white/[0.01] ${
                    isHit 
                      ? 'border-amber-400 bg-amber-500/20 shadow-[0_0_20px_rgba(245,158,11,0.5)] z-20'
                      : 'border-white/5'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <span className="text-slate-400 font-mono text-sm">key:</span>
                    <span className={`font-mono text-sm px-2 py-0.5 rounded ${isHit ? 'text-amber-300 font-bold bg-amber-500/10' : 'text-slate-100 bg-white/5'}`}>{entry.key}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-slate-400 font-mono text-sm">val:</span>
                    <span className={`font-mono text-lg ${isHit ? 'text-amber-400 font-extrabold' : 'text-emerald-400 font-bold'}`}>{String(entry.value)}</span>
                  </div>
                </motion.div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
