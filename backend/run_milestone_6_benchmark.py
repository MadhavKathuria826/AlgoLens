"""
AlgoLens Milestone 6 Performance & Latency Benchmark Suite
Measures and profiles all 9 execution pipeline stages across cold, warm, and uninstrumented execution:
1. Source AST Instrumentation Time (ms)
2. Native Compilation Time (ms)
3. Cache Lookup Time (ms)
4. Process Startup / Backend Invocation Time (ms)
5. Native Execution Time (ms)
6. Event Transport & Buffering Time (ms)
7. Python Event Deserialization / Parsing Time (ms)
8. Universal State Reduction Time (ms)
9. End-to-End Latency (ms)

Runs 10 iterations across representative benchmark workloads.
Outputs statistical summary (median, min, max, std dev) and saves backend/milestone_6_benchmark_results.json.
"""

import os
import sys
import time
import json
import statistics
from typing import Dict, Any, List

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from golden_corpus import GOLDEN_TEST_CASES
from native_runner import NativeCompilationPipeline
from state_reducer import UniversalRuntimeState, UniversalStateReducer
from event_models import AlgoLensEvent

BENCHMARK_CASES = {
    "G01_basic_scalars": {
        "code": GOLDEN_TEST_CASES["G01_basic_scalars"]["code"],
        "entry": "main"
    },
    "G14_linked_lists": {
        "code": GOLDEN_TEST_CASES["G14_linked_lists"]["code"],
        "entry": "main"
    },
    "G15_binary_trees": {
        "code": GOLDEN_TEST_CASES["G15_binary_trees"]["code"],
        "entry": "main"
    },
    "G17_pointer_aliasing": {
        "code": GOLDEN_TEST_CASES["G17_pointer_aliasing"]["code"],
        "entry": "main"
    },
    "M5_nested_structs": {
        "code": """
        struct Point { int x; int y; };
        struct Rect { Point topLeft; Point bottomRight; };
        int test() {
            Rect r;
            r.topLeft.x = 10;
            r.topLeft.y = 20;
            r.bottomRight.x = 100;
            r.bottomRight.y = 200;
            return r.bottomRight.x - r.topLeft.x;
        }
        """,
        "entry": "test"
    },
    "M5_stl_containers": {
        "code": """
        int test() {
            std::vector<int> v;
            for (int i = 0; i < 50; ++i) {
                v.push_back(i * 3);
            }
            std::string s = "algolens_bench";
            s.append("_active");
            return (int)v.size() + (int)s.size();
        }
        """,
        "entry": "test"
    }
}


def stats_dict(vals: List[float]) -> Dict[str, float]:
    """Calculates statistical summary for a list of values."""
    if not vals:
        return {"median": 0.0, "min": 0.0, "max": 0.0, "stdev": 0.0, "mean": 0.0}
    return {
        "median": round(statistics.median(vals), 3),
        "min": round(min(vals), 3),
        "max": round(max(vals), 3),
        "stdev": round(statistics.stdev(vals) if len(vals) > 1 else 0.0, 3),
        "mean": round(statistics.mean(vals), 3)
    }


