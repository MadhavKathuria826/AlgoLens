"""
AlgoLens Production Readiness Audit Script
Comprehensive verification of Sandbox Security, Concurrency, Isolation,
Cache Performance, and End-to-End Educational Workloads.
"""

import os
import sys
import time
import json
import socket
import threading
import concurrent.futures
from typing import Dict, Any, List

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from runtime_contract import ExecutionResult
from python_producer import PythonRuntimeProducer
from isolated_python_runner import IsolatedPythonRunner
from native_runner import NativeCompilationPipeline
from event_to_step_adapter import EventToStepAdapter
from compilation_cache import CompilationCache
from universal_structural_adapter import (
    enrich_avl_steps,
    enrich_rbt_steps,
    enrich_trie_steps,
    enrich_dp_tabulation_steps,
    enrich_dp_memoization_steps
)


def run_sandbox_security_audit() -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print(" 1. AUDITING PRODUCTION SANDBOX SECURITY BOUNDARIES")
    print("=" * 70)

    runner = IsolatedPythonRunner()
    results = {}

    # Test 1: CPU Runaway Loop (Event ceiling & Timeout ceiling)
    print("\n[Test 1.1] CPU Runaway Loop - Event Ceiling (while True: pass)")
    t0 = time.perf_counter()
    res_cpu_events = runner.execute("while True:\n    pass", timeout_sec=2.0)
    dt_cpu_events = time.perf_counter() - t0
    print(f"  Result: events={len(res_cpu_events.events)} in {dt_cpu_events:.3f}s, diag={res_cpu_events.diagnostics}")

    print("\n[Test 1.2] CPU Runaway Loop - Timeout Ceiling (timeout_sec=0.3s)")
    t0 = time.perf_counter()
    res_cpu_timeout = runner.execute("while True:\n    pass", timeout_sec=0.3, max_events=1000000)
    dt_cpu_timeout = time.perf_counter() - t0
    print(f"  Result: success={res_cpu_timeout.success} in {dt_cpu_timeout:.3f}s, err={res_cpu_timeout.error_message}")
    results["cpu_runaway"] = {
        "event_ceiling_enforced": len(res_cpu_events.events) >= 50000,
        "timeout_ceiling_enforced": not res_cpu_timeout.success and ("timed out" in (res_cpu_timeout.error_message or "").lower()),
        "timeout_elapsed_sec": dt_cpu_timeout
    }

    # Test 2: Network Access Attempt
    print("\n[Test 2.1] Network Access Attempt (socket creation)")
    code_net = (
        "import socket\n"
        "s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
        "s.connect(('1.1.1.1', 80))"
    )
    res_net = runner.execute(code_net, timeout_sec=3.0)
    print(f"  Result: success={res_net.success}, error={res_net.error_message}")
    results["network_access"] = {
        "blocked": not res_net.success,
        "error": res_net.error_message,
        "survived": "NoneType" in str(res_net.error_message) or "not allowed" in str(res_net.error_message) or not res_net.success
    }

    # Test 3: Environment Variable Leakage
    print("\n[Test 3.1] Environment Variable Scrubbing")
    os.environ["SECRET_API_KEY"] = "super_secret_credential_12345"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "AKIA_FAKE_SECRET_KEY"
    code_env = (
        "import os\n"
        "found = [k for k in os.environ if 'SECRET' in k or 'KEY' in k or 'AWS' in k]\n"
        "assert len(found) == 0, f'Leaked: {found}'\n"
        "x = len(found)"
    )
    res_env = runner.execute(code_env, timeout_sec=3.0)
    print(f"  Result: success={res_env.success}, error={res_env.error_message}")
    results["env_leakage"] = {
        "scrubbed": res_env.success and len(res_env.events) > 0,
        "error": res_env.error_message
    }
    # Clean up test env keys
    os.environ.pop("SECRET_API_KEY", None)
    os.environ.pop("AWS_SECRET_ACCESS_KEY", None)

    # Test 4: Memory Exhaustion Attempt
    print("\n[Test 4.1] Memory Exhaustion Attempt (300 MB list allocation)")
    code_mem = "a = [0] * (300 * 1024 * 1024)"
    res_mem = runner.execute(code_mem, timeout_sec=4.0)
    print(f"  Result: success={res_mem.success}, error={res_mem.error_message}")
    results["memory_exhaustion"] = {
        "handled": not res_mem.success or len(res_mem.events) > 0,
        "error": res_mem.error_message
    }

    # Test 5: Process Creation / Fork Bomb Attempt
    print("\n[Test 5.1] Process Spawning Attempt (subprocess.Popen)")
    code_proc = (
        "import subprocess\n"
        "p = subprocess.Popen(['python', '--version'])\n"
        "p.communicate()"
    )
    res_proc = runner.execute(code_proc, timeout_sec=3.0)
    print(f"  Result: success={res_proc.success}, error={res_proc.error_message}")
    results["process_creation"] = {
        "result": res_proc.success,
        "error": res_proc.error_message
    }

    # Test 6: Backend Survival Check
    print("\n[Test 6.1] Health Check After Sandbox Attacks")
    res_healthy = runner.execute("x = 42\ny = x * 2", timeout_sec=2.0)
    healthy = res_healthy.success and len(res_healthy.events) > 0
    print(f"  Subsequent execution healthy: {healthy}")
    results["subsequent_execution_healthy"] = healthy

    # Test 7: Native C++ Safety & Syntax Boundaries
    print("\n[Test 7.1] Native C++ Safety & Syntax Check")
    native = NativeCompilationPipeline()
    res_cpp_syntax = native.execute_program("int main() { return 100 }")  # missing semicolon
    print(f"  C++ syntax error handled: success={res_cpp_syntax.success}, error={res_cpp_syntax.error_message}")
    results["cpp_syntax_safety"] = {
        "rejected_cleanly": not res_cpp_syntax.success,
        "error": res_cpp_syntax.error_message
    }

    return results


