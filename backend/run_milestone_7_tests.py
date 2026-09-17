"""
AlgoLens Milestone 7 Test Suite
Validates the Universal Runtime Contract and Second-Language (Python) Producer:
1. Python scalar execution
2. Python control flow
3. Python function frames
4. Python mutable objects
5. Python aliasing
6. Python nested containers
7. Python dictionary/set operations
8. Python stdout/event separation
9. Python timeout
10. max_events enforcement
11. fresh runtime IDs across repeated runs
12. forward/reverse playback
13. arbitrary seeking
14. Python/C++ universal semantic compatibility (10 semantic patterns)
15. Runtime Contract polymorphism
"""

import os
import sys
import time
from typing import Dict, Any, List

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from runtime_contract import LanguageRuntimeProducer, ExecutionResult
from native_runner import NativeCompilationPipeline, CppRuntimeProducer
from python_producer import PythonRuntimeProducer
from event_models import AlgoLensEvent, PrimitiveValue, ObjectRef, NullRef, Uninitialized
from state_reducer import UniversalRuntimeState, UniversalStateReducer
from event_to_step_adapter import EventToStepAdapter
from playback_engine import PlaybackEngine


# =====================================================================
# Test 1: Python Scalar Execution
# =====================================================================
def test_1_python_scalar_execution():
    print("\n--- 1. Testing Python Scalar Execution ---")
    producer = PythonRuntimeProducer()
    code = """
a = 42
b = 3.14
c = True
d = "algolens"
e = None
"""
    res = producer.execute_program(code)
    assert res.success, f"Execution failed: {res.error_message}"
    assert len(res.events) > 0

    state = UniversalRuntimeState()
    for ev in res.events:
        state = UniversalStateReducer.reduce(state, ev)

    vis = state.get_visible_bindings()
    assert "a" in vis and isinstance(vis["a"].value, PrimitiveValue) and vis["a"].value.value == 42
    assert "b" in vis and isinstance(vis["b"].value, PrimitiveValue) and vis["b"].value.value == 3.14
    assert "c" in vis and isinstance(vis["c"].value, PrimitiveValue) and vis["c"].value.value is True
    assert "d" in vis and isinstance(vis["d"].value, PrimitiveValue) and vis["d"].value.value == "algolens"
    assert "e" in vis and isinstance(vis["e"].value, NullRef)

    adapter = EventToStepAdapter()
    steps = adapter.process_event_stream(res.events)
    assert len(steps) >= 5
    final_step = steps[-1]
    assert final_step.locals["a"] == 42
    assert final_step.locals["b"] == 3.14
    assert final_step.locals["c"] is True
    assert final_step.locals["d"] == "algolens"
    assert final_step.locals["e"] == "0x0000"
    print("  [PASS] Python scalar variables (int, float, bool, str, None) mapped and reduced cleanly.")


# =====================================================================
# Test 2: Python Control Flow
# =====================================================================
def test_2_python_control_flow():
    print("\n--- 2. Testing Python Control Flow (Branches, Loops, Continue, Break) ---")
    producer = PythonRuntimeProducer()
    code = """
x = 10
if x > 5:
    y = 1
else:
    y = 2

acc = 0
for i in range(5):
    if i == 2:
        continue
    if i == 4:
        break
    acc += i
"""
    res = producer.execute_program(code)
    assert res.success, f"Execution failed: {res.error_message}"

    # Verify that 'else: y = 2' was NEVER executed
    step_lines = [ev.payload.get("line") for ev in res.events if ev.event_type == "STEP_LINE"]
    # Line 6 is 'y = 2' (1-indexed based on code string)
    code_lines = code.splitlines()
    else_body_lineno = None
    for idx, l in enumerate(code_lines, 1):
        if "y = 2" in l:
            else_body_lineno = idx
            break
    assert else_body_lineno not in step_lines, f"Unexecuted else branch line {else_body_lineno} fired in STEP_LINE!"

    state = UniversalRuntimeState()
    for ev in res.events:
        state = UniversalStateReducer.reduce(state, ev)

    vis = state.get_visible_bindings()
    assert vis["y"].value.value == 1
    # acc should be: i=0 (acc=0), i=1 (acc=1), i=2 (skipped), i=3 (acc=1+3=4), i=4 (break)
    assert vis["acc"].value.value == 4
    print("  [PASS] Real control flow tracing verified: skipped branches omitted, continue/break honored.")


