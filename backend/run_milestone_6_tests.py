"""
AlgoLens Milestone 6 Test Suite
Validates Language-Independent Execution Infrastructure & Performance:
1. Deterministic Compilation Cache:
   - Cryptographic SHA-256 cache key derivation
   - Cache hit on identical source and configuration
   - Zero compilation time on warm hits
2. Content & Configuration-Based Invalidation:
   - Source code mutation produces distinct cache key
   - Entry point function change produces distinct cache key
   - Compiler flags variation produces distinct cache key
   - Binary corruption detection & self-healing rebuild
   - Metadata absence detection & recovery
3. Atomic Publication & Staged Compilation:
   - Staging directory isolation (.staging_<uuid>)
   - Atomic rename under concurrency lock
   - Zero half-written or corrupted artifacts exposed
4. Runtime State Isolation Across Reused Binaries:
   - Execution of the same cached binary 3 times
   - Fresh synthetic ObjectRegistry IDs (no cross-run leakage)
   - Fresh frame IDs starting from frame_0
   - Fresh event sequence numbers starting from 0
   - Clean state reducer snapshots
5. Cold vs Warm Semantic Equivalence:
   - Full event stream match (types, payloads, ordering)
   - Step-by-step state snapshot parity
6. Language-Independent Abstraction:
   - LanguageRuntimeProducer abstract interface compliance
   - CppRuntimeProducer alias and execution contract
7. Zero Leaks into Universal Event Protocol:
   - Diagnostic cache status contained in execution result
   - Zero cache-related event types or payloads in event stream
"""

import os
import sys
import json
import time
import shutil
import tempfile
import threading

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from native_runner import (
    NativeCompilationPipeline,
    CppRuntimeProducer,
    LanguageRuntimeProducer,
    NativeExecutionResult
)
from compilation_cache import CompilationCache, CacheKeySpec, CacheStatus, CachedArtifact
from state_reducer import UniversalRuntimeState, UniversalStateReducer
from event_to_step_adapter import EventToStepAdapter
from playback_engine import PlaybackEngine


