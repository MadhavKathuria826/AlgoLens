"use client";

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import CodeEditor from '@/components/CodeEditor';
import VisualizationCanvas from '@/components/VisualizationCanvas';
import ExplanationPanel from '@/components/ExplanationPanel';
import Timeline from '@/components/Timeline';
import axios from 'axios';
import { Play, RotateCcw, StepForward, StepBack, Loader2, Pause, SkipBack } from 'lucide-react';
import { SemanticAnalyzer } from '@/utils/semanticAnalyzer';
import ThemePopover from '@/components/ThemePopover';
import LanguageSelector from '@/components/LanguageSelector';
import ExportButton from '@/components/ExportButton';
import SettingsModal from '@/components/SettingsModal';
import TestCaseModal from '@/components/TestCaseModal';
import { useSettings } from '@/contexts/SettingsContext';
import { useIsMobile } from '@/hooks/useIsMobile';


const DEFAULT_STARTER_CODE: Record<string, string> = {
  python:
    "# Welcome to AlgoLens Studio\n" +
    "# Write or paste your own Python code here, then click Run to visualize!\n\n" +
    "def bubble_sort(arr):\n" +
    "    n = len(arr)\n" +
    "    for i in range(n):\n" +
    "        for j in range(0, n - i - 1):\n" +
    "            if arr[j] > arr[j + 1]:\n" +
    "                # Swap elements\n" +
    "                arr[j], arr[j + 1] = arr[j + 1], arr[j]\n" +
    "    return arr\n\n" +
    "arr = [64, 34, 25, 12, 22]\n" +
    "bubble_sort(arr)\n",
  cpp:
    "// Welcome to AlgoLens Studio (C++)\n" +
    "// Write or paste your own C++ code here, then click Run to visualize!\n\n" +
    "int sum_vector() {\n" +
    "    std::vector<int> nums;\n" +
    "    nums.push_back(10);\n" +
    "    nums.push_back(20);\n" +
    "    nums.push_back(30);\n" +
    "    int total = 0;\n" +
    "    for (int i = 0; i < nums.size(); i = i + 1) {\n" +
    "        total = total + nums[i];\n" +
    "    }\n" +
    "    return total;\n" +
    "}\n"
};