# =====================================================================
# Test 3: Python Function Frames
# =====================================================================
def test_3_python_function_frames():
    print("\n--- 3. Testing Python Function Frames & Parameter Bindings ---")
    producer = PythonRuntimeProducer()
    code = """
def mul(x, y):
    z = x * y
    return z

ans = mul(6, 7)
"""
    res = producer.execute_program(code)
    assert res.success, f"Execution failed: {res.error_message}"

    # Check frame push/pop events
    pushes = [ev for ev in res.events if ev.event_type == "FRAME_PUSH"]
    pops = [ev for ev in res.events if ev.event_type == "FRAME_POP"]
    assert len(pushes) == 1
    assert len(pops) == 1

    push = pushes[0]
    assert push.payload["func_name"] == "mul"
    assert push.payload["args"]["x"]["value"] == 6
    assert push.payload["args"]["y"]["value"] == 7

    pop = pops[0]
    assert pop.payload["return_value"]["value"] == 42

    state = UniversalRuntimeState()
    for ev in res.events:
        state = UniversalStateReducer.reduce(state, ev)

    vis = state.get_visible_bindings()
    assert "ans" in vis and vis["ans"].value.value == 42
    # Local variable 'z' from function mul must not pollute module scope
    assert "z" not in vis
    print("  [PASS] Function call frames, parameter binding, return value, and scope isolation verified.")


# =====================================================================
# Test 4: Python Mutable Objects
# =====================================================================
def test_4_python_mutable_objects():
    print("\n--- 4. Testing Python Mutable Objects (List Indexing, Append, Pop) ---")
    producer = PythonRuntimeProducer()
    code = """
nums = [10, 20]
nums.append(30)
nums[0] = 99
last = nums.pop()
"""
    res = producer.execute_program(code)
    assert res.success, f"Execution failed: {res.error_message}"

    allocs = [ev for ev in res.events if ev.event_type == "OBJECT_ALLOCATE"]
    mutates = [ev for ev in res.events if ev.event_type == "OBJECT_MUTATE"]
    assert len(allocs) >= 1
    assert len(mutates) >= 3

    state = UniversalRuntimeState()
    for ev in res.events:
        state = UniversalStateReducer.reduce(state, ev)

    obj_id = state.bindings["binding_0"].value.object_id
    assert obj_id in state.heap
    fields = state.heap[obj_id].fields

    assert fields["0"].value == 99
    assert fields["1"].value == 20
    assert fields["length"].value == 2
    # Index 2 was popped, must not be present
    assert "2" not in fields
    print("  [PASS] List operations (append, index write, pop) tracked via semantic OBJECT_MUTATE.")


# =====================================================================
# Test 5: Python Aliasing
# =====================================================================
def test_5_python_aliasing():
    print("\n--- 5. Testing Python Aliasing & Object Re-assignment Invariants ---")
    producer = PythonRuntimeProducer()
    code = """
a = [1]
b = a
b.append(2)
a = [2]
"""
    res = producer.execute_program(code)
    assert res.success, f"Execution failed: {res.error_message}"

    state = UniversalRuntimeState()
    for ev in res.events:
        state = UniversalStateReducer.reduce(state, ev)

    # a should point to new object (obj_1), b should point to original object (obj_0)
    a_obj = state.bindings["binding_0"].value.object_id
    b_obj = state.bindings["binding_1"].value.object_id
    assert a_obj != b_obj, f"a and b must not point to the same object after re-assignment: {a_obj} == {b_obj}"

    # Original object (b_obj) should have both 1 and 2
    assert state.heap[b_obj].fields["0"].value == 1
    assert state.heap[b_obj].fields["1"].value == 2
    assert state.heap[b_obj].fields["length"].value == 2

    # New object (a_obj) should have [2]
    assert state.heap[a_obj].fields["0"].value == 2
    assert state.heap[a_obj].fields["length"].value == 1
    print("  [PASS] Object aliasing and re-assignment identity verified: b -> obj_0, a -> obj_1.")


