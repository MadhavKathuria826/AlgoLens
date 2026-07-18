import { useRef, useEffect, useMemo } from 'react';
import GraphTreeRenderer, { GraphNode, GraphEdge, GraphPointer, GraphFlow } from './GraphTreeRenderer';

type LayoutNode = {
  id: string;
  x: number;
  y: number;
  val: any;
  left?: string;
  right?: string;
};

export default function TreeVisualizer({ heap, locals, step }: { heap: any; locals: any; step?: any }) {
  const avlMetadata = step?.visualizations?.find((v: any) => v.type === 'AVL_METADATA')?.details;
  const rbtMetadata = step?.visualizations?.find((v: any) => v.type === 'RBT_METADATA')?.details;
  const prevPointersRef = useRef<Record<string, string>>({});
  const visitedNodesRef = useRef<Set<string>>(new Set());
  const activeFlowsRef = useRef<{ id: string; source: string; target: string; }[]>([]);

  // 1. Extract active tree nodes from heap
  const nodes: Record<string, any> = {};
  const inDegree: Record<string, number> = {};
  for (const [k, v] of Object.entries(heap || {})) {
    if (v && typeof v === 'object' && (v as any).fields && (('left' in (v as any).fields) || ('right' in (v as any).fields))) {
      nodes[k] = v;
      inDegree[k] = inDegree[k] || 0;
      const left = (v as any).fields.left;
      const right = (v as any).fields.right;
      if (left && left !== 'None') {
        inDegree[left] = (inDegree[left] || 0) + 1;
      }
      if (right && right !== 'None') {
        inDegree[right] = (inDegree[right] || 0) + 1;
      }
    }
  }

  // 2. Compute Layout via Inorder Traversal
  const layout = useMemo(() => {
    let currentX = 0;
    const HORIZONTAL_SPACING = 60;
    const VERTICAL_SPACING = 80;
    const res: Record<string, LayoutNode> = {};
    const cycleVisited = new Set<string>();

    const traverse = (nodeId: string, depth: number) => {
      if (cycleVisited.has(nodeId)) return;
      cycleVisited.add(nodeId);

      const node = nodes[nodeId];
      if (!node) return;

      const left = node.fields.left;
      const right = node.fields.right;

      if (left && left !== 'None') traverse(left, depth + 1);

      res[nodeId] = {
        id: nodeId,
        x: currentX,
        y: depth * VERTICAL_SPACING,
        val: node.fields.val,
        left: left !== 'None' ? left : undefined,
        right: right !== 'None' ? right : undefined
      };
      currentX += HORIZONTAL_SPACING;

      if (right && right !== 'None') traverse(right, depth + 1);
    };

    // Find roots
    const roots = Object.keys(nodes).filter(k => inDegree[k] === 0);
    // If no roots but nodes exist (e.g., pure cycle), just pick the first node
    if (roots.length === 0 && Object.keys(nodes).length > 0) {
      roots.push(Object.keys(nodes)[0]);
    }

    for (const root of roots) {
      traverse(root, 0);
      currentX += HORIZONTAL_SPACING; // gap between separate trees
    }

    if (Object.keys(res).length === 0) {
      return { layout: res, width: '100%', height: '100%' };
    }

    // Center layout
    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;
    for (const node of Object.values(res)) {
      minX = Math.min(minX, node.x);
      maxX = Math.max(maxX, node.x);
      minY = Math.min(minY, node.y);
      maxY = Math.max(maxY, node.y);
    }

    // Add padding
    for (const node of Object.values(res)) {
      node.x = node.x - minX + 80;
      node.y = node.y - minY + 80;
    }

    return { layout: res, width: maxX - minX + 160, height: maxY - minY + 160 };
  }, [nodes]);

  // 3. Track Pointer Traversal
  const pointers: Record<string, string> = {};
  for (const [k, v] of Object.entries(locals || {})) {
    if (typeof v === 'string' && v.startsWith('obj_') && nodes[v]) {
      // Exclude generic internal pointers if needed, but normally all are good
      pointers[k] = v;
    }
  }

  // Identify landed nodes and edge traversals
  const landedNodes = new Set<string>();
  const newFlows: { id: string; source: string; target: string; }[] = [];

  for (const [pName, target] of Object.entries(pointers)) {
    const prevTarget = prevPointersRef.current[pName];
    if (prevTarget !== target) {
      landedNodes.add(target);
      visitedNodesRef.current.add(target);
      
      if (prevTarget && layout.layout[prevTarget]) {
        const pNode = layout.layout[prevTarget];
        if (pNode.left === target || pNode.right === target) {
          // Traversed an edge
          newFlows.push({ id: `flow-${Math.random()}`, source: prevTarget, target });
        }
      }
    } else {
      // Just currently parked on it
      visitedNodesRef.current.add(target);
    }
  }

  useEffect(() => {
    prevPointersRef.current = pointers;
    activeFlowsRef.current = newFlows;
  });

  const nodePointers: Record<string, string[]> = {};
  for (const [pName, target] of Object.entries(pointers)) {
    if (!nodePointers[target]) nodePointers[target] = [];
    nodePointers[target].push(pName);
  }

  // 4. Compute Active Path Nodes (Option B)
  const activePathNodes = new Set<string>();
  const pathCycleVisited = new Set<string>();

  const findPaths = (nodeId: string, currentPath: string[]) => {
    if (pathCycleVisited.has(nodeId)) return false;
    pathCycleVisited.add(nodeId);

    const node = nodes[nodeId];
    if (!node) return false;

    currentPath.push(nodeId);

    let hasPointer = false;
    for (const [pName, target] of Object.entries(pointers)) {
      if (target === nodeId && pName.toLowerCase() !== 'self') {
        hasPointer = true;
      }
    }

    let childHasPointer = false;
    const left = node.fields.left;
    if (left && left !== 'None') {
      if (findPaths(left, currentPath)) childHasPointer = true;
    }
    const right = node.fields.right;
    if (right && right !== 'None') {
      if (findPaths(right, currentPath)) childHasPointer = true;
    }

    if (hasPointer || childHasPointer) {
      for (const p of currentPath) {
        activePathNodes.add(p);
        visitedNodesRef.current.add(p); // Mark path as permanently visited
      }
    }

    currentPath.pop();
    return hasPointer || childHasPointer;
  };

  const pathRoots = Object.keys(nodes).filter(k => inDegree[k] === 0);
  if (pathRoots.length === 0 && Object.keys(nodes).length > 0) {
    pathRoots.push(Object.keys(nodes)[0]);
  }
  for (const root of pathRoots) {
    findPaths(root, []);
  }

  // 5. Map to GraphTreeRenderer Format
  const graphNodes: GraphNode[] = Object.values(layout.layout).map(node => {
    const isNew = avlMetadata?.new_node_id === node.id || rbtMetadata?.new_node_id === node.id || heap[node.id]?.fields?.is_new;
    const isUnbalanced = avlMetadata?.unbalanced_node === node.id;
    const isRotationPivot = (avlMetadata?.rotation_nodes?.includes(node.id) && node.id !== avlMetadata?.unbalanced_node) ||
                            (rbtMetadata?.rotation_nodes?.includes(node.id));
    const balanceFactor = heap[node.id]?.fields?.balance_factor;
    const isRemoved = avlMetadata?.removed_node === node.id || heap[node.id]?.fields?.is_removed;
    const isSwapped = avlMetadata?.successor_swap_node === node.id || heap[node.id]?.fields?.is_swapped;
    const color = heap[node.id]?.fields?.color;
    const isDoubleRed = rbtMetadata?.double_red_node === node.id || rbtMetadata?.double_red_parent === node.id;

    return {
      id: node.id,
      x: node.x,
      y: node.y,
      val: node.val,
      isLanded: landedNodes.has(node.id) || isNew,
      isCurrentTarget: !!nodePointers[node.id] || isUnbalanced || isRemoved || isSwapped || isDoubleRed,
      isActivePath: activePathNodes.has(node.id) || avlMetadata?.insertion_path?.includes(node.id) || rbtMetadata?.insertion_path?.includes(node.id),
      isVisited: visitedNodesRef.current.has(node.id),
      balanceFactor,
      isNew,
      isUnbalanced,
      isRotationPivot,
      isRemoved,
      isSwapped,
      color: color === 'RED' || color === 'BLACK' ? color : undefined,
      isDoubleRed
    };
  });

  const graphEdges: GraphEdge[] = [];
  for (const node of Object.values(layout.layout)) {
    if (node.left && layout.layout[node.left]) {
      graphEdges.push({
        id: `${node.id}-${node.left}`,
        sourceId: node.id,
        targetId: node.left,
        isActivePath: activePathNodes.has(node.left),
        isVisited: visitedNodesRef.current.has(node.left)
      });
    }
    if (node.right && layout.layout[node.right]) {
      graphEdges.push({
        id: `${node.id}-${node.right}`,
        sourceId: node.id,
        targetId: node.right,
        isActivePath: activePathNodes.has(node.right),
        isVisited: visitedNodesRef.current.has(node.right)
      });
    }
  }

  const graphPointers: GraphPointer[] = Object.entries(pointers).map(([pName, targetId]) => ({
    name: pName,
    targetId
  }));

  const graphFlows: GraphFlow[] = newFlows.map(flow => ({
    id: flow.id,
    sourceId: flow.source,
    targetId: flow.target
  }));

  return (
    <div className="w-full h-full relative overflow-auto flex flex-col items-center justify-center p-8 bg-slate-900/50 rounded-xl border border-slate-700/50">
      <div className="absolute top-4 right-4 text-[10px] font-mono text-slate-500 bg-slate-950/80 px-2 py-0.5 rounded border border-slate-800 shadow-sm z-30">
        BUILD-22
      </div>
      {(avlMetadata?.status_message || rbtMetadata?.status_message) && (
        <div className="mb-4 px-4 py-2 bg-slate-800/80 border border-slate-700 text-cyan-300 rounded-lg text-sm font-medium tracking-wide shadow-[0_0_15px_rgba(34,211,238,0.1)]">
          {avlMetadata?.status_message || rbtMetadata?.status_message}
        </div>
      )}
      <GraphTreeRenderer
        nodes={graphNodes}
        edges={graphEdges}
        pointers={graphPointers}
        activeFlows={graphFlows}
        layoutWidth={layout.width}
        layoutHeight={layout.height}
      />
    </div>
  );
}