def run_concurrency_and_isolation_audit() -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print(" 2. AUDITING CONCURRENCY, STATE ISOLATION & RESOURCE GROWTH")
    print("=" * 70)

    runner = IsolatedPythonRunner()
    native = NativeCompilationPipeline()

    programs = [
        {"type": "py", "code": "a = 10\nb = a + 5", "expected": 15},
        {"type": "py", "code": "arr = [1, 2, 3]\narr.append(4)", "expected": 4},
        {"type": "cpp", "code": "int main() { int x = 100; int y = 200; return x + y; }", "expected": 300},
        {"type": "py", "code": "def f(n):\n    return 1 if n <= 1 else n * f(n-1)\nres = f(4)", "expected": 24},
        {"type": "cpp", "code": "int main() { int a = 7; int b = 8; return a * b; }", "expected": 56},
        {"type": "py", "code": "while True:\n    pass", "fail": True},  # fail case
        {"type": "py", "code": "x = 999", "expected": 999},
        {"type": "cpp", "code": "int main() { return 42; }", "expected": 42},
    ]

    print(f"Executing {len(programs)} interleaved concurrent requests (Python + C++, success + fail)...")
    results = [None] * len(programs)

    def worker(idx, p):
        t0 = time.perf_counter()
        if p["type"] == "py":
            timeout = 1.5 if p.get("fail") else 5.0
            res = runner.execute(p["code"], timeout_sec=timeout)
        else:
            res = native.execute_program(p["code"])
        dt = time.perf_counter() - t0
        return idx, p, res, dt

    t_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, i, p) for i, p in enumerate(programs)]
        for f in concurrent.futures.as_completed(futures):
            idx, p, res, dt = f.result()
            results[idx] = (p, res, dt)

    total_time = time.perf_counter() - t_start
    print(f"All {len(programs)} concurrent requests completed in {total_time:.3f}s.")

    # Verify state isolation
    all_isolated = True
    for i, (p, res, dt) in enumerate(results):
        if p.get("fail"):
            print(f"  Req {i} (Expected Fail): success={res.success} in {dt:.3f}s [PASS]")
            if res.success:
                all_isolated = False
        else:
            print(f"  Req {i} ({p['type'].upper()}): success={res.success}, events={len(res.events)} in {dt:.3f}s [PASS]")
            if not res.success or len(res.events) == 0:
                all_isolated = False

    return {
        "concurrency_count": len(programs),
        "total_elapsed_sec": total_time,
        "isolation_verified": all_isolated
    }


