"""
AlgoLens Milestone 4 Performance & Overhead Benchmark Suite
Measures:
1. Pure Uninstrumented Native execution time (mean ms)
2. Instrumented Native execution time (mean ms, warm cached binary)
3. Instrumentation Overhead Ratio (Instrumented / Uninstrumented)
4. Event Count and Raw Trace Bytes
5. Legacy Python AST Interpretation time (ms)
6. Speedup of Native Instrumented vs Legacy Python (Legacy / Instrumented)
Outputs Markdown table and saves JSON to backend/milestone_4_benchmark_results.json
"""

import os
import sys
import time
import json
import statistics

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from golden_corpus import GOLDEN_TEST_CASES
from cpp_interpreter import CPPInterpreter
from native_runner import NativeCompilationPipeline

BENCHMARK_CATEGORIES = [
    "G01_basic_scalars",
    "G03_arithmetic",
    "G08_recursion",
    "G09_arrays",
    "G22_loops",
    "G14_linked_lists",
    "G15_binary_trees",
    "G16_pointer_allocation",
    "G17_pointer_aliasing",
    "G10_vector_operations",
    "G11_stack_operations",
    "G12_queue_operations",
    "G13_map_operations"
]


def run_benchmark():
    print("=== AlgoLens Milestone 4 Performance & Overhead Benchmark ===\n")
    pipeline = NativeCompilationPipeline()
    interp = CPPInterpreter(max_recursion_depth=100)

    print(f"Compiler: {pipeline.compiler_name}")
    print(f"Version:  {pipeline.compiler_version[:70]}...\n")

    results = []

    for key in BENCHMARK_CATEGORIES:
        spec = GOLDEN_TEST_CASES[key]
        code = spec["code"]
        entry_func = spec["entry_func"]
        args = spec["args"]

        print(f"Benchmarking {key}...")

        # 1. Legacy Python AST Interpretation (3 iterations)
        legacy_times = []
        for _ in range(3):
            t0 = time.perf_counter()
            steps, ret = interp.interpret(code, entry_func, args)
            legacy_times.append((time.perf_counter() - t0) * 1000.0)
        avg_legacy_ms = statistics.mean(legacy_times)

        # 2. Pure Uninstrumented Native Execution
        uninst_compile_ms, uninst_exec_ms, _ = pipeline.compile_and_run_uninstrumented(code, entry_func, args)

        # 3. Instrumented Native Execution (Compile once, measure warm runs)
        compiled, diag, compile_ms, err = pipeline.compile_only(code, entry_func, args)
        assert compiled is not None, f"Compilation failed for {key}: {err}"

        warm_times = []
        raw_trace_bytes = 0
        run_res = None
        for _ in range(5):
            t0 = time.perf_counter()
            run_res = pipeline.run_binary(compiled)
            warm_times.append((time.perf_counter() - t0) * 1000.0)
            if raw_trace_bytes == 0:
                raw_trace_bytes = sum(len(f"[ALGOLENS_EVENT] {ev.model_dump_json()}\n".encode("utf-8")) for ev in run_res.events)

        avg_inst_ms = statistics.mean(warm_times)
        compiled.cleanup()

        event_count = len(run_res.events) if run_res else 0

        # Overhead ratio: Instrumented execution vs uninstrumented execution
        # (Both running native process on host OS)
        overhead_ratio = avg_inst_ms / uninst_exec_ms if uninst_exec_ms > 0 else 1.0

        # Speedup vs Legacy Python
        speedup_vs_legacy = avg_legacy_ms / avg_inst_ms if avg_inst_ms > 0 else 1.0

        item = {
            "category": key,
            "uninstrumented_exec_ms": round(uninst_exec_ms, 2),
            "instrumented_warm_ms": round(avg_inst_ms, 2),
            "overhead_ratio": round(overhead_ratio, 2),
            "legacy_time_ms": round(avg_legacy_ms, 2),
            "native_vs_legacy_speedup": round(speedup_vs_legacy, 2),
            "event_count": event_count,
            "raw_trace_bytes": raw_trace_bytes
        }
        results.append(item)

    # Print Table
    print("\n" + "=" * 125)
    header = f"| {'Category':<24} | {'Uninst (ms)':<11} | {'Inst (ms)':<9} | {'Overhead':<8} | {'Legacy (ms)':<11} | {'Speedup':<7} | {'Events':<6} | {'Trace (B)':<9} |"
    divider = f"|{'-'*26}|{'-'*13}|{'-'*11}|{'-'*10}|{'-'*13}|{'-'*9}|{'-'*8}|{'-'*11}|"
    print(header)
    print(divider)
    for r in results:
        line = f"| {r['category']:<24} | {r['uninstrumented_exec_ms']:<11.2f} | {r['instrumented_warm_ms']:<9.2f} | {r['overhead_ratio']:<8.2f}x | {r['legacy_time_ms']:<11.2f} | {r['native_vs_legacy_speedup']:<7.2f}x | {r['event_count']:<6} | {r['raw_trace_bytes']:<9} |"
        print(line)
    print("=" * 125 + "\n")

    # Save to JSON
    out_path = os.path.join(BACKEND_DIR, "milestone_4_benchmark_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "compiler": pipeline.compiler_name,
            "version": pipeline.compiler_version,
            "results": results
        }, f, indent=2)

    print(f"Milestone 4 benchmark results saved to: {out_path}")
    return results


if __name__ == "__main__":
    run_benchmark()