# =====================================================================
# Test 6: Python Nested Containers
# =====================================================================
def test_6_python_nested_containers():
    print("\n--- 6. Testing Python Nested Containers (Grid / List of Lists) ---")
    producer = PythonRuntimeProducer()
    code = """
grid = [[1, 2], [3, 4]]
grid[0].append(99)
grid[1][0] = 77
"""
    res = producer.execute_program(code)
    assert res.success, f"Execution failed: {res.error_message}"

    state = UniversalRuntimeState()
    for ev in res.events:
        state = UniversalStateReducer.reduce(state, ev)

    grid_obj_id = state.bindings["binding_0"].value.object_id
    grid_fields = state.heap[grid_obj_id].fields

    inner_0_id = grid_fields["0"].object_id
    inner_1_id = grid_fields["1"].object_id

    assert inner_0_id in state.heap
    assert inner_1_id in state.heap

    # inner_0 has [1, 2, 99]
    assert state.heap[inner_0_id].fields["0"].value == 1
    assert state.heap[inner_0_id].fields["1"].value == 2
    assert state.heap[inner_0_id].fields["2"].value == 99
    assert state.heap[inner_0_id].fields["length"].value == 3

    # inner_1 has [77, 4]
    assert state.heap[inner_1_id].fields["0"].value == 77
    assert state.heap[inner_1_id].fields["1"].value == 4
    print("  [PASS] Nested containers (graph of object refs) and hierarchical mutation verified.")


# =====================================================================
# Test 7: Python Dictionary and Set Operations
# =====================================================================
def test_7_python_dict_and_set_operations():
    print("\n--- 7. Testing Python Dictionaries and Sets ---")
    producer = PythonRuntimeProducer()
    code = """
d = {"x": 10}
d["y"] = 20
d["x"] = 99
del d["y"]

s = {1, 2}
s.add(3)
s.remove(1)
"""
    res = producer.execute_program(code)
    assert res.success, f"Execution failed: {res.error_message}"

    state = UniversalRuntimeState()
    for ev in res.events:
        state = UniversalStateReducer.reduce(state, ev)

    d_obj_id = state.bindings["binding_0"].value.object_id
    s_obj_id = state.bindings["binding_1"].value.object_id

    d_fields = state.heap[d_obj_id].fields
    assert d_fields["x"].value == 99
    assert "y" not in d_fields
    assert d_fields["size"].value == 1

    s_fields = state.heap[s_obj_id].fields
    assert "1" not in s_fields
    assert s_fields["2"].value == 2
    assert s_fields["3"].value == 3
    assert s_fields["size"].value == 2
    print("  [PASS] Dictionary and set operations (insert, update, delete, add, remove) verified.")


# =====================================================================
# Test 8: Python Stdout and Event Separation
# =====================================================================
def test_8_python_stdout_event_separation():
    print("\n--- 8. Testing User Stdout and Event Stream Separation ---")
    producer = PythonRuntimeProducer()
    code = """
print("HELLO FROM USER CODE")
x = 500
print("OUTPUT LINE 2")
"""
    res = producer.execute_program(code)
    assert res.success, f"Execution failed: {res.error_message}"

    assert "HELLO FROM USER CODE" in res.user_stdout
    assert "OUTPUT LINE 2" in res.user_stdout

    # Verify no stdout lines are masquerading as event types or values
    for ev in res.events:
        assert ev.event_type in (
            "PROG_START", "PROG_END", "STEP_LINE", "FRAME_PUSH", "FRAME_POP",
            "SCOPE_ENTER", "SCOPE_EXIT", "VAR_DECLARE", "VAR_WRITE", "VAR_DELETE",
            "OBJECT_ALLOCATE", "OBJECT_MUTATE", "OBJECT_DEALLOCATE", "OBJECT_FREE",
            "CONTAINER_OP", "TRACE_TRUNCATED"
        )
        if ev.event_type == "VAR_DECLARE":
            assert "HELLO FROM USER CODE" not in str(ev.payload.get("value"))

    state = UniversalRuntimeState()
    for ev in res.events:
        state = UniversalStateReducer.reduce(state, ev)
    assert state.get_visible_bindings()["x"].value.value == 500
    print("  [PASS] Clean demultiplexing between user stdout and universal AlgoLens events verified.")


# =====================================================================
# Test 9: Python Timeout Enforcement
# =====================================================================
def test_9_python_timeout_enforcement():
    print("\n--- 9. Testing Timeout Enforcement on Runaway Loop ---")
    producer = PythonRuntimeProducer()
    code = """
while True:
    pass
"""
    t0 = time.perf_counter()
    res = producer.execute_program(code, timeout_sec=0.1, max_events=10000000)
    elapsed = time.perf_counter() - t0

    assert not res.success
    assert res.exit_code == -1
    assert "Execution timed out" in str(res.error_message)
    assert elapsed < 1.0, f"Timeout took too long to terminate: {elapsed:.2f}s"
    print(f"  [PASS] Runaway loop timed out cleanly in {elapsed*1000:.1f}ms without crashing.")