function StudioInner({ onBack }: { onBack?: () => void }) {
  const { settings, updateSettings } = useSettings();
  const [code, setCode] = useState(() => {
    const lang = settings.language || 'python';
    return DEFAULT_STARTER_CODE[lang] || DEFAULT_STARTER_CODE.python;
  });
  const [steps, setSteps] = useState<any[]>([]);
  const [recurrenceRelations, setRecurrenceRelations] = useState<string[]>([]);
  const prevLanguageRef = useRef(settings.language);

  // Switch starter code when language changes, unless user has typed custom code
  useEffect(() => {
    const currentLang = settings.language || 'python';
    if (prevLanguageRef.current !== currentLang) {
      prevLanguageRef.current = currentLang;

      const isCurrentCodeEmpty = !code || code.trim() === "";
      const isCurrentCodeDefault = Object.values(DEFAULT_STARTER_CODE).some(
        starter => starter.trim() === code.trim()
      );

      if (isCurrentCodeEmpty || isCurrentCodeDefault) {
        setCode(DEFAULT_STARTER_CODE[currentLang] || DEFAULT_STARTER_CODE.python);
        setSteps([]);
        setRecurrenceRelations([]);
        setCurrentStepIdx(0);
      }
    }
  }, [settings.language, code]);

  // Expose global callback for Puppeteer testing to inject custom code
  useEffect(() => {
    (window as any).setStudioCode = (newCode: string) => {
      setCode(newCode);
    };
    (window as any).runStudioCode = (overrideCode?: string) => {
      setSelectedMethod(null);
      executeCode(undefined, undefined, false, overrideCode);
    };
    return () => {
      delete (window as any).setStudioCode;
      delete (window as any).runStudioCode;
    };
  }, [code, settings, selectedMethod]);

  const [currentStepIdx, setCurrentStepIdx] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  
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
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const mockName = params.get('mock');
    const stepStr = params.get('step');
    if (mockName) {
      setIsLoading(true);
      fetch(`/mocks/${mockName}.json`)
        .then(res => res.json())
        .then(data => {
          setCode(data.code);
          setSteps(data.steps);
          if (stepStr) {
            setCurrentStepIdx(parseInt(stepStr, 10));
          }
          setIsLoading(false);
        })
        .catch(err => {
          console.error("Failed to load mock", err);
          setIsLoading(false);
        });
    }
  }, []);

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

  const executeCode = async (optionalTestCase?: string, optionalSelectedMethod?: string, isFromModal: boolean = false, overrideCode?: string) => {
    setIsLoading(true);
    setIsPlaying(false);
    setModalError(null);
    const targetCode = overrideCode || code;
    try {
      const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
      const res = await axios.post(`${API_URL}/api/execute`, { 
        code: targetCode, 
        language: settings.language,
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
        setRecurrenceRelations(res.data.recurrence_relations || []);
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
            className="text-xl font-bold tracking-tight text-[#00e5ff]"
          >
            AlgoLens
          </Link>
          <div className="h-4 w-px bg-white/10 mx-2" />
          <span className="text-slate-300 font-medium">Studio</span>
        </div>
        <div className="flex items-center gap-2">
          <LanguageSelector />
          <ThemePopover />
          <ExportButton disabled={steps.length === 0} />
          <SettingsModal />
        </div>
      </nav>

      <div className="flex flex-col flex-1 overflow-hidden p-6 gap-6">
        {/* Top Controls (not in navbar) */}
        <div className="panel-surface py-3 px-6 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-4">
            {/* EXTENSION POINT: Reintroduce Examples / Preset Selector dropdown here if needed in the future */}

            <button 
              onClick={handleRun}
              disabled={isLoading}
              data-testid="run-button"
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
                  data-testid="next-button"
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
              onClick={() => { setSteps([]); setRecurrenceRelations([]); setCurrentStepIdx(0); setIsPlaying(false); }}
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
            <div className="visualization-header shrink-0 px-6 py-4 text-xs font-semibold tracking-wider text-slate-500 uppercase border-b border-white/5 bg-bg-surface/80 backdrop-blur-sm z-10">Visualization</div>
            <div className="flex-1 relative overflow-hidden w-full h-full">
              <VisualizationCanvas 
                step={currentStep} 
                steps={steps}
                currentStepIdx={currentStepIdx}
                code={code} 
                isFullscreen={isFullscreen}
                onToggleFullscreen={() => setIsFullscreen(!isFullscreen)}
                recurrenceRelations={recurrenceRelations}
              />
            </div>
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
        <div className="h-32 panel-surface !p-0 flex flex-col overflow-hidden shrink-0 w-full min-w-0">
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

export default function Studio({ onBack }: { onBack?: () => void }) {
  const isMobile = useIsMobile();

  if (isMobile === null) {
    return (
      <div className="w-screen h-screen bg-[var(--color-bg-app)] flex items-center justify-center text-white select-none">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 animate-spin text-[#ffa116]" />
          <span className="text-xs font-mono text-[#8e8e95] tracking-[2px] uppercase">INDEXING INTERNALS...</span>
        </div>
      </div>
    );
  }

  if (isMobile) {
    return (
      <div className="w-screen h-screen bg-[var(--color-bg-app)] flex flex-col items-center justify-center p-6 text-center text-[#8e8e95] select-none">
        <div className="text-white text-2xl font-bold mb-4 tracking-tight">
          Desktop experience only
        </div>
        <p className="max-w-md text-base mb-8 font-light leading-relaxed">
          AlgoLens Studio is currently optimized for laptops and desktop computers. Please open it on a larger screen for the full interactive visualization experience.
        </p>
        <button
          onClick={onBack}
          className="px-6 py-2.5 border border-white text-white font-bold rounded-[1000px] hover:bg-white hover:text-[var(--color-bg-app)] transition-colors"
        >
          Go Back
        </button>
      </div>
    );
  }

  return <StudioInner onBack={onBack} />;
}
