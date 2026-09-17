"""
AlgoLens Milestone 7 Performance Benchmark Suite
Empirically measures Python runtime overhead across:
1. Pure uninstrumented Python execution
2. Tracing & instrumentation overhead
3. Event generation
4. UniversalStateReducer reduction
5. Total end-to-end execution
Compares cost structure directly against equivalent native C++ workloads (both Cold and Warm Cache).
"""

import os
import sys
import time
import json
import statistics
from typing import Dict, Any, List, Tuple

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from native_runner import NativeCompilationPipeline
from python_producer import PythonRuntimeProducer
from state_reducer import UniversalRuntimeState, UniversalStateReducer


def benchmark_python_pipeline(code: str, entry_func: str, iterations: int = 10) -> Dict[str, float]:
    """Measures Python pipeline breakdown over repeated iterations."""
    producer = PythonRuntimeProducer()

    # 1. Measure Pure Uninstrumented Python Execution
    pure_times = []
    compiled_pure = compile(code, "<benchmark>", "exec")
    for _ in range(iterations):
        env = {}
        t0 = time.perf_counter()
        exec(compiled_pure, env)
        if entry_func in env and callable(env[entry_func]):
            env[entry_func]()
        pure_times.append((time.perf_counter() - t0) * 1000.0)
    avg_pure_exec_ms = statistics.mean(pure_times)

    # 2. Measure Traced Execution & Event Generation
    exec_times = []
    event_counts = []
    results = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        res = producer.execute_program(code, entry_func=entry_func)
        exec_times.append((time.perf_counter() - t0) * 1000.0)
        event_counts.append(len(res.events))
        results.append(res)
    avg_traced_exec_ms = statistics.mean(exec_times)
    avg_events = statistics.mean(event_counts)

    # 3. Measure UniversalStateReducer Reduction
    last_res = results[-1]
    reduce_times = []
    for _ in range(iterations):
        state = UniversalRuntimeState()
        t0 = time.perf_counter()
        for ev in last_res.events:
            state = UniversalStateReducer.reduce(state, ev)
        reduce_times.append((time.perf_counter() - t0) * 1000.0)
    avg_reduce_ms = statistics.mean(reduce_times)

    # Tracing overhead is difference between traced execution and pure execution
    tracing_overhead_ms = max(0.0, avg_traced_exec_ms - avg_pure_exec_ms)
    total_pipeline_ms = avg_traced_exec_ms + avg_reduce_ms

    return {
        "pure_execution_ms": avg_pure_exec_ms,
        "traced_execution_ms": avg_traced_exec_ms,
        "tracing_overhead_ms": tracing_overhead_ms,
        "reduction_ms": avg_reduce_ms,
        "total_pipeline_ms": total_pipeline_ms,
        "event_count": avg_events
    }


def benchmark_cpp_pipeline(code: str, entry_func: str, iterations: int = 5) -> Dict[str, float]:
    """Measures C++ native pipeline breakdown (Cold vs Warm cache)."""
    pipeline = NativeCompilationPipeline(enable_cache=True)
    pipeline.cache.clear()

    # Cold Run
    t_cold_start = time.perf_counter()
    cold_res = pipeline.execute_program(code, entry_func=entry_func)
    cold_total_ms = (time.perf_counter() - t_cold_start) * 1000.0

    # Warm Runs
    warm_exec_times = []
    warm_total_times = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        res = pipeline.execute_program(code, entry_func=entry_func)
        warm_total_times.append((time.perf_counter() - t0) * 1000.0)
        warm_exec_times.append(res.execution_time_ms)

    # Measure State Reduction on C++ events
    reduce_times = []
    for _ in range(iterations):
        state = UniversalRuntimeState()
        t0 = time.perf_counter()
        for ev in cold_res.events:
            state = UniversalStateReducer.reduce(state, ev)
        reduce_times.append((time.perf_counter() - t0) * 1000.0)
    avg_reduce_ms = statistics.mean(reduce_times)

    return {
        "cold_compile_ms": cold_res.compile_time_ms,
        "cold_total_ms": cold_total_ms,
        "warm_lookup_ms": statistics.mean([warm_total_times[i] - warm_exec_times[i] for i in range(len(warm_total_times))]),
        "warm_execution_ms": statistics.mean(warm_exec_times),
        "warm_total_ms": statistics.mean(warm_total_times),
        "reduction_ms": avg_reduce_ms,
        "event_count": len(cold_res.events)
    }


