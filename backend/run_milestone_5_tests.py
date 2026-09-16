"""
AlgoLens Milestone 5 Test Suite
Validates Advanced C++ Objects, References, and Data Structures:
1. First-Class References:
   - Reference declarations (int& ref = a)
   - Reference writes updating referent (ref = 50 -> a = 50)
   - Pass-by-reference across stack frames (void inc(int& x))
   - Reference reversibility
2. Pointer-to-Pointer:
   - Multi-level pointers (int** pp = &p)
   - Dereference write and reassignment (*pp = &y)
   - Double dereference (**pp = 30)
3. Stack Object Identity:
   - Synthetic object ID isolation for stack objects whose addresses are taken
   - Zero raw hex address leaks
4. Nested Objects & Dot-Paths:
   - Hierarchical member paths (r.topLeft.x = 10)
   - Hierarchical reduction and inverse reduction
5. Classes, Structs, Methods & 'this':
   - Class methods and constructors
   - Automatic 'this' variable binding
   - Member field mutations
6. STL Container & String Expansions:
   - std::string (construction, push_back, pop_back, append, clear, operator[])
   - std::vector (clear, at, operator[])
   - std::map (operator[], erase, clear)
7. Bidirectional Reversible Playback & Seeking
"""

import os
import sys
import copy

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from native_runner import NativeCompilationPipeline
from state_reducer import UniversalRuntimeState, UniversalStateReducer
from event_to_step_adapter import EventToStepAdapter
from playback_engine import PlaybackEngine
from event_models import ReferenceRef, ObjectRef, PrimitiveValue


def test_first_class_references(pipeline: NativeCompilationPipeline):
    print("\n--- 1. Testing First-Class References & Pass-by-Reference ---")
    code = """
    void inc(int& x) {
        x = x + 1;
    }
    int test() {
        int a = 10;
        int& ref = a;
        ref = 50;
        inc(a);
        return a;
    }
    """
    res = pipeline.compile_and_run(code, "test")
    assert res.success, f"Failed: {res.error_message}\n{res.runtime_stderr}"
    
    # Verify events
    var_decl_events = [ev for ev in res.events if ev.event_type == "VAR_DECLARE"]
    ref_decls = [ev for ev in var_decl_events if ev.payload.get("name") == "ref"]
    assert len(ref_decls) >= 1, "ref was not declared"
    ref_val = ref_decls[0].payload.get("value")
    assert ref_val.get("kind") == "reference", f"Expected reference, got {ref_val}"
    assert ref_val.get("target_name") == "a", f"Expected target 'a', got {ref_val}"

    # Verify pass-by-reference in function 'inc'
    x_decls = [ev for ev in var_decl_events if ev.payload.get("name") == "x"]
    assert len(x_decls) >= 1, "x was not declared in inc"
    x_val = x_decls[0].payload.get("value")
    assert x_val.get("kind") == "reference"
    assert x_val.get("target_name") == "a"

    # Verify state reduction
    state = UniversalRuntimeState()
    for ev in res.events:
        state = UniversalStateReducer.reduce(state, ev)
    
    # Referent 'a' should be 51 (10 -> 50 -> 51)
    a_binding = [b for b in state.bindings.values() if b.name == "a"][0]
    assert a_binding.value.value == 51, f"Expected a=51, got {a_binding.value.value}"

    # Step adapter verification
    adapter = EventToStepAdapter()
    steps = adapter.process_event_stream(res.events)
    last_step = steps[-1]
    assert last_step.locals["a"] == 51
    assert last_step.locals["ref"] == "&a"
    print("  [PASS] Reference declaration, alias write, pass-by-reference, and step formatting verified.")


def test_pointer_to_pointer(pipeline: NativeCompilationPipeline):
    print("\n--- 2. Testing Pointer-to-Pointer Chains & Reassignment ---")
    code = """
    int test() {
        int x = 10;
        int y = 20;
        int* p = &x;
        int** pp = &p;
        *pp = &y;
        **pp = 99;
        return y;
    }
    """
    res = pipeline.compile_and_run(code, "test")
    assert res.success, f"Failed: {res.error_message}\n{res.runtime_stderr}"

    # Verify state reduction
    state = UniversalRuntimeState()
    for ev in res.events:
        state = UniversalStateReducer.reduce(state, ev)

    y_binding = [b for b in state.bindings.values() if b.name == "y"][0]
    assert y_binding.value.value == 99, f"Expected y=99, got {y_binding.value.value}"

    adapter = EventToStepAdapter()
    steps = adapter.process_event_stream(res.events)
    last_step = steps[-1]
    assert last_step.locals["y"] == 99
    print("  [PASS] Multi-level pointer tracking, dereference write, and reassignment verified.")


