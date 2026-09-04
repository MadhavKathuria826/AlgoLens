"""
AlgoLens Milestone 3 Native Execution Test Suite
Validates:
1. Native C++ compilation & source instrumentation pipeline across 9 Golden Corpus categories:
   - G01: Basic scalars
   - G02: Assignments
   - G03: Arithmetic
   - G06: Nested scopes
   - G07: Function calls
   - G08: Recursion (Fibonacci)
   - G09: Basic arrays
   - G21: Conditional branches
   - G22: Loops
2. Semantic comparison of native execution vs legacy Python AST interpreter
3. Integration with UniversalStateReducer and EventToStepAdapter
4. Graceful failure modes: syntax error, unsupported constructs, execution timeout
"""

import os
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from golden_corpus import GOLDEN_TEST_CASES
from cpp_interpreter import CPPInterpreter
from native_runner import NativeCompilationPipeline
from state_reducer import UniversalRuntimeState, UniversalStateReducer
from event_to_step_adapter import EventToStepAdapter


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


def test_native_golden_subset():
    print("\n--- 1. Testing Native C++ Execution on Milestone 3 Golden Corpus Subset ---")
    pipeline = NativeCompilationPipeline()
    interp = CPPInterpreter(max_recursion_depth=100)

    print(f"  Detected Native Compiler: {pipeline.compiler_name} ({pipeline.compiler_version[:60]}...)")

    for key in NATIVE_SUBSET_KEYS:
        spec = GOLDEN_TEST_CASES[key]
        code = spec["code"]
        entry_func = spec["entry_func"]
        args = spec["args"]

        # 1. Reference legacy execution
        legacy_steps, legacy_ret = interp.interpret(code, entry_func, args)

        # 2. Native compilation & execution
        native_res = pipeline.compile_and_run(code, entry_func, args)
        assert native_res.success, f"[{key}] Native run failed: {native_res.error_message} {native_res.compiler_diagnostics}"
        assert len(native_res.events) > 0, f"[{key}] No events emitted"

        # 3. Reduce native events into UniversalRuntimeState
        state = UniversalRuntimeState()
        for ev in native_res.events:
            state = UniversalStateReducer.reduce(state, ev)

        # 4. Extract final native return value
        native_ret = None
        for ev in reversed(native_res.events):
            if ev.event_type == "FRAME_POP" and "return_value" in ev.payload:
                rv = ev.payload["return_value"]
                native_ret = rv.get("value") if isinstance(rv, dict) else rv
                break

        # 5. Semantic equivalence check
        assert native_ret == legacy_ret, f"[{key}] Return value mismatch: Native {native_ret} != Legacy {legacy_ret}"

        # 6. Adapt to legacy step model
        adapter = EventToStepAdapter()
        adapter.state = state
        step = adapter.state_to_step()
        assert step is not None

        print(f"  [PASS] {key}: Native={native_ret} | Legacy={legacy_ret} | Events={len(native_res.events)} | Compile={native_res.compile_time_ms:.1f}ms | Exec={native_res.execution_time_ms:.1f}ms")

    print(f"  All {len(NATIVE_SUBSET_KEYS)} native golden corpus tests passed semantic validation with 100% fidelity.")


def test_failure_modes():
    print("\n--- 2. Testing Graceful Failure Handling & Boundaries ---")
    pipeline = NativeCompilationPipeline()

    # Case A: Syntax Error
    bad_code = "int test() { int x = ; return 0; }"
    res_syntax = pipeline.compile_and_run(bad_code, "test")
    assert not res_syntax.success
    assert "Syntax Error" in (res_syntax.error_message or "")
    print("  [PASS] Syntax error gracefully reported without crash.")

    # Case B: Unsupported Construct (dynamic allocation new/delete)
    unsupported_code = "struct Node { int v; }; int test() { Node* n = new Node(); return 0; }"
    res_unsupported = pipeline.compile_and_run(unsupported_code, "test")
    assert not res_unsupported.success
    assert "Unsupported C++ construct" in (res_unsupported.error_message or "")
    print("  [PASS] Unsupported construct (new/delete) explicitly rejected with helpful diagnostic.")

    # Case C: Process Timeout (Infinite Loop)
    timeout_code = "int test() { int i = 0; while(1) { i = i + 1; } return i; }"
    res_timeout = pipeline.compile_and_run(timeout_code, "test", timeout_sec=1.0)
    assert not res_timeout.success
    assert "timed out" in (res_timeout.error_message or "")
    print("  [PASS] Process execution timeout caught cleanly.")


if __name__ == "__main__":
    test_native_golden_subset()
    test_failure_modes()
    print("\n=== ALL MILESTONE 3 NATIVE TESTS PASSED SUCCESSFULLY ===")