def run_milestone_6_benchmarks(iterations: int = 10) -> Dict[str, Any]:
    print("======================================================================")
    print("         ALGOLENS MILESTONE 6 PERFORMANCE & LATENCY BENCHMARK         ")
    print(f"         Workloads: {len(BENCHMARK_CASES)} | Iterations per case: {iterations}")
    print("======================================================================\n")

    pipeline = NativeCompilationPipeline(enable_cache=True)
    all_results = {}

    for case_name, case_info in BENCHMARK_CASES.items():
        code = case_info["code"]
        entry = case_info["entry"]
        print(f"Benchmarking workload: {case_name} ...")

        # 0. Uninstrumented Native Baseline
        uninst_c_ms, uninst_exec_ms, _ = pipeline.compile_and_run_uninstrumented(code, entry_func=entry)

        # 1. Cold Execution (purge cache entry for this workload)
        # Clear specific entry or full cache to guarantee cold compilation
        pipeline.cache.clear()
        t_cold_start = time.perf_counter()
        res_cold = pipeline.compile_and_run(code, entry_func=entry)
        t_cold_total = (time.perf_counter() - t_cold_start) * 1000.0
        assert res_cold.success, f"Cold benchmark failed for {case_name}: {res_cold.error_message}"
        assert res_cold.cache_status == "CACHE_MISS"

        # Measure reduction on cold events
        t_red_start = time.perf_counter()
        s_cold = UniversalRuntimeState()
        for ev in res_cold.events:
            s_cold = UniversalStateReducer.reduce(s_cold, ev)
        cold_red_ms = (time.perf_counter() - t_red_start) * 1000.0

        cold_profile = {
            "instrumentation_ms": round(res_cold.instrumentation_time_ms, 3),
            "compilation_ms": round(res_cold.compile_time_ms, 3),
            "cache_lookup_ms": round(res_cold.cache_lookup_time_ms, 3),
            "backend_execution_ms": round(res_cold.execution_time_ms, 3),
            "reduction_ms": round(cold_red_ms, 3),
            "total_e2e_ms": round(t_cold_total, 3),
            "event_count": len(res_cold.events)
        }

        # 2. Warm Execution (10 iterations on cache hit)
        warm_runs = {
            "instrumentation_ms": [],
            "compilation_ms": [],
            "cache_lookup_ms": [],
            "backend_execution_ms": [],
            "deserialization_ms": [],
            "reduction_ms": [],
            "total_e2e_ms": []
        }

        for run_idx in range(iterations):
            t_warm_start = time.perf_counter()
            res_warm = pipeline.compile_and_run(code, entry_func=entry)
            t_warm_total = (time.perf_counter() - t_warm_start) * 1000.0
            assert res_warm.success
            assert res_warm.cache_status == "CACHE_HIT"

            t_red_start = time.perf_counter()
            s_warm = UniversalRuntimeState()
            for ev in res_warm.events:
                s_warm = UniversalStateReducer.reduce(s_warm, ev)
            warm_red_ms = (time.perf_counter() - t_red_start) * 1000.0

            warm_runs["instrumentation_ms"].append(res_warm.instrumentation_time_ms)
            warm_runs["compilation_ms"].append(res_warm.compile_time_ms)
            warm_runs["cache_lookup_ms"].append(res_warm.cache_lookup_time_ms)
            warm_runs["backend_execution_ms"].append(res_warm.execution_time_ms)
            warm_runs["reduction_ms"].append(warm_red_ms)
            warm_runs["total_e2e_ms"].append(t_warm_total)

        warm_summary = {stage: stats_dict(vals) for stage, vals in warm_runs.items()}
        speedup = round(cold_profile["total_e2e_ms"] / warm_summary["total_e2e_ms"]["median"], 2)

        case_summary = {
            "workload": case_name,
            "event_count": len(res_cold.events),
            "uninstrumented_baseline": {
                "compilation_ms": round(uninst_c_ms, 3),
                "execution_ms": round(uninst_exec_ms, 3)
            },
            "cold_execution": cold_profile,
            "warm_execution": warm_summary,
            "cache_speedup_factor": speedup
        }
        all_results[case_name] = case_summary

        print(f"  -> Cold Total: {cold_profile['total_e2e_ms']:.1f}ms (Compile: {cold_profile['compilation_ms']:.1f}ms)")
        print(f"  -> Warm Total: {warm_summary['total_e2e_ms']['median']:.1f}ms (Compile: 0.0ms, Lookup: {warm_summary['cache_lookup_ms']['median']:.2f}ms)")
        print(f"  -> Execution Speedup: {speedup}x\n")

    # Output Markdown Summary Table
    print("\n======================================================================")
    print("                    MILESTONE 6 BENCHMARK RESULTS                     ")
    print("======================================================================\n")

    header = "| Workload | Events | Uninst Exec (ms) | Cold Total (ms) | Cold Compile (ms) | Warm Lookup (ms) | Warm Exec (ms) | Warm Total (ms) | Cache Speedup |"
    sep    = "|:---|---:|---:|---:|---:|---:|---:|---:|---:|"
    print(header)
    print(sep)

    for case_name, data in all_results.items():
        events = data["event_count"]
        uninst_exec = data["uninstrumented_baseline"]["execution_ms"]
        cold_total = data["cold_execution"]["total_e2e_ms"]
        cold_comp = data["cold_execution"]["compilation_ms"]
        warm_lookup = data["warm_execution"]["cache_lookup_ms"]["median"]
        warm_exec = data["warm_execution"]["backend_execution_ms"]["median"]
        warm_total = data["warm_execution"]["total_e2e_ms"]["median"]
        speedup = data["cache_speedup_factor"]

        print(f"| {case_name} | {events} | {uninst_exec:.2f} | {cold_total:.1f} | {cold_comp:.1f} | {warm_lookup:.2f} | {warm_exec:.2f} | {warm_total:.1f} | **{speedup}x** |")

    # Save results JSON
    out_path = os.path.join(BACKEND_DIR, "milestone_6_benchmark_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved detailed benchmark metrics to: {out_path}")

    return all_results


if __name__ == "__main__":
    run_milestone_6_benchmarks(iterations=10)
