import { motion } from 'framer-motion';

export default function LoopVisualizer({ data }: { data: any }) {
  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      className="glass border-purple-500/30 bg-purple-500/10 p-8 rounded-xl min-w-[250px] flex flex-col items-center gap-6 shadow-[0_0_30px_rgba(168,85,247,0.15)] my-8"
    >
      <div className="text-purple-400 text-sm uppercase tracking-widest font-bold">Loop Iteration</div>
      <div className="flex gap-6 items-center flex-wrap justify-center">
        {Object.entries(data.locals || {}).map(([k,v]: any) => (
          <div key={k} className="flex flex-col items-center">
            <span className="text-slate-400 font-mono text-sm mb-2">{k}</span>
            <motion.div 
              key={`${k}-${v}`} // Re-animate on change
              initial={{ scale: 0.5, rotate: -90 }}
              animate={{ scale: 1, rotate: 0 }}
              className="w-16 h-16 rounded-full border-2 border-purple-400 flex items-center justify-center text-2xl font-bold text-white shadow-[0_0_20px_rgba(168,85,247,0.4)]"
            >
              {v}
            </motion.div>
          </div>
        ))}
      </div>
    </motion.div>
  );
}
