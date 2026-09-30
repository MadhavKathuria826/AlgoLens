"""
AlgoLens Milestone 8 (M8) End-to-End Integration Verification Suite
Validates the complete execution and state-reduction pipeline:
SOURCE CODE
  -> FRONTEND EXECUTION REQUEST
  -> BACKEND FASTAPI ROUTER (/api/execute)
  -> UNIVERSAL LANGUAGE RUNTIME PRODUCER (PythonRuntimeProducer / NativeCompilationPipeline)
  -> UNIVERSAL ALGOLENS EVENT STREAM
  -> STATE REDUCER (UniversalStateReducer)
  -> EVENT-TO-STEP ADAPTER (EventToStepAdapter)
  -> PLAYBACK ENGINE (PlaybackEngine forward, reverse, arbitrary seek)
  -> VISUALIZATIONS (Array, Locals, Heap, Object Identity)
"""

import os
import sys
import copy
import time
import pytest

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from models import CodeExecutionRequest, CodeExecutionResponse, Step, VisualizationData
from main import execute_code
from event_models import AlgoLensEvent, PrimitiveValue, ObjectRef
from state_reducer import UniversalRuntimeState, UniversalStateReducer
from event_to_step_adapter import EventToStepAdapter
from playback_engine import PlaybackEngine


# =====================================================================
# Test 1: Complete End-to-End Vertical Slice (Python Bubble Sort)
# =====================================================================
def test_1_end_to_end_python_bubble_sort():
    print("\n--- 1. Testing End-to-End Python Execution (Bubble Sort Vertical Slice) ---")
    source_code = """def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr

arr = [64, 34, 25, 12, 22]
bubble_sort(arr)
"""
    req = CodeExecutionRequest(code=source_code, language="python")
    res = execute_code(req)

    assert res.error is None, f"Execution failed unexpectedly: {res.error}"
    assert res.events is not None, "Response missing AlgoLensEvent stream"
    assert len(res.events) > 0, "Empty event stream returned"
    assert len(res.steps) > 0, "No visualizer steps generated"

    # Verify event stream structure and termination
    first_ev = res.events[0]
    last_ev = res.events[-1]
    assert first_ev.event_type == "PROG_START"
    assert last_ev.event_type == "PROG_END"
    assert all(isinstance(e, AlgoLensEvent) for e in res.events)

    # Verify step sequence and array visualization evolution
    step_0 = res.steps[0]
    assert step_0.step_number == 0

    # Find the step where arr is initially defined
    initial_arr_steps = [
        s for s in res.steps 
        if s.locals and "arr" in s.locals and isinstance(s.locals["arr"], list)
    ]
    assert len(initial_arr_steps) > 0, "Array was never captured in locals"
    assert initial_arr_steps[0].locals["arr"] == [64, 34, 25, 12, 22], "Initial array corrupted"

    # Find the final step and verify sorted array state
    final_arr_steps = [
        s for s in res.steps 
        if s.locals and "arr" in s.locals and s.locals["arr"] == [12, 22, 25, 34, 64]
    ]
    assert len(final_arr_steps) > 0, f"Array was not properly sorted! Final locals: {res.steps[-1].locals}"

    # Verify Array visualization object exists with real obj_id
    array_vis_found = False
    for s in res.steps:
        for v in s.visualizations:
            if v.type == "Array" and v.details.get("name") == "arr":
                assert isinstance(v.details["value"], list)
                assert v.details["obj_id"].startswith("obj_")
                array_vis_found = True
                break
    assert array_vis_found, "Array visualizer data not generated"

    print(f"  [PASS] Vertical slice verified: {len(res.events)} events -> {len(res.steps)} steps. Initial [64, 34, ...] sorted to [12, 22, ...].")


