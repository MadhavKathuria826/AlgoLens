import { useMemo } from 'react';
import { motion } from 'framer-motion';

type TrieNodeData = {
  id: string;
  char: string;
  is_end_of_word: boolean;
  is_active: boolean;
  children?: TrieNodeData[];
};

type PositionedNode = {
  id: string;
  char: string;
  is_end_of_word: boolean;
  is_active: boolean;
  x: number;
  y: number;
  parentId?: string;
};

export default function TrieVisualizer({ step }: { step?: any }) {
  const trieMetadata = step?.visualizations?.find((v: any) => v.type === 'TRIE_METADATA')?.details;
  const trieTrees: TrieNodeData[] = trieMetadata?.trie_trees || [];
  const statusMessage = trieMetadata?.status_message;

  const { nodes, edges, width, height } = useMemo(() => {
    if (!trieTrees || trieTrees.length === 0) {
      return { nodes: [], edges: [], width: 400, height: 300 };
    }

    const posNodes: PositionedNode[] = [];
    const posEdges: { id: string; sourceX: number; sourceY: number; targetX: number; targetY: number; char: string; is_active: boolean }[] = [];

    let currentX = 80;
    const VERTICAL_SPACING = 95;
    const HORIZONTAL_SPACING = 70;

    const traverse = (node: TrieNodeData, depth: number, parentId?: string, parentX?: number, parentY?: number) => {
      const children = node.children || [];
      const numChildren = children.length;

      let nodeX: number;
      if (numChildren === 0) {
        nodeX = currentX;
        currentX += HORIZONTAL_SPACING;
      } else {
        const startX = currentX;
        const childXs: number[] = [];

        children.forEach(child => {
          const childX = traverse(child, depth + 1, node.id, 0, (depth + 1) * VERTICAL_SPACING);
          childXs.push(childX);
        });

        // Center parent above children
        nodeX = (childXs[0] + childXs[childXs.length - 1]) / 2;
      }

      const nodeY = depth * VERTICAL_SPACING + 80;

      posNodes.push({
        id: node.id,
        char: node.char,
        is_end_of_word: node.is_end_of_word,
        is_active: node.is_active,
        x: nodeX,
        y: nodeY,
        parentId
      });

      if (parentId && parentX !== undefined && parentY !== undefined) {
        posEdges.push({
          id: `${parentId}-${node.id}`,
          sourceX: parentX,
          sourceY: parentY,
          targetX: nodeX,
          targetY: nodeY,
          char: node.char,
          is_active: node.is_active
        });
      }

      return nodeX;
    };

    // Calculate layout for all roots
    trieTrees.forEach(root => {
      traverse(root, 0);
      currentX += HORIZONTAL_SPACING;
    });

    // Adjust Y coordinates of edges after nodes have final positions
    const nodeMap = new Map(posNodes.map(n => [n.id, n]));
    const finalEdges = posEdges.map(edge => {
      const source = nodeMap.get(edge.id.split('-')[0]);
      const target = nodeMap.get(edge.id.split('-')[1]);
      return {
        ...edge,
        sourceX: source ? source.x : edge.sourceX,
        sourceY: source ? source.y : edge.sourceY,
        targetX: target ? target.x : edge.targetX,
        targetY: target ? target.y : edge.targetY
      };
    });

    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;
    posNodes.forEach(n => {
      minX = Math.min(minX, n.x);
      maxX = Math.max(maxX, n.x);
      minY = Math.min(minY, n.y);
      maxY = Math.max(maxY, n.y);
    });

    const padding = 100;
    const finalWidth = Math.max(600, maxX - minX + padding * 2);
    const finalHeight = Math.max(400, maxY - minY + padding * 2);

    return { nodes: posNodes, edges: finalEdges, width: finalWidth, height: finalHeight };
  }, [trieTrees]);

  if (!trieTrees || trieTrees.length === 0) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center text-slate-400 font-mono text-sm">
        No active Trie nodes detected in execution heap.
      </div>
    );
  }

  return (
    <div className="w-full h-full relative overflow-auto flex flex-col items-center justify-center p-8 bg-slate-900/50 rounded-xl border border-slate-700/50">
      <div className="absolute top-4 right-4 text-[10px] font-mono text-emerald-400 bg-slate-950/80 px-2.5 py-1 rounded border border-emerald-500/30 shadow-sm z-30 flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
        TRIE (PREFIX TREE)
      </div>

      {statusMessage && (
        <div className="mb-4 px-4 py-2 bg-slate-800/90 border border-emerald-500/30 text-emerald-300 rounded-lg text-sm font-medium tracking-wide shadow-[0_0_15px_rgba(16,185,129,0.15)] z-20">
          {statusMessage}
        </div>
      )}

      <div className="relative" style={{ width: `${width}px`, height: `${height}px` }}>
        <svg className="absolute inset-0 w-full h-full pointer-events-none z-10">
          <defs>
            <linearGradient id="edge-grad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#334155" />
              <stop offset="100%" stopColor="#1e293b" />
            </linearGradient>
            <linearGradient id="edge-active-grad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#10b981" />
              <stop offset="100%" stopColor="#06b6d4" />
            </linearGradient>
          </defs>
          {edges.map(edge => (
            <g key={edge.id}>
              <line
                x1={edge.sourceX}
                y1={edge.sourceY}
                x2={edge.targetX}
                y2={edge.targetY}
                stroke={edge.is_active ? "url(#edge-active-grad)" : "#334155"}
                strokeWidth={edge.is_active ? 3 : 2}
                strokeDasharray={edge.is_active ? "4 4" : "none"}
                className={edge.is_active ? "animate-[dash_1s_linear_infinite]" : ""}
              />
            </g>
          ))}
        </svg>

        {nodes.map(node => {
          return (
            <motion.div
              key={node.id}
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 0.2 }}
              style={{
                position: 'absolute',
                left: `${node.x}px`,
                top: `${node.y}px`,
                transform: 'translate(-50%, -50%)'
              }}
              className="z-20 flex flex-col items-center justify-center cursor-pointer"
            >
              <div
                className={`w-12 h-12 rounded-full flex items-center justify-center text-sm font-bold font-mono transition-all duration-300 shadow-lg relative ${
                  node.is_active
                    ? 'bg-gradient-to-br from-emerald-500 to-cyan-600 text-white ring-4 ring-emerald-400/50 shadow-[0_0_20px_rgba(16,185,129,0.5)] scale-110'
                    : node.is_end_of_word
                    ? 'bg-slate-800 border-2 border-emerald-400 text-emerald-300 shadow-[0_0_12px_rgba(16,185,129,0.3)]'
                    : 'bg-slate-800/90 border border-slate-600 text-slate-200 hover:border-slate-400'
                }`}
              >
                {node.char}

                {node.is_end_of_word && (
                  <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500 text-[9px] font-bold text-slate-950 shadow-md" title="End of Word">
                    ✓
                  </span>
                )}
              </div>
              <span className="mt-1 text-[10px] font-mono text-slate-400 bg-slate-950/60 px-1.5 py-0.5 rounded border border-slate-800">
                {node.char === 'ROOT' ? 'Root' : `"${node.char}"`}
              </span>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
