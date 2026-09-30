export default function ExecutionInspector({ step, steps, currentStepIdx, events = [], stdout = '' }: any) {
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

      {events && events.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-slate-400 mb-3 uppercase tracking-wider">Event Protocol (M8)</h3>
          <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg text-xs space-y-1.5 font-mono">
            <div className="flex justify-between text-blue-300">
              <span>Universal Events:</span>
              <span className="font-bold text-blue-400">{events.length}</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Active Step:</span>
              <span>{currentStepIdx + 1} / {steps?.length || 0}</span>
            </div>
            {step?.event_type && (
              <div className="flex justify-between text-slate-400">
                <span>Protocol Frame:</span>
                <span className="text-emerald-400 uppercase">{step.event_type}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {stdout && (
        <div>
          <h3 className="text-sm font-semibold text-slate-400 mb-3 uppercase tracking-wider">Program Stdout</h3>
          <pre className="text-xs font-mono p-3 bg-black/40 border border-white/5 rounded-lg text-slate-300 whitespace-pre-wrap">
            {stdout}
          </pre>
        </div>
      )}

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