# =====================================================================
# Test 10: max_events Enforcement
# =====================================================================
def test_10_max_events_enforcement():
    print("\n--- 10. Testing max_events Hard Ceiling Enforcement ---")
    producer = PythonRuntimeProducer()
    code = """
i = 0
while True:
    i += 1
"""
    res = producer.execute_program(code, max_events=150)
    assert len(res.events) == 150
    assert res.events[-1].event_type == "TRACE_TRUNCATED"
    assert res.events[-1].payload["max_limit"] == 150
    assert "Trace truncated" in res.diagnostics
    print("  [PASS] max_events ceiling strictly enforced with TRACE_TRUNCATED event.")


# =====================================================================
# Test 11: Fresh Runtime IDs Across Repeated Runs
# =====================================================================
def test_11_fresh_runtime_ids_across_repeated_runs():
    print("\n--- 11. Testing Fresh Runtime IDs Across Repeated Runs ---")
    producer = PythonRuntimeProducer()
    code = """
lst = [1, 2]
"""
    res1 = producer.execute_program(code)
    res2 = producer.execute_program(code)
    res3 = producer.execute_program(code)

    for r_idx, r in enumerate([res1, res2, res3], 1):
        assert r.success
        assert r.events[0].seq == 0
        assert r.events[0].frame_id == "frame_0"
        alloc_events = [ev for ev in r.events if ev.event_type == "OBJECT_ALLOCATE"]
        assert len(alloc_events) == 1
        assert alloc_events[0].payload["object_id"] == "obj_0", f"Run {r_idx} leaked object ID: {alloc_events[0].payload['object_id']}"

    print("  [PASS] Fresh runtime identity isolation confirmed across 3 sequential executions.")


# =====================================================================
# Test 12: Forward / Reverse Playback
# =====================================================================
def test_12_forward_reverse_playback():
    print("\n--- 12. Testing Forward and Backward Reversible Playback ---")
    producer = PythonRuntimeProducer()
    code = """
x = 10
x = 20
items = [1]
items.append(2)
"""
    res = producer.execute_program(code)
    assert res.success

    engine = PlaybackEngine(res.events)
    engine.build_checkpoints()

    # Step forward to end
    while engine.step_forward():
        pass

    assert engine.current_state.bindings["binding_0"].value.value == 20
    obj_id = engine.current_state.bindings["binding_1"].value.object_id
    assert engine.current_state.heap[obj_id].fields["length"].value == 2

    # Step reverse back to zero
    while engine.step_reverse():
        pass

    assert len(engine.current_state.bindings) == 0
    assert len(engine.current_state.heap) == 0
    assert engine.current_event_index == 0
    print("  [PASS] Full forward traversal and reversible back-propagation to sequence 0 verified.")


# =====================================================================
# Test 13: Arbitrary Seeking
# =====================================================================
def test_13_arbitrary_seeking():
    print("\n--- 13. Testing Arbitrary Seek Equivalence vs Sequential Execution ---")
    producer = PythonRuntimeProducer()
    code = """
sum = 0
for i in range(1, 6):
    sum += i
"""
    res = producer.execute_program(code)
    assert res.success

    # Collect ground-truth states for each event index
    sequential_states = []
    st = UniversalRuntimeState()
    for ev in res.events:
        st = UniversalStateReducer.reduce(st.model_copy(deep=True), ev)
        sequential_states.append(st.model_copy(deep=True))

    engine = PlaybackEngine(res.events)
    engine.build_checkpoints()

    test_targets = [0, 1, 10, len(res.events) - 1, 5, 12, 3, len(res.events)]
    for target in test_targets:
        sought_state = engine.seek(target)
        if target == 0:
            assert len(sought_state.bindings) == 0
        else:
            expected = sequential_states[target - 1]
            assert sought_state.step_sequence == expected.step_sequence
            assert sought_state.current_line == expected.current_line
            # Compare binding values
            for b_id, b in expected.bindings.items():
                assert b_id in sought_state.bindings
                assert sought_state.bindings[b_id].value == b.value

    print(f"  [PASS] Arbitrary seek across indices {test_targets} verified with 100% state equivalence.")


