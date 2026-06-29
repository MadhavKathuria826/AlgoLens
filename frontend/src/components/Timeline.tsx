export default function Timeline({ steps, currentIndex, onNavigate }: any) {
  return (
    <div className="h-full flex flex-col p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Execution Timeline</h3>
        <div className="text-xs text-slate-500 px-2 py-1 bg-black/30 rounded">{steps.length} frames</div>
      </div>
      <div className="flex-1 overflow-x-auto flex items-end gap-1.5 pb-2 custom-scrollbar">
        {steps.map((s: any, idx: number) => {
          const isCurrent = idx === currentIndex;
          const isPast = idx < currentIndex;
          // Simple visual heuristic for height
          const h = Math.max(20, Math.min(100, s.line_number * 8));
          
          return (
            <div 
              key={idx}
              onClick={() => onNavigate(idx)}
              className={`flex-shrink-0 w-6 rounded-t transition-all cursor-pointer relative group ${
                isCurrent ? 'bg-emerald-400' : 
                isPast ? 'bg-emerald-500/40 hover:bg-emerald-500/60' : 'bg-white/10 hover:bg-white/20'
              }`}
              style={{ height: `${h}%` }}
            >
              {/* Tooltip */}
              <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity bg-black text-xs text-white px-2 py-1 rounded whitespace-nowrap z-50 pointer-events-none">
                Step {idx + 1} (Line {s.line_number})
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
