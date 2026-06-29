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
        <div className="z-10 text-orange-400 font-mono text-xl font-bold text-center">
          Branch<br/>Evaluation
        </div>
      </div>
    </motion.div>
  );
}
