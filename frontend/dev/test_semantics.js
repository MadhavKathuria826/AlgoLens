"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
var semanticAnalyzer_1 = require("../src/utils/semanticAnalyzer");
var analyzer = new semanticAnalyzer_1.SemanticAnalyzer();
var steps = [
    { locals: {}, code: "dq = []" },
    { locals: { dq: [] }, code: "dq.append(10)" }, // rear insert
    { locals: { dq: [10] }, code: "dq.append(20)" }, // rear insert
    { locals: { dq: [10, 20] }, code: "dq.pop()" }, // rear remove
    { locals: { dq: [10] }, code: "dq.append(30)" }, // rear insert
    { locals: { dq: [10, 30] }, code: "dq.pop(0)" }, // front remove
    { locals: { dq: [30] }, code: "" }
];
var prevLocals = {};
for (var i = 0; i < steps.length; i++) {
    var step = steps[i];
    console.log("\n--- Step ".concat(i, ": ").concat(step.code, " ---"));
    analyzer.analyzeFrame(step.locals, prevLocals, step.code);
    prevLocals = step.locals;
    var memory = analyzer.getMemory();
    console.log(JSON.stringify(memory, null, 2));
}