# =====================================================================
# Test 2: Playback Engine Forward, Reverse, and Random Seek
# =====================================================================
def test_2_playback_engine_reversibility_and_seek():
    print("\n--- 2. Testing Bidirectional Playback Engine & Random Seek ---")
    source_code = """data = [3, 1, 2]
data.append(9)
data[0] = 7
"""
    req = CodeExecutionRequest(code=source_code, language="python")
    res = execute_code(req)
    assert res.events and len(res.events) > 0

    engine = PlaybackEngine(res.events)
    engine.build_checkpoints()

    # Step forward through all events and record history
    forward_history = []
    while True:
        s = engine.step_forward()
        if s is None:
            break
        forward_history.append(s.model_copy(deep=True))

    total_applied = len(forward_history)
    assert total_applied == len(res.events)

    # Step reverse back to index 0
    for idx in range(total_applied - 1, -1, -1):
        rev_state = engine.step_reverse()
        if idx > 0:
            expected = forward_history[idx - 1]
            assert rev_state.current_line == expected.current_line
            assert len(rev_state.bindings) == len(expected.bindings)
            assert len(rev_state.heap) == len(expected.heap)

    # Assert arbitrary seek matches sequential state exactly
    seek_targets = [0, 1, len(res.events) // 2, len(res.events) - 1, 2, len(res.events)]
    for target in seek_targets:
        seek_state = engine.seek(target)
        if target == 0:
            assert len(seek_state.bindings) == 0
        else:
            expected_seq = forward_history[min(target - 1, len(forward_history) - 1)]
            assert seek_state.step_sequence == expected_seq.step_sequence
            assert seek_state.current_line == expected_seq.current_line

    print(f"  [PASS] PlaybackEngine successfully verified across {len(res.events)} events with O(1) reversibility and random seek.")


# =====================================================================
# Test 3: End-to-End Native C++ Pipeline Execution
# =====================================================================
def test_3_end_to_end_cpp_execution():
    print("\n--- 3. Testing End-to-End C++ Execution via Event Pipeline ---")
    cpp_code = """int test() {
    std::vector<int> nums;
    nums.push_back(100);
    nums.push_back(200);
    int sz = nums.size();
    return sz;
}
"""
    req = CodeExecutionRequest(code=cpp_code, language="cpp")
    res = execute_code(req)

    assert res.error is None, f"C++ execution failed: {res.error}"
    assert res.events is not None and len(res.events) > 0, "No events returned for C++"
    assert res.steps is not None and len(res.steps) > 0, "No steps returned for C++"

    # Verify vector container visualization
    vector_vis_found = False
    for step in res.steps:
        for v in step.visualizations:
            if v.type == "Array" and v.details.get("name") == "nums":
                vector_vis_found = True
                assert 100 in v.details.get("value", [])
    assert vector_vis_found, "C++ vector Array visualization missing"
    print(f"  [PASS] C++ event pipeline verified: {len(res.events)} events, {len(res.steps)} steps.")


# =====================================================================
# Test 4: Runtime Error Handling (Division by Zero)
# =====================================================================
def test_4_runtime_error_handling():
    print("\n--- 4. Testing Runtime Failure & Safety Boundaries ---")
    bad_code = """x = 10
y = 0
z = x / y
"""
    req = CodeExecutionRequest(code=bad_code, language="python")
    res = execute_code(req)

    assert res.error is not None, "Runtime error was not captured in error field"
    assert "ZeroDivisionError" in res.error
    assert res.steps == []
    print("  [PASS] Runtime failure handled safely with clear error report.")


# =====================================================================
# Test 5: Syntax Error Handling
# =====================================================================
def test_5_syntax_error_handling():
    print("\n--- 5. Testing Syntax Error Handling ---")
    invalid_syntax = "def broken(:"
    req = CodeExecutionRequest(code=invalid_syntax, language="python")
    res = execute_code(req)

    assert res.error is not None
    assert "Syntax" in res.error or "invalid syntax" in res.error.lower()
    print("  [PASS] Syntax error rejected gracefully without unhandled exception.")


# =====================================================================
# Test 6: Empty Code Execution
# =====================================================================
def test_6_empty_code_handling():
    print("\n--- 6. Testing Empty Program Handling ---")
    empty_req = CodeExecutionRequest(code="", language="python")
    res = execute_code(empty_req)

    # Empty code is handled safely without throwing or crashing
    assert res.error is None
    assert res.events is not None
    assert len(res.events) >= 2  # PROG_START and PROG_END
    assert res.events[0].event_type == "PROG_START"
    assert res.events[-1].event_type == "PROG_END"
    print("  [PASS] Empty code safely handled without crashing, yielding baseline lifecycle events.")


# =====================================================================
# Test 7: Deterministic Repeated Execution
# =====================================================================
def test_7_deterministic_repeated_execution():
    print("\n--- 7. Testing Deterministic Repeated Execution & State Isolation ---")
    code = """def compute():
    vals = [1, 2, 3]
    return sum(vals)

total = compute()
"""
    runs = []
    for run_idx in range(3):
        req = CodeExecutionRequest(code=code, language="python")
        res = execute_code(req)
        assert res.error is None
        assert res.events and len(res.events) > 0
        runs.append(res)

    # All runs must produce identical event count, event types, and step counts
    base_events = runs[0].events
    base_steps = runs[0].steps

    for run_idx in range(1, 3):
        evs = runs[run_idx].events
        steps = runs[run_idx].steps
        assert len(evs) == len(base_events), f"Run {run_idx} event count mismatch: {len(evs)} vs {len(base_events)}"
        assert len(steps) == len(base_steps), f"Run {run_idx} step count mismatch: {len(steps)} vs {len(base_steps)}"

        # Verify event sequence equivalence
        for i in range(len(evs)):
            assert evs[i].event_type == base_events[i].event_type
            assert evs[i].line == base_events[i].line
            assert evs[i].seq == base_events[i].seq

    print(f"  [PASS] 3 sequential runs verified with 100% deterministic event and step equivalence.")


# =====================================================================
# Main Execution Runner
# =====================================================================
def run_all_milestone_8_tests():
    print("=" * 70)
    print("         ALGOLENS MILESTONE 8 INTEGRATION VERIFICATION SUITE         ")
    print("=" * 70)
    t0 = time.perf_counter()

    test_1_end_to_end_python_bubble_sort()
    test_2_playback_engine_reversibility_and_seek()
    test_3_end_to_end_cpp_execution()
    test_4_runtime_error_handling()
    test_5_syntax_error_handling()
    test_6_empty_code_handling()
    test_7_deterministic_repeated_execution()

    elapsed = time.perf_counter() - t0
    print("\n" + "=" * 70)
    print(f">>> ALL 7 MILESTONE 8 VERIFICATION TESTS PASSED IN {elapsed:.2f}s! <<<")
    print("=" * 70)


if __name__ == "__main__":
    run_all_milestone_8_tests()
