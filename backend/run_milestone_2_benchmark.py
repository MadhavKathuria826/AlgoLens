"""
AlgoLens Milestone 2 Performance Benchmark Suite
Compares:
1. Legacy Architecture: Full state deep-copied snapshots for every step
2. Event Protocol + Checkpoint Architecture: Reversible event stream with adaptive checkpoints

Workloads:
- Workload A: Sorting (Bubble Sort N=4, N=6, N=8)
- Workload B: Recursion (Fibonacci N=3, N=4, N=5)
- Workload C: Data Structures (Vector, Stack, Linked List)

Metrics:
- Trace In-Memory Footprint (KB)
- Network JSON Payload Size (KB) and Compression / Savings Ratio
- Trace Generation & Processing Time (ms)
- Snapshot Count vs Checkpoint Count
- Forward Step Latency (μs)
- Reverse Step Latency (μs)
- Random Seek Latency (μs / ms) across 25%, 50%, 75%, 100%
"""

import sys
import os
import time
import json
from typing import Dict, Any, List, Tuple

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cpp_interpreter import CPPInterpreter
from playback_engine import PlaybackEngine
from checkpoint_manager import AdaptivePolicy, FixedIntervalPolicy
from state_reducer import UniversalStateReducer, UniversalRuntimeState


def get_deep_size(obj, seen=None) -> int:
    """Recursively computes memory footprint of Python objects."""
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)
    size = sys.getsizeof(obj)
    if isinstance(obj, dict):
        for k, v in obj.items():
            size += get_deep_size(k, seen)
            size += get_deep_size(v, seen)
    elif hasattr(obj, "__dict__"):
        size += get_deep_size(obj.__dict__, seen)
    elif hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes, bytearray)):
        for i in obj:
            size += get_deep_size(i, seen)
    return size


def dump_steps_json(steps: List[Any]) -> str:
    res = []
    for s in steps:
        if hasattr(s, "model_dump"):
            res.append(s.model_dump())
        elif hasattr(s, "dict"):
            res.append(s.dict())
        else:
            res.append(s)
    return json.dumps(res)


def dump_events_json(events: List[Any]) -> str:
    res = []
    for e in events:
        if hasattr(e, "model_dump"):
            res.append(e.model_dump())
        elif hasattr(e, "dict"):
            res.append(e.dict())
        else:
            res.append(e)
    return json.dumps(res)


BENCHMARK_WORKLOADS = {
    "BubbleSort_N4": {
        "category": "Sorting",
        "name": "Bubble Sort (N=4)",
        "code": """
int test() {
    int a[4];
    a[0] = 4; a[1] = 3; a[2] = 2; a[3] = 1;
    for (int i = 0; i < 3; i = i + 1) {
        for (int j = 0; j < 3 - i; j = j + 1) {
            if (a[j] > a[j + 1]) {
                int t = a[j];
                a[j] = a[j + 1];
                a[j + 1] = t;
            }
        }
    }
    return a[0];
}
""",
        "entry_func": "test",
        "args": []
    },
    "BubbleSort_N6": {
        "category": "Sorting",
        "name": "Bubble Sort (N=6)",
        "code": """
int test() {
    int a[6];
    a[0] = 6; a[1] = 5; a[2] = 4; a[3] = 3; a[4] = 2; a[5] = 1;
    for (int i = 0; i < 5; i = i + 1) {
        for (int j = 0; j < 5 - i; j = j + 1) {
            if (a[j] > a[j + 1]) {
                int t = a[j];
                a[j] = a[j + 1];
                a[j + 1] = t;
            }
        }
    }
    return a[0];
}
""",
        "entry_func": "test",
        "args": []
    },
    "BubbleSort_N8": {
        "category": "Sorting",
        "name": "Bubble Sort (N=8)",
        "code": """
int test() {
    int a[8];
    a[0] = 8; a[1] = 7; a[2] = 6; a[3] = 5; a[4] = 4; a[5] = 3; a[6] = 2; a[7] = 1;
    for (int i = 0; i < 7; i = i + 1) {
        for (int j = 0; j < 7 - i; j = j + 1) {
            if (a[j] > a[j + 1]) {
                int t = a[j];
                a[j] = a[j + 1];
                a[j + 1] = t;
            }
        }
    }
    return a[0];
}
""",
        "entry_func": "test",
        "args": []
    },
    "Fibonacci_N3": {
        "category": "Recursion",
        "name": "Fibonacci (N=3)",
        "code": """
int fib(int n) {
    if (n <= 1) return n;
    return fib(n - 1) + fib(n - 2);
}
int test() {
    return fib(3);
}
""",
        "entry_func": "test",
        "args": []
    },
    "Fibonacci_N4": {
        "category": "Recursion",
        "name": "Fibonacci (N=4)",
        "code": """
int fib(int n) {
    if (n <= 1) return n;
    return fib(n - 1) + fib(n - 2);
}
int test() {
    return fib(4);
}
""",
        "entry_func": "test",
        "args": []
    },
    "Fibonacci_N5": {
        "category": "Recursion",
        "name": "Fibonacci (N=5)",
        "code": """
int fib(int n) {
    if (n <= 1) return n;
    return fib(n - 1) + fib(n - 2);
}
int test() {
    return fib(5);
}
""",
        "entry_func": "test",
        "args": []
    },
    "Vector_Ops": {
        "category": "Data Structure",
        "name": "std::vector Push/Pop (x8)",
        "code": """
int test() {
    std::vector<int> v;
    v.push_back(10);
    v.push_back(20);
    v.push_back(30);
    v.push_back(40);
    v.pop_back();
    v.push_back(50);
    v.push_back(60);
    v.pop_back();
    return v.size();
}
""",
        "entry_func": "test",
        "args": []
    },
    "LinkedList_Ops": {
        "category": "Data Structure",
        "name": "Linked List 3-Node Chain",
        "code": """
struct Node {
    int val;
    Node* next;
};
int test() {
    Node* head = new Node();
    head->val = 100;
    Node* second = new Node();
    second->val = 200;
    head->next = second;
    Node* third = new Node();
    third->val = 300;
    second->next = third;
    int sum = head->val + head->next->val + head->next->next->val;
    return sum;
}
""",
        "entry_func": "test",
        "args": []
    }
}