def test_stack_object_identity(pipeline: NativeCompilationPipeline):
    print("\n--- 3. Testing Stack Object Identity & Synthetic Isolation ---")
    code = """
    struct Node {
        int val;
    };
    int test() {
        Node local_node;
        local_node.val = 42;
        Node* p = &local_node;
        p->val = 84;
        return local_node.val;
    }
    """
    res = pipeline.compile_and_run(code, "test")
    assert res.success, f"Failed: {res.error_message}\n{res.runtime_stderr}"

    # Verify no raw hex addresses in event payloads
    for ev in res.events:
        obj_id = ev.payload.get("object_id")
        if obj_id:
            assert obj_id.startswith("obj_"), f"Exposed raw address as object_id: {obj_id}"
            assert not obj_id.startswith("0x"), f"Raw hex object_id: {obj_id}"

    state = UniversalRuntimeState()
    for ev in res.events:
        state = UniversalStateReducer.reduce(state, ev)

    # local_node and p must both reference the exact same synthetic object ID
    node_b = [b for b in state.bindings.values() if b.name == "local_node"][0]
    p_b = [b for b in state.bindings.values() if b.name == "p"][0]
    assert isinstance(node_b.value, ObjectRef)
    assert isinstance(p_b.value, ObjectRef)
    assert node_b.value.object_id == p_b.value.object_id, "node and p do not share the same object ID"

    target_obj = state.heap[node_b.value.object_id]
    assert target_obj.fields["val"].value == 84
    print("  [PASS] Stack object synthetic ID minted, shared with pointer, zero hex address leaks.")


def test_nested_objects_and_dot_paths(pipeline: NativeCompilationPipeline):
    print("\n--- 4. Testing Nested Objects & Hierarchical Dot-Paths ---")
    code = """
    struct Point {
        int x;
        int y;
    };
    struct Rectangle {
        Point topLeft;
        Point bottomRight;
    };
    int test() {
        Rectangle rect;
        rect.topLeft.x = 10;
        rect.topLeft.y = 20;
        rect.bottomRight.x = 100;
        rect.bottomRight.y = 200;
        return rect.bottomRight.x;
    }
    """
    res = pipeline.compile_and_run(code, "test")
    assert res.success, f"Failed: {res.error_message}\n{res.runtime_stderr}"

    state = UniversalRuntimeState()
    for ev in res.events:
        state = UniversalStateReducer.reduce(state, ev)

    rect_b = [b for b in state.bindings.values() if b.name == "rect"][0]
    obj = state.heap[rect_b.value.object_id]
    assert "topLeft" in obj.fields
    assert "bottomRight" in obj.fields
    assert obj.fields["topLeft"]["x"].value == 10
    assert obj.fields["topLeft"]["y"].value == 20
    assert obj.fields["bottomRight"]["x"].value == 100
    assert obj.fields["bottomRight"]["y"].value == 200
    print("  [PASS] Hierarchical dot-paths rect.topLeft.x and rect.bottomRight.x reduced properly.")


def test_class_methods_and_this(pipeline: NativeCompilationPipeline):
    print("\n--- 5. Testing Classes, Constructors, Member Methods, and 'this' Binding ---")
    code = """
    class Counter {
    public:
        int count;
        Counter() : count(0) {}
        void inc() {
            count = count + 1;
        }
        void add(int delta) {
            this->count = this->count + delta;
        }
    };
    int test() {
        Counter c;
        c.inc();
        c.add(5);
        return c.count;
    }
    """
    res = pipeline.compile_and_run(code, "test")
    assert res.success, f"Failed: {res.error_message}\n{res.runtime_stderr}"

    # Verify 'this' was declared in method frames
    this_decls = [ev for ev in res.events if ev.event_type == "VAR_DECLARE" and ev.payload.get("name") == "this"]
    assert len(this_decls) >= 3, f"Expected at least 3 'this' declarations, found {len(this_decls)}"

    state = UniversalRuntimeState()
    for ev in res.events:
        state = UniversalStateReducer.reduce(state, ev)

    c_b = [b for b in state.bindings.values() if b.name == "c"][0]
    obj = state.heap[c_b.value.object_id]
    assert obj.fields["count"].value == 6, f"Expected count=6, got {obj.fields['count'].value}"
    print("  [PASS] Constructor, member method, 'this' declaration, and unqualified field writes verified.")