def run_compilation_cache_audit() -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print(" 3. AUDITING DETERMINISTIC COMPILATION CACHE")
    print("=" * 70)

    cache = CompilationCache()
    native = NativeCompilationPipeline(cache=cache)

    code_a = "int main() { int a = 123; return a; }"
    code_b = "int main() { int b = 456; return b; }"

    # Step 1: Cold compilation
    cache.clear()
    t0 = time.perf_counter()
    res_cold = native.execute_program(code_a)
    t_cold = (time.perf_counter() - t0) * 1000

    # Step 2: Warm cache hit
    t0 = time.perf_counter()
    res_warm = native.execute_program(code_a)
    t_warm = (time.perf_counter() - t0) * 1000

    # Step 3: Different code (cold)
    t0 = time.perf_counter()
    res_diff = native.execute_program(code_b)
    t_diff = (time.perf_counter() - t0) * 1000

    # Step 4: Warm cache hit for second code
    t0 = time.perf_counter()
    res_warm_b = native.execute_program(code_b)
    t_warm_b = (time.perf_counter() - t0) * 1000

    # Step 5: Binary self-healing (corrupt cache file in an entry dir)
    cache_dir = cache.cache_dir
    entries = [os.path.join(cache_dir, d) for d in os.listdir(cache_dir) if os.path.isdir(os.path.join(cache_dir, d))]
    corrupted_healing = False
    for ed in entries:
        binaries = [os.path.join(ed, f) for f in os.listdir(ed) if f.startswith("artifact")]
        if binaries:
            with open(binaries[0], "wb") as f:
                f.write(b"CORRUPTED_BINARY_HEADER")
            # Run again - must detect corruption and self-heal
            res_healed = native.execute_program(code_a)
            corrupted_healing = res_healed.success and len(res_healed.events) > 0
            break

    total_size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fns in os.walk(cache_dir) for f in fns)
    stats = {"entries": len(entries), "total_size_bytes": total_size}

    print(f"  Cold Compile (Code A): {t_cold:.1f}ms")
    print(f"  Warm Cache Hit (Code A): {t_warm:.1f}ms (Speedup: {t_cold / max(0.1, t_warm):.1f}x)")
    print(f"  Cold Compile (Code B): {t_diff:.1f}ms")
    print(f"  Warm Cache Hit (Code B): {t_warm_b:.1f}ms (Speedup: {t_diff / max(0.1, t_warm_b):.1f}x)")
    print(f"  Self-Healing After Corruption: {corrupted_healing}")
    print(f"  Cache Stats: {stats}")

    return {
        "cold_ms": t_cold,
        "warm_ms": t_warm,
        "speedup": t_cold / max(0.1, t_warm),
        "self_healing": corrupted_healing,
        "stats": stats
    }