def run_milestone_7_benchmarks():
    print("======================================================================")
    print("           ALGOLENS MILESTONE 7 PERFORMANCE BENCHMARK SUITE           ")
    print("======================================================================")

    # Workload 1: Iterative Loop Accumulator (100 iterations)
    py_code_loop = """
def run():
    acc = 0
    for i in range(1, 101):
        acc += i * 2
    return acc
"""
    cpp_code_loop = """
int run() {
    int acc = 0;
    for (int i = 1; i <= 100; ++i) {
        acc += i * 2;
    }
    return acc;
}
"""
    print("\n--- Workload 1: Iterative Loop Accumulator (100 iterations) ---")
    py_metrics_1 = benchmark_python_pipeline(py_code_loop, "run", iterations=10)
    cpp_metrics_1 = benchmark_cpp_pipeline(cpp_code_loop, "run", iterations=5)

    print("  Python Metrics:")
    print(f"    - Pure Uninstrumented Execution: {py_metrics_1['pure_execution_ms']:.3f} ms")
    print(f"    - Tracing & Event Generation:    {py_metrics_1['traced_execution_ms']:.3f} ms")
    print(f"    - Tracing Overhead:              {py_metrics_1['tracing_overhead_ms']:.3f} ms ({py_metrics_1['traced_execution_ms'] / max(0.001, py_metrics_1['pure_execution_ms']):.1f}x pure)")
    print(f"    - Universal State Reduction:     {py_metrics_1['reduction_ms']:.3f} ms")
    print(f"    - Total End-to-End Pipeline:     {py_metrics_1['total_pipeline_ms']:.3f} ms")
    print(f"    - Events Generated:              {py_metrics_1['event_count']:.0f}")

    print("\n  C++ Native Metrics:")
    print(f"    - Cold Compilation (Clang++):   {cpp_metrics_1['cold_compile_ms']:.1f} ms")
    print(f"    - Cold Total Time:               {cpp_metrics_1['cold_total_ms']:.1f} ms")
    print(f"    - Warm Cache Lookup:             {cpp_metrics_1['warm_lookup_ms']:.3f} ms")
    print(f"    - Warm Native Execution:         {cpp_metrics_1['warm_execution_ms']:.3f} ms")
    print(f"    - Universal State Reduction:     {cpp_metrics_1['reduction_ms']:.3f} ms")
    print(f"    - Warm Total Time:               {cpp_metrics_1['warm_total_ms']:.3f} ms")
    print(f"    - Events Generated:              {cpp_metrics_1['event_count']}")

    # Workload 2: Container Mutations (Vector / List Append & Index writes)
    py_code_container = """
def run():
    lst = []
    for i in range(50):
        lst.append(i * 3)
    for i in range(50):
        lst[i] = lst[i] + 1
    return len(lst)
"""
    cpp_code_container = """
int run() {
    std::vector<int> lst;
    for (int i = 0; i < 50; ++i) {
        lst.push_back(i * 3);
    }
    for (int i = 0; i < 50; ++i) {
        lst[i] = lst[i] + 1;
    }
    return lst.size();
}
"""
    print("\n--- Workload 2: Container Mutations (50 appends + 50 index writes) ---")
    py_metrics_2 = benchmark_python_pipeline(py_code_container, "run", iterations=10)
    cpp_metrics_2 = benchmark_cpp_pipeline(cpp_code_container, "run", iterations=5)

    print("  Python Metrics:")
    print(f"    - Pure Uninstrumented Execution: {py_metrics_2['pure_execution_ms']:.3f} ms")
    print(f"    - Tracing & Event Generation:    {py_metrics_2['traced_execution_ms']:.3f} ms")
    print(f"    - Tracing Overhead:              {py_metrics_2['tracing_overhead_ms']:.3f} ms")
    print(f"    - Universal State Reduction:     {py_metrics_2['reduction_ms']:.3f} ms")
    print(f"    - Total End-to-End Pipeline:     {py_metrics_2['total_pipeline_ms']:.3f} ms")
    print(f"    - Events Generated:              {py_metrics_2['event_count']:.0f}")

    print("\n  C++ Native Metrics:")
    print(f"    - Cold Compilation (Clang++):   {cpp_metrics_2['cold_compile_ms']:.1f} ms")
    print(f"    - Cold Total Time:               {cpp_metrics_2['cold_total_ms']:.1f} ms")
    print(f"    - Warm Cache Lookup:             {cpp_metrics_2['warm_lookup_ms']:.3f} ms")
    print(f"    - Warm Native Execution:         {cpp_metrics_2['warm_execution_ms']:.3f} ms")
    print(f"    - Universal State Reduction:     {cpp_metrics_2['reduction_ms']:.3f} ms")
    print(f"    - Warm Total Time:               {cpp_metrics_2['warm_total_ms']:.3f} ms")
    print(f"    - Events Generated:              {cpp_metrics_2['event_count']}")

    # Save benchmark results
    results_payload = {
        "workload_1_loop": {
            "python": py_metrics_1,
            "cpp": cpp_metrics_1
        },
        "workload_2_container": {
            "python": py_metrics_2,
            "cpp": cpp_metrics_2
        }
    }
    bench_file = os.path.join(BACKEND_DIR, "milestone_7_benchmark_results.json")
    with open(bench_file, "w", encoding="utf-8") as f:
        json.dump(results_payload, f, indent=2)
    print(f"\n[OK] Benchmark results written to {bench_file}")


if __name__ == "__main__":
    run_milestone_7_benchmarks()
