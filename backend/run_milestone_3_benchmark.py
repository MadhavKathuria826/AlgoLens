"""
AlgoLens Milestone 3 Performance Benchmark Suite
Compares:
1. Legacy Python AST Interpreter execution time (mean of multiple runs)
2. Native Cold execution time (source instrumentation + clang++ compilation + execution)
3. Native Warm execution time (cached native binary execution without recompilation)
4. Speedup ratios (Cold vs Legacy, Warm vs Legacy)
5. Event stream size and event count across the 9 Golden Categories
Outputs results in Markdown table format and writes JSON to backend/milestone_3_benchmark_results.json
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

NATIVE_SUBSET_KEYS = [
    "G01_basic_scalars",
    "G02_assignments",
    "G03_arithmetic",
    "G06_nested_scopes",
    "G07_function_calls",
    "G08_recursion",
    "G09_arrays",
    "G21_conditional_branches",
    "G22_loops"
]


def run_benchmark():
    print("=== AlgoLens Milestone 3 Native Performance Benchmark ===\n")
    pipeline = NativeCompilationPipeline()
    interp = CPPInterpreter(max_recursion_depth=100)

    print(f"Compiler: {pipeline.compiler_name}")
    print(f"Version:  {pipeline.compiler_version}\n")

    results = []

    for key in NATIVE_SUBSET_KEYS:
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
            t_ms = (time.perf_counter() - t0) * 1000.0
            legacy_times.append(t_ms)
        avg_legacy_ms = statistics.mean(legacy_times)

        # 2. Native Cold Execution (Instrument + Compile + Run)
        t_cold_start = time.perf_counter()
        compiled, diag, compile_ms, err = pipeline.compile_only(code, entry_func, args)
        assert compiled is not None, f"Compilation failed for {key}: {err} {diag}"
        cold_run = pipeline.run_binary(compiled)
        cold_total_ms = (time.perf_counter() - t_cold_start) * 1000.0
        assert cold_run.success, f"Execution failed for {key}: {cold_run.error_message}"

        # 3. Native Warm Execution (Running cached executable 5 iterations)
        warm_times = []
        raw_trace_bytes = 0
        for _ in range(5):
            t0 = time.perf_counter()
            run_res = pipeline.run_binary(compiled)
            warm_ms = (time.perf_counter() - t0) * 1000.0
            warm_times.append(warm_ms)
            if raw_trace_bytes == 0:
                # calculate serialized trace bytes
                raw_trace_bytes = sum(len(f"[ALGOLENS_EVENT] {ev.model_dump_json()}\n".encode('utf-8')) for ev in run_res.events)

        avg_warm_ms = statistics.mean(warm_times)
        compiled.cleanup()

        event_count = len(cold_run.events)

        # Speedup ratios:
        cold_speedup = avg_legacy_ms / cold_total_ms if cold_total_ms > 0 else 0.0
        warm_speedup = avg_legacy_ms / avg_warm_ms if avg_warm_ms > 0 else 0.0

        item = {
            "category": key,
            "legacy_time_ms": round(avg_legacy_ms, 2),
            "native_cold_time_ms": round(cold_total_ms, 2),
            "native_compile_time_ms": round(compile_ms, 2),
            "native_warm_time_ms": round(avg_warm_ms, 2),
            "cold_vs_legacy_speedup": round(cold_speedup, 3),
            "warm_vs_legacy_speedup": round(warm_speedup, 3),
            "event_count": event_count,
            "raw_trace_bytes": raw_trace_bytes
        }
        results.append(item)

    # Print Table
    print("\n" + "=" * 116)
    header = f"| {'Category':<26} | {'Legacy (ms)':<11} | {'Cold (ms)':<10} | {'Warm (ms)':<10} | {'Cold Spdup':<10} | {'Warm Spdup':<10} | {'Events':<6} | {'Trace (B)':<9} |"
    divider = f"|{'-'*28}|{'-'*13}|{'-'*12}|{'-'*12}|{'-'*12}|{'-'*12}|{'-'*8}|{'-'*11}|"
    print(header)
    print(divider)
    for r in results:
        line = f"| {r['category']:<26} | {r['legacy_time_ms']:<11.2f} | {r['native_cold_time_ms']:<10.2f} | {r['native_warm_time_ms']:<10.2f} | {r['cold_vs_legacy_speedup']:<10.3f} | {r['warm_vs_legacy_speedup']:<10.3f} | {r['event_count']:<6} | {r['raw_trace_bytes']:<9} |"
        print(line)
    print("=" * 116 + "\n")

    # Output JSON file
    out_path = os.path.join(BACKEND_DIR, "milestone_3_benchmark_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "compiler": pipeline.compiler_name,
            "version": pipeline.compiler_version,
            "results": results
        }, f, indent=2)

    print(f"Benchmark results successfully saved to: {out_path}")
    return results


if __name__ == "__main__":
    run_benchmark()
