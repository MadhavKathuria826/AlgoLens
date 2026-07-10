"use client";

import { useState, useEffect } from 'react';
import Link from 'next/link';
import CodeEditor from '@/components/CodeEditor';
import VisualizationCanvas from '@/components/VisualizationCanvas';
import ExplanationPanel from '@/components/ExplanationPanel';
import Timeline from '@/components/Timeline';
import axios from 'axios';
import { Play, RotateCcw, StepForward, StepBack, Loader2, Pause, SkipBack } from 'lucide-react';
import { SemanticAnalyzer } from '@/utils/semanticAnalyzer';
import ThemePopover from '@/components/ThemePopover';
import ExportButton from '@/components/ExportButton';
import SettingsModal from '@/components/SettingsModal';
import TestCaseModal from '@/components/TestCaseModal';
import { useSettings } from '@/contexts/SettingsContext';

export default function Studio({ onBack }: { onBack?: () => void }) {
  const [code, setCode] = useState(`def factorial(n):\n    if n == 0:\n        return 1\n    return n * factorial(n - 1)\n\nresult = factorial(3)`);
  const [steps, setSteps] = useState<any[]>([]);
  const [currentStepIdx, setCurrentStepIdx] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const { settings, updateSettings } = useSettings();
  
  // Local session override for playback speed, initialized from settings default
  const [playbackSpeed, setPlaybackSpeed] = useState(() => 
    settings.animationSpeed === 'slow' ? 0.5 : settings.animationSpeed === 'fast' ? 2 : 1
  );

  const [modalMode, setModalMode] = useState<'disambiguation' | 'params' | null>(null);
  const [modalCandidates, setModalCandidates] = useState<string[] | null>(null);
  const [modalParams, setModalParams] = useState<string[] | null>(null);
  const [modalError, setModalError] = useState<string | null>(null);
  const [selectedMethod, setSelectedMethod] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isFullscreen) {
        setIsFullscreen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isFullscreen]);

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


  const handleRun = () => {
    setSelectedMethod(null);
    executeCode();
  };

  const executeCode = async (optionalTestCase?: string, optionalSelectedMethod?: string, isFromModal: boolean = false) => {
    setIsLoading(true);
    setIsPlaying(false);
    setModalError(null);
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const res = await axios.post(`${API_URL}/api/execute`, { 
        code, 
        max_recursion_depth: settings.maxRecursionDepth,
        test_case: optionalTestCase,
        selected_method: optionalSelectedMethod || selectedMethod
      }, {
        timeout: settings.executionTimeoutMs,
      });

      if (res.data.needs_disambiguation) {
        setModalCandidates(res.data.candidates);
        setModalMode('disambiguation');
        setIsModalOpen(true);
      } else if (res.data.needs_test_case) {
        setModalParams(res.data.params);
        setModalMode('params');
        setIsModalOpen(true);
      } else if (res.data.error) {
        if (isFromModal) {
          setModalError(res.data.error);
        } else {
          setSteps([{
            step_number: 1,
            line_number: 0,
            event_type: 'error',
            locals: {},
            visualizations: [{ type: 'Error', details: { msg: res.data.error } }]
          }]);
          setCurrentStepIdx(0);
        }
      } else if (res.data.steps) {
        setIsModalOpen(false);
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
    } catch (err: any) {
      console.error(err);
      if (err.code === 'ECONNABORTED' || (err.message && err.message.includes('timeout'))) {
        setSteps([{
          step_number: 1,
          line_number: 0,
          event_type: 'error',
          locals: {},
          visualizations: [{ type: 'Error', details: { msg: `Execution timed out after ${settings.executionTimeoutMs / 1000} seconds. You might have an infinite loop or recursion.` } }]
        }]);
        setCurrentStepIdx(0);
      }
    }
    setIsLoading(false);
  };

  const currentStep = steps[currentStepIdx] || null;
  const previousStep = currentStepIdx > 0 ? steps[currentStepIdx - 1] : null;

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-bg-app text-text-body font-sans">
      {/* Global App Navigation Bar */}
      <nav className="h-[72px] w-full flex items-center justify-between px-6 bg-bg-surface border-b border-white/5 shrink-0 z-50">
        <div className="flex items-center gap-4">
          <Link 
            href="/" 
            onClick={(e) => {
              if (onBack) {
                e.preventDefault();
                onBack();
              }
            }}
            className="text-xl font-bold tracking-tight text-brand-teal"
          >
            AlgoLens
          </Link>
          <div className="h-4 w-px bg-white/10 mx-2" />
          <span className="text-slate-300 font-medium">Studio</span>
        </div>
        <div className="flex items-center gap-2">
          <ThemePopover />
          <ExportButton disabled={steps.length === 0} />
          <SettingsModal />
        </div>
      </nav>

      <div className="flex flex-col flex-1 overflow-hidden p-6 gap-6">
        {/* Top Controls (not in navbar) */}
        <div className="panel-surface py-3 px-6 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-4">
            <button 
              onClick={handleRun}
              disabled={isLoading}
              className="btn-primary gap-2"
            >
              {isLoading ? <Loader2 className="animate-spin w-5 h-5" /> : <Play className="w-5 h-5" />}
              Run
            </button>
            
            {steps.length > 0 && (
              <div className="flex items-center gap-2 border-l border-white/10 pl-4">
                <button
                  onClick={() => {
                    if (currentStepIdx >= steps.length - 1) {
                      setCurrentStepIdx(0);
                      setIsPlaying(true);
                    } else {
                      setIsPlaying(!isPlaying);
                    }
                  }}
                  className="btn-secondary gap-2"
                >
                  {isPlaying ? <><Pause className="w-5 h-5" /> Pause</> : <><Play className="w-5 h-5" /> Play</>}
                </button>
                
                <button 
                  onClick={() => { setIsPlaying(false); setCurrentStepIdx(p => Math.max(0, p - 1)); }}
                  className="btn-icon bg-bg-app border border-white/5 hover:border-brand-teal"
                  title="Previous Step"
                >
                  <StepBack className="w-5 h-5 text-text-heading" />
                </button>
                
                <button 
                  onClick={() => { setIsPlaying(false); setCurrentStepIdx(p => Math.min(steps.length - 1, p + 1)); }}
                  className="btn-icon bg-bg-app border border-white/5 hover:border-brand-teal"
                  title="Next Step"
                >
                  <StepForward className="w-5 h-5 text-text-heading" />
                </button>
                
                <button 
                  onClick={() => { setIsPlaying(false); setCurrentStepIdx(0); }}
                  className="btn-ghost gap-2 text-slate-400"
                  title="Reset to Start"
                >
                  <SkipBack className="w-4 h-4" />
                </button>

                <div className="flex items-center bg-bg-app rounded-xl border border-white/5 overflow-hidden ml-2">
                  {[0.5, 1, 2, 4].map(speed => (
                    <button
                      key={speed}
                      onClick={() => setPlaybackSpeed(speed)}
                      className={`px-3 py-2 text-sm font-mono transition-colors ${playbackSpeed === speed ? 'bg-brand-teal/20 text-brand-teal font-semibold' : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'}`}
                    >
                      {speed}x
                    </button>
                  ))}
                </div>
              </div>
            )}

            <button 
              onClick={() => { setSteps([]); setCurrentStepIdx(0); setIsPlaying(false); }}
              className="btn-ghost gap-2 text-brand-coral hover:bg-brand-coral/10 ml-4"
            >
              <RotateCcw className="w-4 h-4" /> Clear
            </button>
          </div>
          <div className="text-sm text-slate-500 font-mono">
            {steps.length > 0 ? `Step ${currentStepIdx + 1} of ${steps.length}` : 'Ready'}
          </div>
        </div>

        {/* Main 3-Column Layout */}
        <div className="flex-1 flex gap-6 overflow-hidden">
          {/* Left: Code Editor */}
          <div className="w-[30%] panel-surface flex flex-col !p-0 overflow-hidden">
            <div className="px-6 py-4 text-xs font-semibold tracking-wider text-slate-500 uppercase border-b border-white/5 bg-bg-surface z-10">Code Editor</div>
            <div className="flex-1 overflow-hidden relative bg-bg-surface">
              <CodeEditor 
                code={code} 
                onChange={(val: string | undefined) => setCode(val || '')} 
                activeLine={currentStep?.line_number}
                onRun={handleRun}
              />
            </div>
          </div>

          {/* Center: Canvas */}
          <div 
            id="export-visualization-panel" 
            className={`panel-surface flex flex-col !p-0 overflow-hidden bg-bg-app ${
              isFullscreen ? '!fixed !inset-0 !z-[100]' : 'flex-1 relative'
            }`}
          >
            <div className="visualization-header absolute top-0 left-0 right-0 px-6 py-4 text-xs font-semibold tracking-wider text-slate-500 uppercase z-10 border-b border-white/5 bg-bg-surface/80 backdrop-blur-sm">Visualization</div>
            <VisualizationCanvas 
              step={currentStep} 
              code={code} 
              isFullscreen={isFullscreen}
              onToggleFullscreen={() => setIsFullscreen(!isFullscreen)}
            />
          </div>

          {/* Right: Inspector */}
          <div className="w-[25%] panel-surface flex flex-col !p-0 overflow-hidden">
            <div className="px-6 py-4 text-xs font-semibold tracking-wider text-slate-500 uppercase border-b border-white/5 bg-bg-surface z-10">Inspector</div>
            <div className="flex-1 overflow-auto bg-bg-surface">
              <ExplanationPanel code={code} step={currentStep} previousStep={previousStep} />
            </div>
          </div>
        </div>

        {/* Bottom: Timeline */}
        <div className="h-32 panel-surface !p-0 flex flex-col overflow-hidden shrink-0">
          <Timeline 
            steps={steps} 
            currentIndex={currentStepIdx} 
            onNavigate={setCurrentStepIdx} 
          />
        </div>
      </div>
      <TestCaseModal 
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmitMethod={(method) => {
          setSelectedMethod(method);
          executeCode(undefined, method, true);
        }}
        onSubmitTestCase={(testCaseStr) => {
          executeCode(testCaseStr, selectedMethod || undefined, true);
        }}
        candidates={modalCandidates}
        params={modalParams}
        error={modalError}
        mode={modalMode}
      />
    </div>
  );
}
