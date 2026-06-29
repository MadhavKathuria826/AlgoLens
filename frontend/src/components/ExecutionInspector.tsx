export default function ExecutionInspector({ step, steps, currentStepIdx }: any) {
  return (
    <div className="flex-1 flex flex-col p-4 gap-6 overflow-y-auto">
      <div>
        <h3 className="text-sm font-semibold text-slate-400 mb-3 uppercase tracking-wider">Variables</h3>
        {step?.variables?.length ? (
          <div className="space-y-2">
            {step.variables.map((v: any) => (
              <div key={v.name} className="flex justify-between items-center text-sm p-2.5 bg-black/30 border border-white/5 rounded-lg shadow-sm">
                <span className="font-mono text-blue-400">{v.name}</span>
                <span className="font-mono text-emerald-400">{v.value}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-slate-500 italic p-2">No variables in scope.</div>
        )}
      </div>
      <div>
        <h3 className="text-sm font-semibold text-slate-400 mb-3 uppercase tracking-wider">Execution Log</h3>
        <div className="space-y-2">
          {step && (
             <div className="text-sm text-emerald-400 p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
               <div className="font-medium mb-1">Line {step.line_number} executed</div>
               <div className="text-xs text-emerald-400/70 uppercase tracking-widest">{step.event_type} event</div>
               {step.output && <div className="mt-2 pt-2 border-t border-emerald-500/20 text-emerald-300">{step.output}</div>}
             </div>
          )}
        </div>
      </div>
    </div>
  );
}