# =====================================================================
# Test 14: Python / C++ Universal Semantic Compatibility (10 Patterns)
# =====================================================================
def test_14_cross_language_semantic_corpus():
    print("\n--- 14. Testing Cross-Language Semantic Compatibility (10 Patterns) ---")
    py_prod = PythonRuntimeProducer()
    cpp_prod = NativeCompilationPipeline()

    semantic_cases = [
        # 1. Scalar declaration/write
        {
            "name": "1. Scalar declaration/write",
            "py": "def test():\n    x = 10\n    x = 20\n    return x\n",
            "cpp": "int test() { int x = 10; x = 20; return x; }",
            "entry": "test",
            "expected_ret": 20
        },
        # 2. Arithmetic
        {
            "name": "2. Arithmetic",
            "py": "def test():\n    a = 7\n    b = 3\n    c = (a * b) + (a // b)\n    return c\n",
            "cpp": "int test() { int a = 7; int b = 3; int c = (a * b) + (a / b); return c; }",
            "entry": "test",
            "expected_ret": 23
        },
        # 3. Conditional branch
        {
            "name": "3. Conditional branch",
            "py": "def test():\n    x = 15\n    y = 0\n    if x > 10:\n        y = 1\n    else:\n        y = 2\n    return y\n",
            "cpp": "int test() { int x = 15; int y = 0; if (x > 10) { y = 1; } else { y = 2; } return y; }",
            "entry": "test",
            "expected_ret": 1
        },
        # 4. Loop
        {
            "name": "4. Loop",
            "py": "def test():\n    acc = 0\n    for i in range(1, 4):\n        acc += i\n    return acc\n",
            "cpp": "int test() { int acc = 0; for (int i = 1; i <= 3; ++i) { acc += i; } return acc; }",
            "entry": "test",
            "expected_ret": 6
        },
        # 5. Function call
        {
            "name": "5. Function call",
            "py": "def add(a, b):\n    return a + b\ndef test():\n    return add(10, 25)\n",
            "cpp": "int add(int a, int b) { return a + b; }\nint test() { return add(10, 25); }",
            "entry": "test",
            "expected_ret": 35
        },
        # 6. Mutable object
        {
            "name": "6. Mutable object",
            "py": "def test():\n    b = [10]\n    b[0] = 42\n    return b[0]\n",
            "cpp": "struct Box { int val; };\nint test() { Box* b = new Box{10}; b->val = 42; return b->val; }",
            "entry": "test",
            "expected_ret": 42
        },
        # 7. Aliasing
        {
            "name": "7. Aliasing",
            "py": "def test():\n    a = [10]\n    b = a\n    b[0] = 99\n    return a[0]\n",
            "cpp": "struct Node { int val; };\nint test() { Node* a = new Node{10}; Node* b = a; b->val = 99; return a->val; }",
            "entry": "test",
            "expected_ret": 99
        },
        # 8. Nested mutable object
        {
            "name": "8. Nested mutable object",
            "py": "def test():\n    inner = [5]\n    outer = [inner]\n    outer[0][0] = 77\n    return inner[0]\n",
            "cpp": "struct Inner { int val; };\nstruct Outer { Inner* in; };\nint test() { Inner* in = new Inner{5}; Outer* out = new Outer{in}; out->in->val = 77; return in->val; }",
            "entry": "test",
            "expected_ret": 77
        },
        # 9. Container mutation
        {
            "name": "9. Container mutation",
            "py": "def test():\n    v = []\n    v.append(10)\n    v.append(20)\n    v.pop()\n    return len(v)\n",
            "cpp": "int test() { std::vector<int> v; v.push_back(10); v.push_back(20); v.pop_back(); int sz = v.size(); return sz; }",
            "entry": "test",
            "expected_ret": 1
        },
        # 10. Function-local scope
        {
            "name": "10. Function-local scope",
            "py": "def test():\n    x = 100\n    for _ in range(1):\n        y = 200\n        x += y\n    return x\n",
            "cpp": "int test() { int x = 100; { int y = 200; x += y; } return x; }",
            "entry": "test",
            "expected_ret": 300
        }
    ]

    for case in semantic_cases:
        name = case["name"]
        entry = case["entry"]
        expected = case["expected_ret"]

        # Run Python
        py_res = py_prod.execute_program(case["py"], entry_func=entry)
        assert py_res.success, f"[{name}] Python failed: {py_res.error_message}"
        py_state = UniversalRuntimeState()
        for ev in py_res.events:
            py_state = UniversalStateReducer.reduce(py_state, ev)

        # Extract Python return value from FRAME_POP or PROG_END
        py_ret = None
        for ev in reversed(py_res.events):
            if ev.event_type == "FRAME_POP" and ev.payload.get("return_value"):
                rv = ev.payload["return_value"]
                py_ret = rv.get("value") if isinstance(rv, dict) else getattr(rv, "value", rv)
                break
            elif ev.event_type == "PROG_END" and ev.payload.get("return_value"):
                rv = ev.payload["return_value"]
                py_ret = rv.get("value") if isinstance(rv, dict) else getattr(rv, "value", rv)
                break

        # Run C++
        cpp_res = cpp_prod.compile_and_run(case["cpp"], entry_func=entry)
        assert cpp_res.success, f"[{name}] C++ failed: {cpp_res.error_message}"
        cpp_state = UniversalRuntimeState()
        for ev in cpp_res.events:
            cpp_state = UniversalStateReducer.reduce(cpp_state, ev)

        cpp_ret = None
        for ev in reversed(cpp_res.events):
            if ev.event_type == "FRAME_POP" and ev.payload.get("return_value"):
                rv = ev.payload["return_value"]
                cpp_ret = rv.get("value") if isinstance(rv, dict) else getattr(rv, "value", rv)
                break

        assert py_ret == expected, f"[{name}] Python returned {py_ret}, expected {expected}"
        assert cpp_ret == expected, f"[{name}] C++ returned {cpp_ret}, expected {expected}"
        assert py_ret == cpp_ret, f"[{name}] Cross-language mismatch: Python {py_ret} != C++ {cpp_ret}"

        print(f"  [PASS] {name}: Python Ret={py_ret} == C++ Ret={cpp_ret} == Expected={expected}.")

    print("  All 10 Cross-Language Semantic Corpus test cases passed with 100% fidelity.")


