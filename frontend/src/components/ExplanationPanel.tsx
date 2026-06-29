import { motion } from 'framer-motion';

export default function ExplanationPanel({ code, step, previousStep }: any) {
  if (!step) {
    return (
      <div className="p-6 text-slate-500 flex items-center justify-center h-full text-sm">
        Run code to see execution details...
      </div>
    );
  }

  // 1. Current line code
  const codeLines = code.split('\n');
  const currentLineCode = step.line_number > 0 && step.line_number <= codeLines.length 
    ? codeLines[step.line_number - 1].trim() 
    : '';

  // 2. Extract Locals from current step and previous step
  const extractLocals = (s: any) => {
    if (!s) return {};
    let locals = {};
    if (s.locals) {
      Object.assign(locals, s.locals);
    }
    if (s.visualizations) {
      s.visualizations.forEach((v: any) => {
        if (v.type === 'Variable' || v.type === 'Loop') {
          Object.assign(locals, v.details.locals || v.details);
        }
      });
    }
    return locals;
  };

  const currentLocals: any = extractLocals(step);
  const previousLocals: any = extractLocals(previousStep);

  const filterLocals = (locals: any) => {
    return Object.fromEntries(
      Object.entries(locals).filter(([k, v]: any) => ((typeof v === 'string' && !v.startsWith('<function') && !v.startsWith('<module') && !v.startsWith('obj_')) || typeof v === 'number'))
    );
  };

  const filteredCurrent = filterLocals(currentLocals);
  const filteredPrevious = filterLocals(previousLocals);

  // Calculate State Changes
  const changes = [];
  for (const [k, v] of Object.entries(filteredCurrent)) {
    if (filteredPrevious[k] !== v) {
      changes.push({ name: k, old: filteredPrevious[k] || 'undefined', new: v });
    }
  }

  // Generate Explanation Heuristic
  let explanation = "Executing current line.";
  if (currentLineCode.includes('+=')) {
    explanation = "Adding the value to the running total.";
  } else if (currentLineCode.includes('-=')) {
    explanation = "Subtracting from the running total.";
  } else if (currentLineCode.startsWith('if ') || currentLineCode.startsWith('elif ')) {
    explanation = "Evaluating condition.";
  } else if (currentLineCode.startsWith('for ') || currentLineCode.startsWith('while ')) {
    explanation = "Advancing the loop to the next iteration.";
  } else if (currentLineCode.includes('=')) {
    explanation = "Updating variable assignment.";
  } else if (currentLineCode.startsWith('def ')) {
    explanation = "Defining function.";
  } else if (currentLineCode.startsWith('return ')) {
    explanation = "Returning value from function.";
  } else if (currentLineCode.includes('print(')) {
    explanation = "Printing output.";
  }

  return (
    <div className="flex flex-col h-full bg-[#050508] text-slate-300 font-sans p-6 overflow-y-auto w-full">
      <div className="px-1 py-2 text-xs font-semibold tracking-wider text-slate-500 uppercase border-b border-white/5 mb-6">What's Happening Now</div>
      
      {/* Current Line */}
      <div className="mb-8">
        <h3 className="text-[10px] text-slate-500 uppercase tracking-widest mb-3">Executing Code</h3>
        <motion.div 
          key={step.step_number}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          className="bg-blue-950/20 border-l-2 border-blue-500 p-3 rounded-r-lg font-mono text-sm text-blue-200"
        >
          {currentLineCode || "Starting execution..."}
        </motion.div>
      </div>

      {/* Explanation */}
      <div className="mb-8">
        <h3 className="text-[10px] text-slate-500 uppercase tracking-widest mb-3">Explanation</h3>
        <motion.div 
          key={`exp-${step.step_number}`}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-base text-slate-200 leading-relaxed font-light"
        >
          {explanation}
        </motion.div>
      </div>

      {/* State Changes */}
      {changes.length > 0 && (
        <div className="mb-8">
          <h3 className="text-[10px] text-emerald-500/80 uppercase tracking-widest mb-3">State Changes</h3>
          <div className="flex flex-col gap-2">
            {changes.map(c => (
              <motion.div 
                key={c.name} 
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex items-center gap-3 bg-emerald-950/20 border border-emerald-900/30 p-2.5 rounded-lg"
              >
                <span className="font-mono text-emerald-100/70 text-sm">{c.name}:</span>
                <div className="flex items-center gap-2 font-mono text-sm">
                  <span className="text-slate-500 line-through">{String(c.old)}</span>
                  <span className="text-emerald-500">→</span>
                  <span className="text-emerald-400 font-bold">{String(c.new)}</span>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Running Variables */}
      {Object.keys(filteredCurrent).length > 0 && (
        <div>
          <h3 className="text-[10px] text-slate-500 uppercase tracking-widest mb-3">Running Variables</h3>
          <div className="flex flex-col gap-2">
            {Object.entries(filteredCurrent).map(([k, v]: any) => (
              <div key={k} className="flex justify-between items-center bg-slate-900/50 px-3 py-2 rounded-lg border border-white/5">
                <span className="font-mono text-slate-400 text-xs">{k}</span>
                <span className="font-mono text-blue-300 text-sm">{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
