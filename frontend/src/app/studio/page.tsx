"use client";

import { useState, useEffect } from 'react';
import CodeEditor from '@/components/CodeEditor';
import VisualizationCanvas from '@/components/VisualizationCanvas';
import ExplanationPanel from '@/components/ExplanationPanel';
import Timeline from '@/components/Timeline';
import axios from 'axios';
import { Play, RotateCcw, StepForward, StepBack, Loader2, Pause, SkipBack } from 'lucide-react';
import { SemanticAnalyzer } from '@/utils/semanticAnalyzer';

export default function Studio() {
  const [code, setCode] = useState(`def factorial(n):\n    if n == 0:\n        return 1\n    return n * factorial(n - 1)\n\nresult = factorial(3)`);
  const [steps, setSteps] = useState<any[]>([]);
  const [currentStepIdx, setCurrentStepIdx] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    let timeoutId: NodeJS.Timeout;

    if (isPlaying && steps.length > 0) {
      if (currentStepIdx >= steps.length - 1) {
        setIsPlaying(false);
      } else {
        const baseDelay = 1000;
        const delay = baseDelay / playbackSpeed;
        
        timeoutId = setTimeout(() => {
          setCurrentStepIdx(prev => Math.min(steps.length - 1, prev + 1));
        }, delay);
      }
    }

    return () => clearTimeout(timeoutId);
  }, [isPlaying, currentStepIdx, steps.length, playbackSpeed]);


  const handleRun = async () => {
    setIsLoading(true);
    setIsPlaying(false);
    try {
      const res = await axios.post('http://localhost:8000/api/execute', { code });
      if (res.data.error) {
        setSteps([{
          step_number: 1,
          line_number: 0,
          event_type: 'error',
          locals: {},
          visualizations: [{ type: 'Error', details: { msg: res.data.error } }]
        }]);
        setCurrentStepIdx(0);
      } else if (res.data.steps) {
        const codeLines = code.split('\n');
        
        const buildSemanticInputs = (s: any) => {
          let inputs: any = {};
          if (s && s.locals) {
            Object.assign(inputs, s.locals);
          }
          if (s && s.visualizations) {
            s.visualizations.forEach((v: any) => {
              if (v.type === 'Array' && v.details && v.details.name) {
                inputs[v.details.name] = v.details.value;
              }
              if (v.type === 'Variable' || v.type === 'Loop') {
                Object.assign(inputs, v.details.locals || v.details);
              }
            });
          }
          return inputs;
        };

        const globalAnalyzer = new SemanticAnalyzer();
        const objIdRoles: Record<string, any> = {};

        res.data.steps.forEach((step: any, idx: number) => {
          const prevStep = idx > 0 ? res.data.steps[idx - 1] : null;
          const currentLineCode = codeLines[step.line_number - 1] || '';
          globalAnalyzer.analyzeFrame(buildSemanticInputs(step), buildSemanticInputs(prevStep), currentLineCode);

          if (step.visualizations) {
             const currentMem = globalAnalyzer.getMemory();
             step.visualizations.forEach((v: any) => {
                if (v.type === 'Array' && v.details && v.details.name && v.details.obj_id) {
                   const varName = v.details.name;
                   const objId = v.details.obj_id;
                   const mem = currentMem[varName];
                   if (mem && mem.primaryContainerRole !== 'UNKNOWN' && mem.primaryContainerRole !== 'ARRAY') {
                       if (!objIdRoles[objId]) objIdRoles[objId] = mem;
                       // Highest priority override (HEAP)
                       if (mem.primaryContainerRole === 'HEAP') objIdRoles[objId] = mem;
                   }
                }
             });
          }
        });
        const globalSemanticMemory = JSON.parse(JSON.stringify(globalAnalyzer.getMemory()));

        const isTreeAlgorithm = res.data.steps.some((s: any) => 
          s.heap && Object.keys(s.heap).some(k => s.heap[k].fields && ('left' in s.heap[k].fields || 'right' in s.heap[k].fields))
        );
        const isLinkedListAlgorithm = res.data.steps.some((s: any) => 
          !isTreeAlgorithm && s.heap && Object.keys(s.heap).some(k => s.heap[k].fields && 'next' in s.heap[k].fields)
        );

        const analyzer = new SemanticAnalyzer();
        const stepsWithSemantics = res.data.steps.map((step: any, idx: number) => {
          const prevStep = idx > 0 ? res.data.steps[idx - 1] : null;
          const currentLineCode = codeLines[step.line_number - 1] || '';
          
          const currentInputs = buildSemanticInputs(step);
          const prevInputs = buildSemanticInputs(prevStep);

          analyzer.analyzeFrame(currentInputs, prevInputs, currentLineCode);
          const localMemory = JSON.parse(JSON.stringify(analyzer.getMemory()));

          for (const k of Object.keys(localMemory)) {
             let globalId = globalSemanticMemory[k];

             // Check if it's an Array with an obj_id identity first
             const vis = step.visualizations?.find((v: any) => v.type === 'Array' && v.details?.name === k);
             if (vis && vis.details.obj_id && objIdRoles[vis.details.obj_id]) {
                 globalId = objIdRoles[vis.details.obj_id];
             }

             if (globalId) {
                const localVal = currentInputs[k];
                
                if (Array.isArray(localVal)) {
                   localMemory[k].primaryContainerRole = globalId.primaryContainerRole;
                   localMemory[k].containerScores = globalId.containerScores;
                   localMemory[k].operations = globalId.operations;
                } else {
                   localMemory[k].primaryContainerRole = 'UNKNOWN';
                }

                if (typeof localVal === 'number' || typeof localVal === 'boolean' || typeof localVal === 'string') {
                   localMemory[k].primaryRole = globalId.primaryRole;
                   localMemory[k].roleScores = globalId.roleScores;
                }
             }
          }
          
          return {
            ...step,
            semanticMemory: localMemory,
            isTreeAlgorithm,
            isLinkedListAlgorithm
          };
        });

        setSteps(stepsWithSemantics);
        setCurrentStepIdx(0);
      }
    } catch (err) {
      console.error(err);
    }
    setIsLoading(false);
  };

  const currentStep = steps[currentStepIdx] || null;
  const previousStep = currentStepIdx > 0 ? steps[currentStepIdx - 1] : null;

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] overflow-hidden">
      {/* Top Controls */}
      <div className="glass rounded-none border-t-0 border-l-0 border-r-0 border-b-white/10 p-2 flex items-center justify-between z-10 shrink-0 bg-black/40">
        <div className="flex items-center gap-2 px-4">
          <button 
            onClick={handleRun}
            disabled={isLoading}
            className="bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 px-4 py-1.5 rounded-md flex items-center gap-2 text-sm font-medium transition-colors disabled:opacity-50"
          >
            {isLoading ? <Loader2 className="animate-spin w-4 h-4" /> : <Play className="w-4 h-4" />}
            Run Execution
          </button>
          
          {steps.length > 0 && (
            <div className="flex items-center gap-2 border-l border-white/10 pl-4 ml-2">
              <button
                onClick={() => {
                  if (currentStepIdx >= steps.length - 1) {
                    setCurrentStepIdx(0);
                    setIsPlaying(true);
                  } else {
                    setIsPlaying(!isPlaying);
                  }
                }}
                className={`px-4 py-1.5 rounded-md flex items-center gap-2 text-sm font-medium transition-colors ${isPlaying ? 'bg-amber-500/20 text-amber-400 hover:bg-amber-500/30' : 'bg-blue-500/20 text-blue-400 hover:bg-blue-500/30'}`}
              >
                {isPlaying ? <><Pause className="w-4 h-4" /> Pause</> : <><Play className="w-4 h-4" /> Play</>}
              </button>
              
              <button 
                onClick={() => { setIsPlaying(false); setCurrentStepIdx(p => Math.max(0, p - 1)); }}
                className="bg-white/5 hover:bg-white/10 px-3 py-1.5 rounded-md flex items-center gap-2 text-sm font-medium transition-colors"
                title="Previous Step"
              >
                <StepBack className="w-4 h-4" /> Prev
              </button>
              
              <button 
                onClick={() => { setIsPlaying(false); setCurrentStepIdx(p => Math.min(steps.length - 1, p + 1)); }}
                className="bg-white/5 hover:bg-white/10 px-3 py-1.5 rounded-md flex items-center gap-2 text-sm font-medium transition-colors"
                title="Next Step"
              >
                Next <StepForward className="w-4 h-4" />
              </button>
              
              <button 
                onClick={() => { setIsPlaying(false); setCurrentStepIdx(0); }}
                className="bg-white/5 hover:bg-white/10 px-3 py-1.5 rounded-md flex items-center gap-2 text-sm font-medium transition-colors"
                title="Reset to Start"
              >
                <SkipBack className="w-4 h-4" /> Reset
              </button>

              <div className="flex items-center bg-black/40 rounded-md border border-white/10 ml-2 overflow-hidden">
                {[0.5, 1, 2, 4].map(speed => (
                  <button
                    key={speed}
                    onClick={() => setPlaybackSpeed(speed)}
                    className={`px-2 py-1.5 text-xs font-mono transition-colors ${playbackSpeed === speed ? 'bg-blue-500/30 text-blue-300' : 'text-slate-400 hover:bg-white/10 hover:text-slate-200'}`}
                  >
                    {speed}x
                  </button>
                ))}
              </div>
            </div>
          )}

          <button 
            onClick={() => { setSteps([]); setCurrentStepIdx(0); setIsPlaying(false); }}
            className="bg-white/5 hover:bg-white/10 px-4 py-1.5 rounded-md flex items-center gap-2 text-sm font-medium transition-colors text-red-400 ml-4 border border-red-500/20"
          >
            <RotateCcw className="w-4 h-4" /> Clear
          </button>
        </div>
        <div className="text-xs text-slate-500 px-4 font-mono">
          {steps.length > 0 ? `Step ${currentStepIdx + 1} of ${steps.length}` : 'Ready'}
        </div>
      </div>

      {/* Main 3-Column Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Code Editor */}
        <div className="w-1/3 border-r border-white/10 flex flex-col min-w-[300px]">
          <div className="px-4 py-2 text-xs font-semibold tracking-wider text-slate-500 uppercase bg-black/20">Code Editor</div>
          <div className="flex-1 overflow-hidden relative bg-[#1e1e1e]">
             <CodeEditor code={code} onChange={(val: string | undefined) => setCode(val || '')} activeLine={currentStep?.line_number} />
          </div>
        </div>

        {/* Center: Canvas */}
        <div className="flex-1 flex flex-col relative bg-[#050508] overflow-hidden">
          <div className="absolute top-0 left-0 right-0 px-4 py-2 text-xs font-semibold tracking-wider text-slate-500 uppercase z-10 bg-black/20 border-b border-white/5">Visualization</div>
          <VisualizationCanvas step={currentStep} code={code} />
        </div>

        {/* Right: Inspector */}
        <div className="w-80 border-l border-white/10 flex flex-col bg-black/20 shrink-0">
          <ExplanationPanel code={code} step={currentStep} previousStep={previousStep} />
        </div>
      </div>

      {/* Bottom: Timeline */}
      <div className="h-48 glass rounded-none border-b-0 border-l-0 border-r-0 border-t-white/10 shrink-0 bg-black/40">
        <Timeline 
          steps={steps} 
          currentIndex={currentStepIdx} 
          onNavigate={setCurrentStepIdx} 
        />
      </div>
    </div>
  );
}