# =====================================================================
# Test 15: Runtime Contract Polymorphism
# =====================================================================
def test_15_runtime_contract_polymorphism():
    print("\n--- 15. Testing Runtime Contract Polymorphism ---")
    py_prod: LanguageRuntimeProducer = PythonRuntimeProducer()
    cpp_prod: LanguageRuntimeProducer = NativeCompilationPipeline()

    assert isinstance(py_prod, LanguageRuntimeProducer)
    assert isinstance(cpp_prod, LanguageRuntimeProducer)

    def polymorphic_runner(producer: LanguageRuntimeProducer, code: str, entry: str) -> ExecutionResult:
        return producer.execute_program(code, entry_func=entry)

    py_res = polymorphic_runner(py_prod, "def main(): return 7", "main")
    cpp_res = polymorphic_runner(cpp_prod, "int main() { return 7; }", "main")

    assert isinstance(py_res, ExecutionResult)
    assert isinstance(cpp_res, ExecutionResult)
    assert py_res.success
    assert cpp_res.success
    print("  [PASS] Universal LanguageRuntimeProducer contract polymorphism verified.")


def run_all_milestone_7_tests():
    print("======================================================================")
    print("                ALGOLENS MILESTONE 7 VERIFICATION SUITE               ")
    print("======================================================================")
    t_start = time.perf_counter()

    test_1_python_scalar_execution()
    test_2_python_control_flow()
    test_3_python_function_frames()
    test_4_python_mutable_objects()
    test_5_python_aliasing()
    test_6_python_nested_containers()
    test_7_python_dict_and_set_operations()
    test_8_python_stdout_event_separation()
    test_9_python_timeout_enforcement()
    test_10_max_events_enforcement()
    test_11_fresh_runtime_ids_across_repeated_runs()
    test_12_forward_reverse_playback()
    test_13_arbitrary_seeking()
    test_14_cross_language_semantic_corpus()
    test_15_runtime_contract_polymorphism()

    elapsed = time.perf_counter() - t_start
    print("\n======================================================================")
    print(f">>> ALL 15 MILESTONE 7 TESTS PASSED SUCCESSFULLY IN {elapsed:.2f}s! <<<")
    print("======================================================================")


if __name__ == "__main__":
    run_all_milestone_7_tests()