def run_benchmark():
    print("=" * 100)
    print("AlgoLens Architecture Milestone 2 Performance Validation Benchmark")
    print("Comparing: Legacy Full Snapshots vs Event Protocol + Adaptive Checkpoints")
    print("=" * 100)

    results = []

    for key, spec in BENCHMARK_WORKLOADS.items():
        name = spec["name"]
        category = spec["category"]
        code = spec["code"]
        entry_func = spec["entry_func"]
        args = spec["args"]

        # --- 1. Legacy Pipeline ---
        interp_legacy = CPPInterpreter(max_recursion_depth=100)
        t0 = time.perf_counter()
        legacy_steps, _ = interp_legacy.interpret(code, entry_func, args)
        t_legacy_gen = (time.perf_counter() - t0) * 1000.0  # ms

        legacy_mem_bytes = get_deep_size(legacy_steps)
        legacy_json_str = dump_steps_json(legacy_steps)
        legacy_json_bytes = len(legacy_json_str.encode("utf-8"))

        num_legacy_snapshots = len(legacy_steps)

        # --- 2. Event + Checkpoint Pipeline ---
        interp_event = CPPInterpreter(max_recursion_depth=100)
        t0 = time.perf_counter()
        events, _, _ = interp_event.interpret_with_events(code, entry_func, args)
        engine = PlaybackEngine(events, checkpoint_policy=AdaptivePolicy(min_interval=8, max_interval=20))
        engine.build_checkpoints()
        t_event_gen = (time.perf_counter() - t0) * 1000.0  # ms

        num_events = len(events)
        num_checkpoints = len(engine.checkpoint_manager.checkpoints)

        events_mem_bytes = get_deep_size(events) + get_deep_size(engine.checkpoint_manager.checkpoints)
        events_json_str = dump_events_json(events)
        events_json_bytes = len(events_json_str.encode("utf-8"))

        # Payload savings
        mem_savings_pct = (1.0 - (events_mem_bytes / max(1, legacy_mem_bytes))) * 100.0
        json_savings_pct = (1.0 - (events_json_bytes / max(1, legacy_json_bytes))) * 100.0

        # --- 3. Playback Latency Measurements ---
        # Forward stepping
        t_fwd_start = time.perf_counter()
        engine.seek(0)
        fwd_steps_count = 0
        while engine.current_event_index < len(events):
            engine.step_forward()
            fwd_steps_count += 1
        t_fwd_total = time.perf_counter() - t_fwd_start
        avg_fwd_us = (t_fwd_total / max(1, fwd_steps_count)) * 1_000_000.0

        # Reverse stepping
        t_rev_start = time.perf_counter()
        rev_steps_count = 0
        while engine.current_event_index > 0:
            engine.step_reverse()
            rev_steps_count += 1
        t_rev_total = time.perf_counter() - t_rev_start
        avg_rev_us = (t_rev_total / max(1, rev_steps_count)) * 1_000_000.0

        # Random seek latency (test seeks to 25%, 50%, 75%, 100%, 10%)
        seek_targets = [
            int(len(events) * 0.25),
            int(len(events) * 0.50),
            int(len(events) * 0.75),
            len(events),
            int(len(events) * 0.10)
        ]
        seek_times_us = []
        for target in seek_targets:
            t_seek_start = time.perf_counter()
            engine.seek(target)
            seek_times_us.append((time.perf_counter() - t_seek_start) * 1_000_000.0)

        avg_seek_us = sum(seek_times_us) / len(seek_times_us)

        res = {
            "key": key,
            "category": category,
            "name": name,
            "legacy_steps": num_legacy_snapshots,
            "event_count": num_events,
            "checkpoints": num_checkpoints,
            "legacy_mem_kb": legacy_mem_bytes / 1024.0,
            "event_mem_kb": events_mem_bytes / 1024.0,
            "mem_savings_pct": mem_savings_pct,
            "legacy_json_kb": legacy_json_bytes / 1024.0,
            "event_json_kb": events_json_bytes / 1024.0,
            "json_savings_pct": json_savings_pct,
            "legacy_gen_ms": t_legacy_gen,
            "event_gen_ms": t_event_gen,
            "avg_fwd_us": avg_fwd_us,
            "avg_rev_us": avg_rev_us,
            "avg_seek_us": avg_seek_us
        }
        results.append(res)

        print(f"\nWorkload: {name} ({category})")
        print(f"  Legacy Steps (Snapshots): {num_legacy_snapshots} | Events: {num_events} | Checkpoints: {num_checkpoints} (ratio: {num_checkpoints/max(1,num_events):.1%})")
        print(f"  Memory Footprint: Legacy={res['legacy_mem_kb']:.1f} KB, Event+Ckpt={res['event_mem_kb']:.1f} KB [{mem_savings_pct:+.1f}% savings]")
        print(f"  Network JSON:     Legacy={res['legacy_json_kb']:.1f} KB, EventStream={res['event_json_kb']:.1f} KB [{json_savings_pct:+.1f}% savings]")
        print(f"  Generation Time:  Legacy={t_legacy_gen:.2f} ms, Event+Ckpt={t_event_gen:.2f} ms")
        print(f"  Step Latency:     Forward={avg_fwd_us:.2f} us/step, Reverse={avg_rev_us:.2f} us/step")
        print(f"  Random Seek Time: Avg={avg_seek_us:.2f} us ({avg_seek_us/1000.0:.3f} ms)")

    # --- Summary Table Printout ---
    print("\n" + "=" * 115)
    print("SUMMARY PERFORMANCE & RESOURCE METRICS TABLE")
    print("=" * 115)
    print(f"{'Workload':<24} | {'Steps':>6} | {'Events':>6} | {'Ckpts':>5} | {'LegacyMem':>11} | {'EventMem':>10} | {'MemSav%':>8} | {'LegacyJSON':>11} | {'EventJSON':>10} | {'JSONSav%':>9} | {'SeekAvg':>10}")
    print("-" * 115)
    for r in results:
        print(f"{r['name']:<24} | {r['legacy_steps']:>6} | {r['event_count']:>6} | {r['checkpoints']:>5} | {r['legacy_mem_kb']:>9.1f}KB | {r['event_mem_kb']:>8.1f}KB | {r['mem_savings_pct']:>7.1f}% | {r['legacy_json_kb']:>9.1f}KB | {r['event_json_kb']:>8.1f}KB | {r['json_savings_pct']:>8.1f}% | {r['avg_seek_us']:>8.2f}us")
    print("=" * 115)

    # Save benchmark results as JSON artifact for report reference
    out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "milestone_2_benchmark_results.json")
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved benchmark metrics to: {out_file}")


if __name__ == "__main__":
    run_benchmark()
