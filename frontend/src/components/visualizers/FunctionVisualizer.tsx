import { motion } from 'framer-motion';

export default function FunctionVisualizer({ data }: { data: any }) {
  const argsStr = Object.entries(data.args || {}).map(([k,v]) => `${k} = ${v}`).join('\n');
  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.9, y: 20 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.9 }}
      className="glass border-pink-500/30 bg-pink-500/10 p-6 rounded-xl min-w-[200px] flex flex-col gap-4 shadow-[0_0_30px_rgba(236,72,153,0.15)] my-8"
    >
      <div className="text-pink-400 font-mono text-xl border-b border-pink-500/20 pb-2 tracking-wider flex items-center justify-between">
        <span>{data.func}()</span>
        <span className="text-xs bg-pink-500/20 px-2 py-1 rounded text-pink-300">Frame</span>
      </div>
      <pre className="text-slate-300 font-mono text-lg whitespace-pre-wrap">
        {argsStr || "No arguments"}
      </pre>
    </motion.div>
  );
}