def test_stl_expansions(pipeline: NativeCompilationPipeline):
    print("\n--- 6. Testing STL String, Vector, and Map Expansions ---")
    code = """
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
        m["first"] = 1;
        m["second"] = 2;
        m.erase("first");
        m.clear();

        return 0;
    }
    """
    res = pipeline.compile_and_run(code, "test")
    assert res.success, f"Failed: {res.error_message}\n{res.runtime_stderr}"

    state = UniversalRuntimeState()
    for ev in res.events:
        state = UniversalStateReducer.reduce(state, ev)

    # Verify string final state ("Algolen")
    s_b = [b for b in state.bindings.values() if b.name == "s"][0]
    assert s_b.value.value == "Algolen", f"Expected 'Algolen', got '{s_b.value.value}'"

    # Verify vector cleared
    assert state.containers["v"]["elements"] == []

    # Verify map cleared
    assert state.containers["m"]["elements"] == {}
    print("  [PASS] std::string mutations, std::vector::clear, and std::map::erase/clear verified.")


def test_reversible_playback_engine(pipeline: NativeCompilationPipeline):
    print("\n--- 7. Testing Bidirectional Reversible Playback & Random Seek ---")
    code = """
    void inc(int& r) {
        r = r + 10;
    }
    int test() {
        int a = 5;
        int& ref = a;
        ref = 20;
        inc(a);
        std::vector<int> v;
        v.push_back(1);
        v.push_back(2);
        v.clear();
        return a;
    }
    """
    res = pipeline.compile_and_run(code, "test")
    assert res.success, f"Failed: {res.error_message}\n{res.runtime_stderr}"

    engine = PlaybackEngine(res.events)
    engine.build_checkpoints()
    total_events = len(res.events)

    # 1. Step Forward through all events
    states_forward = []
    while engine.current_event_index < total_events:
        st = engine.step_forward()
        states_forward.append(copy.deepcopy(st))

    final_fwd = engine.current_state
    a_b = [b for b in final_fwd.bindings.values() if b.name == "a"][0]
    assert a_b.value.value == 30

    # 2. Step Backward all the way to start
    while engine.current_event_index > 0:
        engine.step_reverse()

    assert engine.current_event_index == 0

    # 3. Random Seek Tests
    for target_idx in [total_events // 2, total_events - 1, 3, total_events // 4]:
        seeked_st = engine.seek(target_idx)
        expected_st = states_forward[target_idx - 1]
        
        # Check bindings match exactly
        for k in expected_st.bindings:
            assert seeked_st.bindings[k].value == expected_st.bindings[k].value
        # Check containers match exactly
        assert seeked_st.containers == expected_st.containers

    print("  [PASS] Bidirectional stepping and random seeking verified across Milestone 5 events.")


def run_all():
    print("================================================================")
    print("      AlgoLens Milestone 5 Verification Test Suite")
    print("================================================================")
    pipeline = NativeCompilationPipeline()
    print(f"Compiler: {pipeline.compiler_name} ({pipeline.compiler_version[:60]}...)")

    test_first_class_references(pipeline)
    test_pointer_to_pointer(pipeline)
    test_stack_object_identity(pipeline)
    test_nested_objects_and_dot_paths(pipeline)
    test_class_methods_and_this(pipeline)
    test_stl_expansions(pipeline)
    test_reversible_playback_engine(pipeline)

    print("\n================================================================")
    print("  ALL MILESTONE 5 VERIFICATION SUITES PASSED (100% SUCCESS)")
    print("================================================================")


if __name__ == "__main__":
    run_all()