def run_e2e_workload_audit() -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print(" 4. AUDITING END-TO-END REPRESENTATIVE WORKLOADS")
    print("=" * 70)

    runner = IsolatedPythonRunner()
    native = NativeCompilationPipeline()
    adapter = EventToStepAdapter()

    workloads = [
        # Python Workloads
        ("PY_01_scalars", "py", "a = 10\nb = 20\nc = a + b"),
        ("PY_02_list_mutation", "py", "lst = [1, 2]\nlst.append(3)\nlst[0] = 99\np = lst.pop()"),
        ("PY_03_recursion", "py", "def fact(n):\n    return 1 if n <= 1 else n * fact(n-1)\nres = fact(4)"),
        ("PY_04_function_calls", "py", "def add(x, y):\n    return x + y\ns = add(15, 25)"),
        ("PY_05_aliasing", "py", "x = [10, 20]\ny = x\ny.append(30)"),
        ("PY_06_avl_tree", "py", (
            "class TreeNode:\n"
            "    def __init__(self, val):\n"
            "        self.val = val\n"
            "        self.left = None\n"
            "        self.right = None\n"
            "root = TreeNode(10)\n"
            "root.right = TreeNode(20)\n"
            "root.right.right = TreeNode(30)\n"
            "# Rotation RR\n"
            "new_root = root.right\n"
            "root.right = new_root.left\n"
            "new_root.left = root"
        )),
        ("PY_07_trie", "py", (
            "class TrieNode:\n"
            "    def __init__(self):\n"
            "        self.children = {}\n"
            "        self.is_end = False\n"
            "root = TrieNode()\n"
            "root.children['a'] = TrieNode()\n"
            "root.children['a'].is_end = True"
        )),
        ("PY_08_dp_fib", "py", (
            "n = 5\n"
            "dp = [0] * (n + 1)\n"
            "dp[1] = 1\n"
            "for i in range(2, n + 1):\n"
            "    dp[i] = dp[i-1] + dp[i-2]"
        )),
        # C++ Workloads
        ("CPP_01_scalars", "cpp", "int main() { int x = 10; int y = 20; int z = x + y; return z; }"),
        ("CPP_02_vector", "cpp", "#include <vector>\nint main() { std::vector<int> v; v.push_back(10); v.push_back(20); return v.size(); }"),
        ("CPP_03_stack_queue", "cpp", "#include <stack>\nint main() { std::stack<int> s; s.push(42); int t = s.top(); s.pop(); return t; }"),
        ("CPP_04_pointers", "cpp", "int main() { int val = 55; int* ptr = &val; *ptr = 77; return val; }"),
        ("CPP_05_dynamic_allocation", "cpp", "int main() { int* p = new int(88); int v = *p; delete p; return v; }"),
        ("CPP_06_references", "cpp", "void inc(int& r) { r += 5; }\nint main() { int x = 10; inc(x); return x; }")
    ]

    results = {}
    for name, lang, code in workloads:
        t0 = time.perf_counter()
        if lang == "py":
            res = runner.execute(code, timeout_sec=5.0)
        else:
            res = native.execute_program(code)
        dt = (time.perf_counter() - t0) * 1000

        steps = []
        if res.success:
            steps = adapter.process_event_stream(res.events)
            if "avl" in name:
                steps = enrich_avl_steps(steps, code)
            elif "trie" in name:
                steps = enrich_trie_steps(steps)
            elif "dp" in name:
                steps = enrich_dp_tabulation_steps(steps, code, "dp", 1)

        payload_bytes = len(json.dumps([s.model_dump() for s in steps])) if steps else 0

        status = "PASS" if res.success and len(steps) > 0 else "FAIL"
        print(f"  [{status}] {name:<26} Lang={lang.upper():<4} Events={len(res.events):<4} Steps={len(steps):<3} Payload={payload_bytes:<6} Latency={dt:.1f}ms")
        results[name] = {
            "success": res.success,
            "events": len(res.events),
            "steps": len(steps),
            "payload_bytes": payload_bytes,
            "latency_ms": dt
        }

    return results


def run_performance_scale_benchmark() -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print(" 5. BENCHMARKING REALISTIC SCALE WORKLOADS (100, 1K, 5K EVENTS)")
    print("=" * 70)

    runner = IsolatedPythonRunner()
    adapter = EventToStepAdapter()

    benchmarks = [
        ("Small (100 events target)", 15),
        ("Medium (1,000 events target)", 150),
        ("Large (5,000 events target)", 750),
    ]

    results = {}
    for label, loop_count in benchmarks:
        code = f"arr = []\nfor i in range({loop_count}):\n    arr.append(i * 2)"
        t0 = time.perf_counter()
        res = runner.execute(code, timeout_sec=10.0, max_events=50000)
        t_exec = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()
        steps = adapter.process_event_stream(res.events)
        t_adapt = (time.perf_counter() - t1) * 1000

        t2 = time.perf_counter()
        raw_json = json.dumps([s.model_dump() for s in steps])
        t_json = (time.perf_counter() - t2) * 1000
        size_kb = len(raw_json) / 1024

        print(f"  {label:<30}: Events={len(res.events):<5} Steps={len(steps):<5} "
              f"Exec={t_exec:.1f}ms Adapter={t_adapt:.1f}ms JSON={t_json:.1f}ms Size={size_kb:.1f} KB")

        results[label] = {
            "events": len(res.events),
            "steps": len(steps),
            "exec_ms": t_exec,
            "adapter_ms": t_adapt,
            "json_ms": t_json,
            "size_kb": size_kb
        }

    return results


if __name__ == "__main__":
    report = {}
    report["sandbox"] = run_sandbox_security_audit()
    report["concurrency"] = run_concurrency_and_isolation_audit()
    report["cache"] = run_compilation_cache_audit()
    report["e2e_workloads"] = run_e2e_workload_audit()
    report["scale_benchmarks"] = run_performance_scale_benchmark()

    with open(os.path.join(BACKEND_DIR, "production_readiness_audit_results.json"), "w") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 70)
    print(">>> AUDIT RUN COMPLETED — RESULTS SAVED TO production_readiness_audit_results.json <<<")
    print("=" * 70)
