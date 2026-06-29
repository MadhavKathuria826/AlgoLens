import * as fs from 'fs';
import { SemanticAnalyzer } from '../src/utils/semanticAnalyzer';

const code = `
import heapq

h = []

heapq.heappush(h, 5)
heapq.heappush(h, 10)
heapq.heappush(h, 3)
heapq.heappush(h, 8)
`;
const codeLines = code.split('\n');
const steps = JSON.parse(fs.readFileSync('../trace_output.json', 'utf8'));

const buildSemanticInputs = (s: any) => {
  let inputs: any = {};
  if (s && s.locals) Object.assign(inputs, s.locals);
  if (s && s.visualizations) {
    s.visualizations.forEach((v: any) => {
      if (v.type === 'Array' && v.details && v.details.name) inputs[v.details.name] = v.details.value;
    });
  }
  return inputs;
};

const globalAnalyzer = new SemanticAnalyzer();
const objIdRoles: Record<string, any> = {};

steps.forEach((step: any, idx: number) => {
  const prevStep = idx > 0 ? steps[idx - 1] : null;
  globalAnalyzer.analyzeFrame(buildSemanticInputs(step), buildSemanticInputs(prevStep), codeLines[step.line_number - 1] || '');

  if (step.visualizations) {
     const currentMem = globalAnalyzer.getMemory();
     step.visualizations.forEach((v: any) => {
        if (v.type === 'Array' && v.details && v.details.name && v.details.obj_id) {
           const mem = currentMem[v.details.name];
           if (mem && mem.primaryContainerRole !== 'UNKNOWN' && mem.primaryContainerRole !== 'ARRAY') {
               if (!objIdRoles[v.details.obj_id]) objIdRoles[v.details.obj_id] = mem;
               if (mem.primaryContainerRole === 'HEAP') objIdRoles[v.details.obj_id] = mem;
           }
        }
     });
  }
});
const globalSemanticMemory = JSON.parse(JSON.stringify(globalAnalyzer.getMemory()));

const analyzer = new SemanticAnalyzer();
const stepsWithSemantics = steps.map((step: any, idx: number) => {
  const prevStep = idx > 0 ? steps[idx - 1] : null;
  const currentInputs = buildSemanticInputs(step);
  analyzer.analyzeFrame(currentInputs, buildSemanticInputs(prevStep), codeLines[step.line_number - 1] || '');
  const localMemory = JSON.parse(JSON.stringify(analyzer.getMemory()));

  for (const k of Object.keys(localMemory)) {
     let globalId = globalSemanticMemory[k];
     const vis = step.visualizations?.find((v: any) => v.type === 'Array' && v.details?.name === k);
     if (vis && vis.details.obj_id && objIdRoles[vis.details.obj_id]) {
         globalId = objIdRoles[vis.details.obj_id];
     }
     if (globalId && Array.isArray(currentInputs[k])) {
        localMemory[k].primaryContainerRole = globalId.primaryContainerRole;
     }
  }
  return { ...step, semanticMemory: localMemory };
});

stepsWithSemantics.forEach((step: any, idx: number) => {
  if (step.visualizations.length > 0) {
    const v = step.visualizations[0];
    const varName = v.details.name || 'N/A';
    const values = v.details.value || [];
    let mountedComponent = 'N/A';
    
    if (varName !== 'N/A' && step.semanticMemory && step.semanticMemory[varName]) {
      const primaryRole = step.semanticMemory[varName].primaryContainerRole;
      if (v.type === 'Array' && primaryRole === 'HEAP') mountedComponent = 'HeapVisualizer';
    }
    
    const idMapTree = new Map<any, number>();
    const nodeIds = values.map((val: any) => {
       const count = idMapTree.get(val) || 0;
       idMapTree.set(val, count + 1);
       return `heap-node-${val}-${count}`;
    });

    const HORIZONTAL_SPACING = 60;
    const VERTICAL_SPACING = 80;

    const resX: number[] = [];
    const resY: number[] = [];
    let currentX = 0;

    const traverse = (i: number, depth: number) => {
      if (i >= values.length) return;
      traverse(2 * i + 1, depth + 1);
      resX[i] = currentX;
      resY[i] = depth * VERTICAL_SPACING;
      currentX += HORIZONTAL_SPACING;
      traverse(2 * i + 2, depth + 1);
    };

    if (values.length > 0) traverse(0, 0);

    let minX = Infinity, maxX = -Infinity;
    let minY = Infinity, maxY = -Infinity;
    for (let i = 0; i < values.length; i++) {
      minX = Math.min(minX, resX[i]);
      maxX = Math.max(maxX, resX[i]);
      minY = Math.min(minY, resY[i]);
      maxY = Math.max(maxY, resY[i]);
    }

    const layoutWidth = values.length > 0 ? maxX - minX + 160 : '100%';
    const computedTreeHeight = values.length > 0 ? maxY - minY + 160 : 320;
    
    if (mountedComponent === 'HeapVisualizer') {
      console.log(`Frame ${idx.toString().padStart(2)} | values=${JSON.stringify(values)} | layoutWidth=${layoutWidth} layoutHeight=${computedTreeHeight}`);
      values.forEach((v: any, i: number) => {
         console.log(`  index=${i} value=${v} id=${nodeIds[i]}`);
      });
    }
  }
});