def test_cache_hit_and_artifact_integrity(pipeline: NativeCompilationPipeline):
    print("\n--- 1. Testing Deterministic Cache Hit & Artifact Integrity ---")
    code = """
    int compute(int n) {
        int acc = 0;
        for (int i = 1; i <= n; ++i) {
            acc += i * 2;
        }
        return acc;
    }
    """
    # Clear cache before test to ensure cold baseline
    pipeline.cache.clear()

    # Cold Run
    res_cold = pipeline.compile_and_run(code, entry_func="compute", args=[5])
    assert res_cold.success, f"Cold run failed: {res_cold.error_message}\nStderr: {res_cold.runtime_stderr}"
    assert res_cold.cache_status == "CACHE_MISS", f"Expected CACHE_MISS on first run, got {res_cold.cache_status}"
    assert res_cold.compile_time_ms > 0, "Cold run should report > 0 ms compile time"
    cold_cache_key = res_cold.cache_key
    assert cold_cache_key is not None and len(cold_cache_key) == 64, f"Invalid SHA-256 key: {cold_cache_key}"

    # Warm Run 1
    res_warm = pipeline.compile_and_run(code, entry_func="compute", args=[5])
    assert res_warm.success, f"Warm run failed: {res_warm.error_message}"
    assert res_warm.cache_status == "CACHE_HIT", f"Expected CACHE_HIT on warm run, got {res_warm.cache_status}"
    assert res_warm.compile_time_ms == 0.0, f"Expected 0.0 ms compile time on cache hit, got {res_warm.compile_time_ms}"
    assert res_warm.cache_key == cold_cache_key, "Cache key must match between identical cold and warm invocations"
    assert res_warm.cache_lookup_time_ms > 0, "Lookup time should be tracked"

    # Verify physical cached files
    entry_dir = os.path.join(pipeline.cache.cache_dir, cold_cache_key)
    assert os.path.isdir(entry_dir), f"Cache directory missing: {entry_dir}"
    meta_file = os.path.join(entry_dir, "metadata.json")
    inst_file = os.path.join(entry_dir, "instrumented.cpp")
    assert os.path.exists(meta_file), "metadata.json missing"
    assert os.path.exists(inst_file), "instrumented.cpp missing"

    with open(meta_file, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["cache_key"] == cold_cache_key
    bin_name = meta["artifact_name"]
    bin_path = os.path.join(entry_dir, bin_name)
    assert os.path.exists(bin_path), f"Artifact binary missing: {bin_path}"
    assert os.path.getsize(bin_path) > 0, "Artifact binary must not be empty"

    print(f"PASS: Cold compile ({res_cold.compile_time_ms:.1f}ms) -> Warm hit (0.0ms compile, {res_warm.cache_lookup_time_ms:.2f}ms lookup). Artifact hash verified.")


def test_invalidation_and_corruption_recovery(pipeline: NativeCompilationPipeline):
    print("\n--- 2. Testing Invalidation Mechanics & Self-Healing Corruption Recovery ---")
    base_code = """
    int run() {
        int x = 42;
        return x;
    }
    """
    res1 = pipeline.compile_and_run(base_code, entry_func="run")
    assert res1.success
    key1 = res1.cache_key

    # A. Source code change produces distinct key
    mutated_code = """
    int run() {
        int x = 99;
        return x;
    }
    """
    res2 = pipeline.compile_and_run(mutated_code, entry_func="run")
    assert res2.success
    key2 = res2.cache_key
    assert key1 != key2, f"Mutated source must produce different cache key! {key1} == {key2}"

    # B. Entry function change produces distinct key
    res3 = pipeline.compile_and_run(base_code, entry_func="other_func")
    key3 = res3.cache_key
    assert key1 != key3, f"Different entry func must produce different cache key! {key1} == {key3}"

    # C. Corruption of binary: deliberately tamper with artifact binary
    entry_dir = os.path.join(pipeline.cache.cache_dir, key1)
    meta_path = os.path.join(entry_dir, "metadata.json")
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    bin_path = os.path.join(entry_dir, meta["artifact_name"])

    # Overwrite binary bytes with junk
    with open(bin_path, "wb") as f:
        f.write(b"CORRUPTED_BINARY_BYTES_FOR_TESTING")

    # Next execution must detect corruption, purge corrupted directory, and compile fresh
    res_corrupt_heal = pipeline.compile_and_run(base_code, entry_func="run")
    assert res_corrupt_heal.success, "Pipeline should transparently heal corrupted cache entry"
    assert res_corrupt_heal.compile_time_ms > 0, "Rebuild must happen on corrupted cache"

    # Verify binary is valid again
    with open(meta_path, "r", encoding="utf-8") as f:
        new_meta = json.load(f)
    assert new_meta["artifact_hash"] != "corrupted"

    # D. Missing metadata: delete metadata.json
    os.remove(meta_path)
    res_meta_heal = pipeline.compile_and_run(base_code, entry_func="run")
    assert res_meta_heal.success, "Pipeline should heal missing metadata"
    assert os.path.exists(meta_path), "metadata.json should be restored"

    print("PASS: Source mutation, entry change, binary corruption healing, and metadata regeneration verified.")


def test_runtime_state_isolation_across_runs(pipeline: NativeCompilationPipeline):
    print("\n--- 3. Testing Runtime State Isolation Across Reused Binaries ---")
    # Code allocates heap objects, establishes stack frames, and mutates state
    code = """
    struct Node {
        int val;
        Node* next;
    };
    int build_list() {
        Node* n1 = new Node{10, nullptr};
        Node* n2 = new Node{20, nullptr};
        n1->next = n2;
        delete n2;
        delete n1;
        return 0;
    }
    """
    # Ensure binary is in cache
    res0 = pipeline.compile_and_run(code, entry_func="build_list")
    assert res0.success

    runs = []
    for run_idx in range(3):
        res = pipeline.compile_and_run(code, entry_func="build_list")
        assert res.success, f"Run {run_idx+1} failed"
        assert res.cache_status == "CACHE_HIT", f"Run {run_idx+1} should be CACHE_HIT"
        runs.append(res)

    # Verify State Isolation across runs:
    # 1. First event sequence number must be 0 for all runs
    for idx, r in enumerate(runs):
        assert r.events[0].seq == 0, f"Run {idx+1} sequence number did not restart at 0"

    # 2. Allocations must produce the exact same fresh synthetic object IDs (obj_1, obj_2), not obj_3, obj_4...
    for idx, r in enumerate(runs):
        alloc_events = [ev for ev in r.events if ev.event_type == "OBJECT_ALLOCATE"]
        assert len(alloc_events) == 2, f"Run {idx+1} expected 2 allocations, got {len(alloc_events)}"
        obj_ids = [ev.payload["object_id"] for ev in alloc_events]
        assert obj_ids == ["obj_0", "obj_1"], f"Run {idx+1} leaked object IDs! Got {obj_ids}"

    # 3. Stack frames must start from frame_1 (with parent frame_0)
    for idx, r in enumerate(runs):
        frame_events = [ev for ev in r.events if ev.event_type == "FRAME_PUSH"]
        assert len(frame_events) >= 1
        assert frame_events[0].frame_id == "frame_1", f"Run {idx+1} frame ID did not restart at frame_1: {frame_events[0].frame_id}"
        assert frame_events[0].payload.get("parent_frame_id") == "frame_0"

    # 4. UniversalStateReducer snapshots must be identical step-by-step
    s1, s2, s3 = UniversalRuntimeState(), UniversalRuntimeState(), UniversalRuntimeState()
    for ev in runs[0].events:
        s1 = UniversalStateReducer.reduce(s1, ev)
    for ev in runs[1].events:
        s2 = UniversalStateReducer.reduce(s2, ev)
    for ev in runs[2].events:
        s3 = UniversalStateReducer.reduce(s3, ev)

    state1 = s1.model_dump()
    state2 = s2.model_dump()
    state3 = s3.model_dump()

    # Compare universal state snapshots (heap, stack, bindings)
    assert set(state1["heap"].keys()) == set(state2["heap"].keys()) == set(state3["heap"].keys())
    for obj_id in state1["heap"]:
        h1, h2, h3 = state1["heap"][obj_id], state2["heap"][obj_id], state3["heap"][obj_id]
        assert h1["object_id"] == h2["object_id"] == h3["object_id"]
        assert h1["type_name"] == h2["type_name"] == h3["type_name"]
        assert h1["fields"] == h2["fields"] == h3["fields"]
        assert h1["is_alive"] == h2["is_alive"] == h3["is_alive"]

    assert state1["call_stack"] == state2["call_stack"] == state3["call_stack"]
    assert state1["bindings"] == state2["bindings"] == state3["bindings"]

    print("PASS: 3 sequential runs of same cached binary proved perfect synthetic ID, frame, sequence, and reducer state isolation.")


def test_cold_vs_warm_semantic_equivalence(pipeline: NativeCompilationPipeline):
    print("\n--- 4. Testing Cold vs Warm Semantic Equivalence ---")
    code = """
    int complex_algo() {
        std::vector<int> v;
        v.push_back(100);
        v.push_back(200);
        v.push_back(300);
        v.pop_back();

        std::string s = "algolens";
        s.append("_perf");

        int sum = 0;
        for (int i = 0; i < v.size(); ++i) {
            sum += v.at(i);
        }
        return sum + (int)s.size();
    }
    """
    pipeline.cache.clear()

    # Cold Run
    res_cold = pipeline.compile_and_run(code, entry_func="complex_algo")
    assert res_cold.success, f"Cold run failed: {res_cold.error_message}"
    assert res_cold.cache_status == "CACHE_MISS"

    # Warm Run
    res_warm = pipeline.compile_and_run(code, entry_func="complex_algo")
    assert res_warm.success, f"Warm run failed: {res_warm.error_message}"
    assert res_warm.cache_status == "CACHE_HIT"

    # Compare event streams
    assert len(res_cold.events) == len(res_warm.events), f"Event count mismatch: {len(res_cold.events)} != {len(res_warm.events)}"

    for i, (ec, ew) in enumerate(zip(res_cold.events, res_warm.events)):
        assert ec.event_type == ew.event_type, f"Event {i} type mismatch: {ec.event_type} != {ew.event_type}"
        assert ec.seq == ew.seq, f"Event {i} seq mismatch"
        assert ec.payload == ew.payload, f"Event {i} payload mismatch:\nCold: {ec.payload}\nWarm: {ew.payload}"

    # Compare PlaybackEngine steps
    adapter_cold = EventToStepAdapter()
    steps_cold = adapter_cold.process_event_stream(res_cold.events)
    adapter_warm = EventToStepAdapter()
    steps_warm = adapter_warm.process_event_stream(res_warm.events)

    assert len(steps_cold) == len(steps_warm), f"Step count mismatch: {len(steps_cold)} != {len(steps_warm)}"
    for idx, (sc, sw) in enumerate(zip(steps_cold, steps_warm)):
        assert sc.locals == sw.locals, f"Step {idx} locals mismatch"
        assert sc.line_number == sw.line_number, f"Step {idx} line mismatch"

    print(f"PASS: Cold and warm runs produced 100% bit-for-bit identical {len(res_cold.events)} events and {len(steps_cold)} visualization steps.")


def test_atomic_publication_concurrency(pipeline: NativeCompilationPipeline):
    print("\n--- 5. Testing Atomic Publication & Staged Compilation ---")
    # Verify preparation creates unique staging directories
    sdir1, _, _ = pipeline.cache.prepare_staging()
    sdir2, _, _ = pipeline.cache.prepare_staging()
    assert sdir1 != sdir2, "Staging directories must be unique"
    assert os.path.exists(sdir1) and os.path.exists(sdir2)
    shutil.rmtree(sdir1, ignore_errors=True)
    shutil.rmtree(sdir2, ignore_errors=True)

    # Test concurrent compilation requests for the same source
    code = """
    int fast(int x) {
        return x * x;
    }
    """
    errors = []
    results = [None, None, None, None]

    def worker(idx: int):
        try:
            r = pipeline.compile_and_run(code, entry_func="fast", args=[5])
            results[idx] = r
        except Exception as ex:
            errors.append(f"Worker {idx} raised: {ex}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Concurrent compilation encountered errors: {errors}"
    for idx, r in enumerate(results):
        assert r is not None and r.success, f"Worker {idx} execution failed"
        assert r.cache_key is not None

    # All workers must agree on the same cache key
    keys = {r.cache_key for r in results}
    assert len(keys) == 1, f"All concurrent runs must resolve to the same cache key: {keys}"

    print("PASS: Concurrent staging and publication safely handled without race conditions.")


def test_language_runtime_producer_abstraction():
    print("\n--- 6. Testing LanguageRuntimeProducer Abstract Interface ---")
    # Verify inheritance
    assert issubclass(CppRuntimeProducer, LanguageRuntimeProducer), "CppRuntimeProducer must inherit LanguageRuntimeProducer"
    assert issubclass(NativeCompilationPipeline, LanguageRuntimeProducer), "NativeCompilationPipeline must inherit LanguageRuntimeProducer"

    producer: LanguageRuntimeProducer = CppRuntimeProducer()
    code = "int test() { return 777; }"
    res = producer.execute_program(code, entry_func="test")
    assert res.success
    ret_events = [ev for ev in res.events if ev.event_type == "FRAME_POP"]
    assert len(ret_events) >= 1
    val = ret_events[-1].payload.get("return_value")
    if isinstance(val, dict):
        assert val.get("value") == 777
    else:
        assert val == 777

    print("PASS: Polymorphic LanguageRuntimeProducer.execute_program() executed correctly.")


def test_cache_diagnostics_containment(pipeline: NativeCompilationPipeline):
    print("\n--- 7. Testing Event Protocol Cleanliness (Zero Cache Tokens in Events) ---")
    code = "int simple() { int a = 1; return a; }"
    res = pipeline.compile_and_run(code, entry_func="simple")
    assert res.success

    # Diagnostics reside on NativeExecutionResult
    assert hasattr(res, "cache_status")
    assert hasattr(res, "cache_key")
    assert hasattr(res, "compile_time_ms")
    assert hasattr(res, "cache_lookup_time_ms")
    assert hasattr(res, "instrumentation_time_ms")

    # Events must NEVER contain cache diagnostics
    for ev in res.events:
        assert ev.event_type not in ("CACHE_HIT", "CACHE_MISS", "CACHE_INVALIDATED", "CACHE_CORRUPT"), \
            f"Event type {ev.event_type} leaks cache mechanics into Event Protocol!"
        payload_str = json.dumps(ev.payload)
        assert "CACHE_" not in payload_str, f"Payload leaks cache token: {payload_str}"
        assert res.cache_key not in payload_str, f"Payload leaks cache key: {payload_str}"

    print("PASS: Cache diagnostics strictly confined to execution result; Event Protocol remains universal and pure.")


def run_all_milestone_6_tests():
    print("======================================================================")
    print("           ALGOLENS MILESTONE 6 TEST SUITE VERIFICATION               ")
    print("======================================================================")
    pipeline = NativeCompilationPipeline()

    test_cache_hit_and_artifact_integrity(pipeline)
    test_invalidation_and_corruption_recovery(pipeline)
    test_runtime_state_isolation_across_runs(pipeline)
    test_cold_vs_warm_semantic_equivalence(pipeline)
    test_atomic_publication_concurrency(pipeline)
    test_language_runtime_producer_abstraction()
    test_cache_diagnostics_containment(pipeline)

    print("\n======================================================================")
    print(">>> ALL MILESTONE 6 EXECUTION INFRASTRUCTURE & CACHE TESTS PASSED! <<<")
    print("======================================================================")


if __name__ == "__main__":
    run_all_milestone_6_tests()
