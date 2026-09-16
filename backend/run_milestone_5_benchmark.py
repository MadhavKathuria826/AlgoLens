"""
AlgoLens Milestone 5 Performance & Overhead Benchmark Suite
Measures:
1. Pure Uninstrumented Native execution time (mean ms)
2. Instrumented Native execution time (mean ms)
3. Instrumentation Overhead Ratio (Instrumented / Uninstrumented)
4. Event Count and Raw Trace Bytes
5. State Reducer throughput (events/sec)
6. Playback Engine Seek Latency (ms)
Outputs Markdown table and saves JSON to backend/milestone_5_benchmark_results.json
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
from native_runner import NativeCompilationPipeline
from state_reducer import UniversalRuntimeState, UniversalStateReducer
from playback_engine import PlaybackEngine

BENCHMARK_CASES = {
    "G01_basic_scalars": GOLDEN_TEST_CASES["G01_basic_scalars"]["code"],
    "G03_arithmetic": GOLDEN_TEST_CASES["G03_arithmetic"]["code"],
    "G14_linked_lists": GOLDEN_TEST_CASES["G14_linked_lists"]["code"],
    "G15_binary_trees": GOLDEN_TEST_CASES["G15_binary_trees"]["code"],
    "G16_pointer_allocation": GOLDEN_TEST_CASES["G16_pointer_allocation"]["code"],
    "G17_pointer_aliasing": GOLDEN_TEST_CASES["G17_pointer_aliasing"]["code"],
    "G18_reference_behavior": GOLDEN_TEST_CASES["G18_reference_behavior"]["code"],
    "M5_first_class_refs": """
    void inc(int& x) { x = x + 1; }
    int test() {
        int a = 10;
        int& ref = a;
        ref = 50;
        inc(a);
        return a;
    }
    """,
    "M5_pointer_to_pointer": """
    int test() {
        int x = 10;
        int y = 20;
        int* p = &x;
        int** pp = &p;
        *pp = &y;
        **pp = 99;
        return y;
    }
    """,
    "M5_nested_structs": """
    struct Point { int x; int y; };
    struct Rect { Point topLeft; Point bottomRight; };
    int test() {
        Rect r;
        r.topLeft.x = 10;
        r.topLeft.y = 20;
        r.bottomRight.x = 100;
        r.bottomRight.y = 200;
        return r.bottomRight.x;
    }
    """,
    "M5_class_methods": """
    class Counter {
    public:
        int count;
        Counter() : count(0) {}
        void inc() { count = count + 1; }
        void add(int d) { count = count + d; }
    };
    int test() {
        Counter c;
        c.inc();
        c.add(5);
        return c.count;
    }
    """,
    "M5_stl_expansions": """
    int test() {
        std::string s = "algo";
        s.push_back('l');
        s.append("ens");
        s[0] = 'A';
        s.pop_back();

        std::vector<int> v;
        v.push_back(10);
        v.push_back(20);
        v.clear();

        std::map<std::string, int> m;
        m["k1"] = 1;
        m["k2"] = 2;
        m.erase("k1");
        m.clear();
        return 0;
    }
    """
}


def run_benchmark():
    print("==================================================================")
    print("      AlgoLens Milestone 5 Performance & Overhead Benchmark")
    print("==================================================================\n")
    pipeline = NativeCompilationPipeline()
    print(f"Compiler: {pipeline.compiler_name}")
    print(f"Version:  {pipeline.compiler_version[:70]}...\n")

    results = []

    for name, code in BENCHMARK_CASES.items():
        print(f"Benchmarking {name}...")

        # 1. Pure Uninstrumented Native Execution
        uninst_compile_ms, uninst_exec_ms, _ = pipeline.compile_and_run_uninstrumented(code, "test", [])

        # 2. Compile Instrumented Binary
        compiled, diag, compile_ms, err = pipeline.compile_only(code, "test", [])
        assert compiled is not None, f"Compilation failed for {name}: {err}"

        # 3. Warm Execution Iterations
        exec_times = []
        raw_trace_bytes = 0
        run_res = None
        for _ in range(5):
            run_res = pipeline.run_binary(compiled)
            exec_times.append(run_res.execution_time_ms)
        compiled.cleanup()

        avg_inst_ms = statistics.mean(exec_times)
        min_inst_ms = min(exec_times)
        events = run_res.events
        event_count = len(events)
        raw_trace_bytes = sum(len(json.dumps(ev.payload)) for ev in events)

        overhead_ratio = avg_inst_ms / uninst_exec_ms if uninst_exec_ms > 0 else 1.0

        # 4. State Reducer Throughput
        t_red_start = time.perf_counter()
        state = UniversalRuntimeState()
        for ev in events:
            state = UniversalStateReducer.reduce(state, ev)
        reducer_time_ms = (time.perf_counter() - t_red_start) * 1000.0
        reducer_throughput = (event_count / (reducer_time_ms / 1000.0)) if reducer_time_ms > 0 else 0.0

        # 5. Playback Engine Seek Latency
        engine = PlaybackEngine(events)
        engine.build_checkpoints()
        seek_times = []
        for seq in range(event_count):
            t_seek0 = time.perf_counter()
            engine.seek(seq)
            seek_times.append((time.perf_counter() - t_seek0) * 1000.0)
        avg_seek_ms = statistics.mean(seek_times) if seek_times else 0.0

        item = {
            "name": name,
            "uninst_exec_ms": round(uninst_exec_ms, 2),
            "inst_exec_ms": round(avg_inst_ms, 2),
            "overhead_ratio": round(overhead_ratio, 2),
            "event_count": event_count,
            "raw_trace_bytes": raw_trace_bytes,
            "reducer_throughput_eps": round(reducer_throughput, 1),
            "avg_seek_ms": round(avg_seek_ms, 3)
        }
        results.append(item)
        print(f"  Uninst: {item['uninst_exec_ms']}ms | Inst: {item['inst_exec_ms']}ms | Overhead: {item['overhead_ratio']}x | Events: {item['event_count']} | Seek: {item['avg_seek_ms']}ms")

    # Save JSON results
    out_path = os.path.join(BACKEND_DIR, "milestone_5_benchmark_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved benchmark results to {out_path}")

    # Output Markdown Table
    print("\n### Milestone 5 Performance & Overhead Summary Table\n")
    headers = ["Benchmark Category", "Uninst Exec (ms)", "Inst Exec (ms)", "Overhead", "Events", "Trace Size", "Reducer (eps)", "Seek Latency (ms)"]
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in results:
        row = [
            f"`{r['name']}`",
            f"{r['uninst_exec_ms']:.2f}",
            f"{r['inst_exec_ms']:.2f}",
            f"{r['overhead_ratio']:.2f}x",
            f"{r['event_count']}",
            f"{r['raw_trace_bytes']} B",
            f"{r['reducer_throughput_eps']:.0f}",
            f"{r['avg_seek_ms']:.3f}"
        ]
        print("| " + " | ".join(row) + " |")


if __name__ == "__main__":
    run_benchmark()
