import { motion } from 'framer-motion';

export default function ConditionVisualizer({ data }: { data: any }) {
  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.8 }}
      className="flex flex-col items-center my-12"
    >
      <div className="relative w-40 h-40 flex items-center justify-center">
        <motion.div 
          className="absolute inset-0 rotate-45 border-4 border-orange-500/50 bg-orange-500/10 shadow-[0_0_40px_rgba(249,115,22,0.3)]"
          animate={{ scale: [1, 1.05, 1], rotate: 45 }}
          transition={{ duration: 2, repeat: Infinity }}
        />
        <div className="z-10 flex flex-col items-center justify-center text-center p-3 select-none">
          {data?.raw_expression && (
            <div className="text-[10px] text-orange-500/60 font-mono font-medium max-w-[120px] truncate mb-1" title={data.raw_expression}>
              {data.raw_expression}
            </div>
          )}
          <div className="text-orange-400 font-mono text-xs sm:text-sm font-bold max-w-[120px] break-words leading-tight">
            {data?.expression || "Branch Evaluation"}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
