import { motion, AnimatePresence } from 'framer-motion';
import ArrayVisualizer from './visualizers/ArrayVisualizer';
import RecursionVisualizer from './visualizers/RecursionVisualizer';
import FunctionVisualizer from './visualizers/FunctionVisualizer';
import LoopVisualizer from './visualizers/LoopVisualizer';
import ConditionVisualizer from './visualizers/ConditionVisualizer';
import LinkedListVisualizer from './visualizers/LinkedListVisualizer';
import StackVisualizer from './visualizers/StackVisualizer';
import QueueVisualizer from './visualizers/QueueVisualizer';
import DequeVisualizer from './visualizers/DequeVisualizer';
import TreeVisualizer from './visualizers/TreeVisualizer';
import HeapVisualizer from './visualizers/HeapVisualizer';
import Viewport from './Viewport';

export default function VisualizationCanvas({ step, code }: any) {
  if (!step || !step.visualizations || step.visualizations.length === 0) {
    return <div className="flex-1 flex items-center justify-center text-slate-500 font-light text-lg">Run code to see the algorithm</div>;
  }

  const hasRecursion = step.visualizations.some((v: any) => v.type === 'RecursionTree');

  const extractLocals = (s: any) => {
    let locals = {};
    if (s && s.locals) {
      Object.assign(locals, s.locals);
    }
    if (s && s.visualizations) {
      s.visualizations.forEach((v: any) => {
        if (v.type === 'Variable' || v.type === 'Loop') {
          Object.assign(locals, v.details.locals || v.details);
        }
      });
    }
    return locals;
  };
  const activeLocals = extractLocals(step);

  // Detect active loop line to determine which array is currently being iterated
  let activeLoopLine = "";
  let currentLineCode = "";
  if (code && step && step.line_number > 0) {
    const lines = code.split('\n');
    currentLineCode = lines[step.line_number - 1] || "";
    const currentIndentation = currentLineCode.search(/\S/);
    
    for (let i = step.line_number - 1; i >= 0; i--) {
      const lineStr = lines[i];
      if (!lineStr) continue;
      const trimmed = lineStr.trim();
      const indent = lineStr.search(/\S/);
      
      if ((trimmed.startsWith('for ') || trimmed.startsWith('while ')) && 
          (i === step.line_number - 1 || indent < (currentIndentation === -1 ? 999 : currentIndentation))) {
        activeLoopLine = trimmed;
        break;
      }
    }
  }

  const anyArrayIterated = step.visualizations.some((v: any) => 
    v.type === 'Array' && activeLoopLine.includes(v.details.name)
  );

  const hasTree = step.isTreeAlgorithm || (step.heap && Object.keys(step.heap).some(k => step.heap[k].fields && ('left' in step.heap[k].fields || 'right' in step.heap[k].fields)));
  const hasLinkedList = step.isLinkedListAlgorithm || (!hasTree && step.heap && Object.keys(step.heap).some(k => step.heap[k].fields && 'next' in step.heap[k].fields));

  return (
    <div className="relative w-full h-full flex flex-col">
      <Viewport>
        <div className="flex flex-col items-center justify-center gap-8 min-w-max p-8">
          {hasLinkedList && <LinkedListVisualizer heap={step.heap} locals={activeLocals} />}
          {hasTree && <TreeVisualizer heap={step.heap} locals={activeLocals} />}
          <AnimatePresence mode="popLayout">
            {step.visualizations.map((vis: any, index: number) => {
            switch (vis.type) {
              case 'Array':
                if (hasTree || hasLinkedList) return null;

                const isCurrentlyIterated = activeLoopLine.includes(vis.details.name);
                const isDimmed = anyArrayIterated && !isCurrentlyIterated;
                
                const semanticIdentity = step.semanticMemory?.[vis.details.name];
                const isStack = semanticIdentity?.primaryContainerRole === 'STACK';
                const isQueue = semanticIdentity?.primaryContainerRole === 'QUEUE';
                const isDeque = semanticIdentity?.primaryContainerRole === 'DEQUE';
                const isHeap = semanticIdentity?.primaryContainerRole === 'HEAP';

                const keyBase = vis.details.obj_id || vis.details.name;

                if (isHeap) {
                  return (
                    <HeapVisualizer 
                      key={`heap-${keyBase}`} 
                      data={vis.details} 
                      locals={activeLocals} 
                      currentLineCode={currentLineCode}
                    />
                  );
                }

                if (isStack) {
                  return (
                    <StackVisualizer 
                      key={`stack-${keyBase}`} 
                      data={vis.details} 
                      locals={activeLocals} 
                      currentLineCode={currentLineCode}
                    />
                  );
                }

                if (isQueue) {
                  return (
                    <QueueVisualizer 
                      key={`queue-${keyBase}`} 
                      data={vis.details} 
                      locals={activeLocals} 
                      currentLineCode={currentLineCode}
                    />
                  );
                }

                if (isDeque) {
                  return (
                    <DequeVisualizer 
                      key={`deque-${keyBase}`} 
                      data={vis.details} 
                      locals={activeLocals} 
                      currentLineCode={currentLineCode}
                      operations={semanticIdentity.operations}
                    />
                  );
                }

                return (
                  <ArrayVisualizer 
                    key={`arr-${keyBase}`} 
                    data={vis.details} 
                    locals={activeLocals} 
                    isCurrentlyIterated={isCurrentlyIterated}
                    isDimmed={isDimmed}
                    currentLineCode={currentLineCode}
                  />
                );
              case 'RecursionTree':
              case 'Function':
                if (hasTree || hasLinkedList) return null;
                return vis.type === 'RecursionTree' ? 
                       <RecursionVisualizer key={`rec-tree`} data={vis.details} /> :
                       <FunctionVisualizer key={`func`} data={vis.details} />;
              case 'Loop':
                if (hasTree || hasLinkedList) return null;
                return <LoopVisualizer key={`loop-${index}`} data={vis.details} />;
              case 'Condition':
                if (hasTree || hasLinkedList) return null;
                return <ConditionVisualizer key={`cond-${index}`} data={vis.details} />;
              case 'Variable':
                if (hasTree || hasLinkedList) return null;
                const hasRecursion = step.visualizations.some((v: any) => v.type === 'RecursionTree');
                if (hasRecursion) return null;

                const validEntries = Object.entries(vis.details).filter(
                  ([k, v]: any) => ((typeof v === 'string' && !v.startsWith('<function') && !v.startsWith('<module') && !v.startsWith('obj_')) || typeof v === 'number')
                );

                if (validEntries.length === 0) return null;

                return (
                  <motion.div 
                    key={`var-${index}`} 
                    initial={{ opacity: 0, y: 20 }} 
                    animate={{ opacity: 1, y: 0 }} 
                    exit={{ opacity: 0, scale: 0.8 }} 
                    className="glass p-6 rounded-xl border-blue-500/20 shadow-[0_0_20px_rgba(59,130,246,0.1)] flex flex-col gap-2"
                  >
                    <div className="text-xs text-blue-400 uppercase tracking-widest font-semibold border-b border-blue-500/20 pb-2 mb-2">Memory State</div>
                    {validEntries.map(([k, v]: any) => (
                      <div key={k} className="flex justify-between gap-8 font-mono text-lg">
                        <span className="text-slate-300">{k}</span>
                        <span className="text-emerald-400">{v}</span>
                      </div>
                    ))}
                  </motion.div>
                );
              case 'Error':
                return (
                   <motion.div key={`err-${index}`} className="text-red-400 p-4 border border-red-500/50 bg-red-500/10 rounded-lg max-w-md text-center">
                      {vis.details.msg}
                   </motion.div>
                );
              default:
                return null;
            }
          })}
        </AnimatePresence>
        </div>
      </Viewport>
    </div>
  );
}
