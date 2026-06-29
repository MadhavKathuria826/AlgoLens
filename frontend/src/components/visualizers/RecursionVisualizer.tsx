import { motion, AnimatePresence } from 'framer-motion';

export default function RecursionVisualizer({ data }: { data: any }) {
  const rootNodes = data.nodes.filter((n: any) => !data.nodes.some((other: any) => other.id === n.parent_id));

  const renderNode = (node: any) => {
    const children = data.nodes.filter((n: any) => n.parent_id === node.id);
    const argsStr = Object.values(node.args || {}).join(', ');
    const hasReturned = node.return_val !== null;

    return (
      <div key={node.id} className="flex flex-col items-center">
        {/* Node Body */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative z-10"
        >
          <div className={`
            px-3 py-1.5 rounded-md font-mono text-xs sm:text-sm border flex items-center justify-center gap-2 min-w-[80px] transition-colors duration-300
            ${hasReturned 
              ? 'bg-emerald-950/50 border-emerald-500/50 text-emerald-300' 
              : node.is_active 
                ? 'bg-blue-900/60 border-blue-400 text-blue-100 ring-1 ring-blue-500/40'
                : 'bg-slate-800/80 border-slate-600 text-slate-400'}
          `}>
            <span>
              {node.func}(<span className={hasReturned ? 'text-emerald-400' : 'text-blue-300'}>{argsStr}</span>)
            </span>
            
            {hasReturned && (
              <div className="flex items-center gap-1 font-bold text-emerald-400 bg-emerald-950/50 px-1.5 py-0.5 rounded border border-emerald-500/30">
                <span className="text-emerald-500/80 text-[10px]">→</span>
                <span>{node.return_val}</span>
              </div>
            )}
          </div>
        </motion.div>

        {/* Children Subtree */}
        {children.length > 0 && (
          <>
            {/* Edge down from parent to the horizontal connector */}
            <div 
              className={`w-px h-5 ${
                children.some((c:any) => c.return_val !== null || c.is_returning) 
                  ? 'bg-emerald-500/60' 
                  : 'bg-slate-600'
              }`}
            />
            
            {/* Children container */}
            <div className="flex relative justify-center">
              {children.map((child: any, index: number) => (
                <div key={child.id} className="flex flex-col items-center px-2 sm:px-4 relative">
                  
                  {/* Horizontal Connector Line */}
                  {children.length > 1 && (
                    <div 
                      className={`absolute top-0 h-px ${
                        child.return_val !== null || child.is_returning 
                          ? 'bg-emerald-500/60' 
                          : 'bg-slate-600'
                      } ${
                        index === 0 
                          ? 'left-1/2 right-0' 
                          : index === children.length - 1 
                            ? 'left-0 right-1/2' 
                            : 'left-0 right-0'
                      }`}
                    />
                  )}
                  
                  {/* Vertical line from horizontal connector down to child */}
                  {children.length > 1 && (
                    <div 
                      className={`w-px h-5 ${
                        child.return_val !== null || child.is_returning 
                          ? 'bg-emerald-500/60' 
                          : 'bg-slate-600'
                      }`}
                    />
                  )}

                  {/* Render the child subtree recursively */}
                  {renderNode(child)}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    );
  };

  return (
    <div className="flex flex-col items-center justify-start w-full h-full p-4 sm:p-8 overflow-auto bg-[#0f172a]">
      <div className="text-slate-400 font-mono text-xs tracking-widest uppercase mb-4 font-semibold bg-slate-800/50 px-3 py-1.5 rounded border border-slate-700/50">
        Recursion Tree: {data.func}
      </div>

      <div className="flex justify-center items-start min-w-max pb-16">
        {rootNodes.map(renderNode)}
      </div>
    </div>
  );
}
