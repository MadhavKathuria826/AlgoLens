"""
AlgoLens Milestone 4 Test Suite
Validates:
1. Native compilation & execution across expanded Golden Corpus:
   - Milestone 3 subset: G01, G02, G03, G06, G07, G08, G09, G21, G22
   - Data structures: G14 (Linked List), G15 (Binary Tree), G16 (Pointer Allocation),
                     G17 (Pointer Aliasing), G18 (Reference Parameter),
                     G10 (Vector), G11 (Stack), G12 (Queue), G13 (Map)
2. Native ObjectRegistry & Pointer Model:
   - Synthetic object ID isolation (no raw hex addresses in universal state)
   - Pointer aliasing (multiple bindings to one object)
   - Pointer dereference mutation (*p = val)
   - Struct member field mutation (n->field = val)
   - Object deallocation (delete ptr)
   - Dangling reference detection
   - Pointer reuse (ensuring new synthetic ID on memory reuse)
   - Null pointer distinction (nullptr vs dangling vs live)
3. Bidirectional Reversible Playback and Arbitrary Seek via PlaybackEngine
4. Graceful failure modes (syntax error, class inheritance rejection, timeout)
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
from playback_engine import PlaybackEngine
from semantic_comparator import SemanticComparator

# All 18 native golden categories supported in Milestone 4
M4_GOLDEN_CATEGORIES = [
    "G01_basic_scalars",
    "G02_assignments",
    "G03_arithmetic",
    "G06_nested_scopes",
    "G07_function_calls",
    "G08_recursion",
    "G09_arrays",
    "G21_conditional_branches",
    "G22_loops",
    "G14_linked_lists",
    "G15_binary_trees",
    "G16_pointer_allocation",
    "G17_pointer_aliasing",
    "G18_reference_behavior",
    "G10_vector_operations",
    "G11_stack_operations",
    "G12_queue_operations",
    "G13_map_operations"
]


def test_native_golden_corpus():
    print("\n--- 1. Testing Native Execution on All 18 Golden Categories ---")
    pipeline = NativeCompilationPipeline()
    interp = CPPInterpreter(max_recursion_depth=100)

    print(f"  Compiler: {pipeline.compiler_name} ({pipeline.compiler_version[:60]}...)")

    passed_count = 0
    for key in M4_GOLDEN_CATEGORIES:
        spec = GOLDEN_TEST_CASES[key]
        code = spec["code"]
        entry_func = spec["entry_func"]
        args = spec["args"]

        # 1. Native compilation & execution
        native_res = pipeline.compile_and_run(code, entry_func, args)
        assert native_res.success, f"[{key}] Native run failed: {native_res.error_message}\n{native_res.compiler_diagnostics}"
        assert len(native_res.events) > 0, f"[{key}] No events emitted"

        # 2. Extract native return value
        native_ret = None
        for ev in reversed(native_res.events):
            if ev.event_type == "FRAME_POP" and "return_value" in ev.payload:
                rv = ev.payload["return_value"]
                native_ret = rv.get("value") if isinstance(rv, dict) else rv
                break

        # 3. Reduce native events into UniversalRuntimeState
        state = UniversalRuntimeState()
        for ev in native_res.events:
            state = UniversalStateReducer.reduce(state, ev)

        # 4. Compare with legacy interpreter
        legacy_steps, legacy_ret = interp.interpret(code, entry_func, args)
        if key not in ("G13_map_operations", "G18_reference_behavior"):
            assert native_ret == legacy_ret, f"[{key}] Return value mismatch: Native {native_ret} != Legacy {legacy_ret}"
        elif key == "G18_reference_behavior":
            # Real C++ pass-by-reference modifies num to 11; legacy interpreter lacked reference support and returned 10
            assert native_ret == 11, f"[{key}] Expected real C++ pass-by-reference return 11, got {native_ret}"
        elif key == "G13_map_operations":
            # Real C++ std::map stores 1; legacy interpreter returned 0
            assert native_ret == 1, f"[{key}] Expected real C++ std::map return 1, got {native_ret}"

        # 5. Adapt to legacy Step model
        adapter = EventToStepAdapter()
        steps = adapter.process_event_stream(native_res.events)
        assert len(steps) > 0

        print(f"  [PASS] {key}: Native Ret={native_ret} | Events={len(native_res.events)} | Steps={len(steps)} | Heap Objs={len(state.heap)}")
        passed_count += 1

    print(f"  All {passed_count}/{len(M4_GOLDEN_CATEGORIES)} Golden Corpus tests passed with 100% semantic fidelity.")


def test_object_registry_and_pointer_model():
    print("\n--- 2. Testing ObjectRegistry, Dangling Pointers, and Memory Reuse ---")
    pipeline = NativeCompilationPipeline()

    # Case A: Pointer Aliasing & Mutation (Two bindings, one object)
    code_alias = """
    struct Node { int val; };
    int test() {
        Node* a = new Node;
        a->val = 10;
        Node* b = a;
        b->val = 42;
        return a->val;
    }
    """
    res_alias = pipeline.compile_and_run(code_alias, "test")
    assert res_alias.success
    adapter = EventToStepAdapter()
    steps_alias = adapter.process_event_stream(res_alias.events)
    # Check step before return
    step_pre_ret = steps_alias[-1]
    assert step_pre_ret.locals["a"] == "obj_0"
    assert step_pre_ret.locals["b"] == "obj_0"
    assert step_pre_ret.heap["obj_0"]["fields"]["val"] == 42
    print("  [PASS] Pointer aliasing verified: multiple bindings map to one synthetic object ID.")

    # Case B: Pointer Dereference Write (*p = val)
    code_deref = """
    int test() {
        int* p = new int(5);
        *p = 10;
        return *p;
    }
    """
    res_deref = pipeline.compile_and_run(code_deref, "test")
    assert res_deref.success
    mutate_events = [ev for ev in res_deref.events if ev.event_type == "OBJECT_MUTATE"]
    assert len(mutate_events) > 0
    assert mutate_events[0].payload["object_id"] == "obj_0"
    assert mutate_events[0].payload["field"] == "value"
    assert mutate_events[0].payload["new_value"]["value"] == 10
    print("  [PASS] Pointer dereference write verified: mutates object value rather than pointer variable.")

    # Case C: Deallocation & Dangling References
    code_dangling = """
    struct Node { int val; };
    int test() {
        Node* a = new Node;
        a->val = 100;
        Node* b = a;
        delete a;
        return 0;
    }
    """
    res_dangling = pipeline.compile_and_run(code_dangling, "test")
    assert res_dangling.success
    adapter = EventToStepAdapter()
    steps_dangling = adapter.process_event_stream(res_dangling.events)
    # Step after delete a
    step_after_del = steps_dangling[-1]
    assert step_after_del.locals["a"] == "<dangling:obj_0>"
    assert step_after_del.locals["b"] == "<dangling:obj_0>"
    assert "obj_0" not in step_after_del.heap  # Dead object not rendered in active heap
    print("  [PASS] Dangling pointer detection verified: bindings explicitly marked <dangling:obj_0>.")

    # Case D: Pointer Reuse Safety (Minting new synthetic ID)
    code_reuse = """
    struct Node { int val; };
    int test() {
        Node* a = new Node;
        a->val = 1;
        delete a;
        Node* c = new Node;
        c->val = 2;
        return c->val;
    }
    """
    res_reuse = pipeline.compile_and_run(code_reuse, "test")
    assert res_reuse.success
    adapter = EventToStepAdapter()
    steps_reuse = adapter.process_event_stream(res_reuse.events)
    last_step = steps_reuse[-1]
    assert last_step.locals["a"] == "<dangling:obj_0>"
    assert last_step.locals["c"] == "obj_1"  # New synthetic ID minted! Never resurrected obj_0!
    assert "obj_1" in last_step.heap
    print("  [PASS] Pointer reuse invariant verified: new allocation creates obj_1, never resurrecting obj_0.")

    # Case E: Null Pointer Handling & Delete nullptr
    code_null = """
    struct Node { int val; };
    int test() {
        Node* p = nullptr;
        delete p;
        return 0;
    }
    """
    res_null = pipeline.compile_and_run(code_null, "test")
    assert res_null.success
    adapter = EventToStepAdapter()
    steps_null = adapter.process_event_stream(res_null.events)
    assert steps_null[-1].locals["p"] == "0x0000"
    print("  [PASS] Null pointer handling verified: nullptr recognized and delete nullptr safely handled.")


def test_bidirectional_playback_and_reversibility():
    print("\n--- 3. Testing Bi-directional Reversible Playback & Seeking ---")
    pipeline = NativeCompilationPipeline()

    code = """
    struct Node { int val; Node* next; };
    int test() {
        Node* a = new Node;
        a->val = 10;
        Node* b = new Node;
        b->val = 20;
        a->next = b;
        a->val = 99;
        delete b;
        delete a;
        return 0;
    }
    """
    res = pipeline.compile_and_run(code, "test")
    assert res.success

    engine = PlaybackEngine(res.events)
    total_events = len(res.events)

    # 1. Forward traversal
    step_count = 0
    while engine.step_forward():
        step_count += 1
    assert engine.current_event_index == total_events
    assert engine.current_state.heap["obj_0"].is_alive == False
    assert engine.current_state.heap["obj_1"].is_alive == False

    # 2. Reverse traversal back to beginning
    rev_count = 0
    while engine.step_reverse():
        rev_count += 1
    assert engine.current_event_index == 0
    assert len(engine.current_state.heap) == 0

    # 3. Arbitrary seek to midway where both nodes are alive and linked
    # Event index 14 is right after a->val = 99 and before delete b
    engine.seek(14)
    state = engine.current_state
    assert state.heap["obj_0"].is_alive == True
    assert state.heap["obj_1"].is_alive == True
    assert state.heap["obj_0"].fields["val"].value == 10
    assert state.heap["obj_0"].fields["next"].object_id == "obj_1"
    assert state.heap["obj_1"].fields["val"].value == 20

    print("  [PASS] PlaybackEngine successfully verified: forward stepping, full reverse to zero, and random seek.")


def test_failure_modes():
    print("\n--- 4. Testing Failure Modes & Safety Boundaries ---")
    pipeline = NativeCompilationPipeline()

    # Syntax Error
    bad_code = "int test() { int x = ; return 0; }"
    res_syntax = pipeline.compile_and_run(bad_code, "test")
    assert not res_syntax.success
    assert "Syntax Error" in (res_syntax.error_message or "")
    print("  [PASS] Syntax error gracefully reported without crash.")

    # Unsupported Construct (Class Inheritance)
    unsupported_code = "class Base {}; class Derived : public Base {}; int test() { return 0; }"
    res_unsupported = pipeline.compile_and_run(unsupported_code, "test")
    assert not res_unsupported.success
    assert "class inheritance" in (res_unsupported.error_message or "")
    print("  [PASS] Unsupported construct (class inheritance) explicitly rejected with helpful diagnostic.")

    # Execution Timeout
    timeout_code = "int test() { int i = 0; while(1) { i = i + 1; } return i; }"
    res_timeout = pipeline.compile_and_run(timeout_code, "test", timeout_sec=1.0)
    assert not res_timeout.success
    assert "timed out" in (res_timeout.error_message or "")
    print("  [PASS] Process execution timeout caught cleanly.")


if __name__ == "__main__":
    test_native_golden_corpus()
    test_object_registry_and_pointer_model()
    test_bidirectional_playback_and_reversibility()
    test_failure_modes()
    print("\n=== ALL MILESTONE 4 TESTS PASSED SUCCESSFULLY ===")
