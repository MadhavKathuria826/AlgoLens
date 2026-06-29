import { SemanticAnalyzer } from '../src/utils/semanticAnalyzer';

const analyzer = new SemanticAnalyzer();

const steps = [
  { locals: {}, code: "dq = []" },
  { locals: { dq: [] }, code: "dq.append(10)" },      // rear insert
  { locals: { dq: [10] }, code: "dq.append(20)" },  // rear insert
  { locals: { dq: [10, 20] }, code: "dq.pop()" },     // rear remove
  { locals: { dq: [10] }, code: "dq.append(30)" },  // rear insert
  { locals: { dq: [10, 30] }, code: "dq.pop(0)" },    // front remove
  { locals: { dq: [30] }, code: "" }
];

let prevLocals = {};
for (let i = 0; i < steps.length; i++) {
  const step = steps[i];
  console.log(`\n--- Step ${i}: ${step.code} ---`);
  analyzer.analyzeFrame(step.locals, prevLocals, step.code);
  prevLocals = step.locals;
  const memory = analyzer.getMemory();
  console.log(JSON.stringify(memory, null, 2));
}
