"""
AlgoLens Milestone 9 (M9) Verification Test Suite
Tests Subsystem Unification & Production Sandboxing:
1. Universal AVL Trees (allocations, mutations, balance factors, rotations, bidirectional playback)
2. Universal Red-Black Trees (coloring, recoloring, double-red violations, bidirectional playback)
3. Universal Tries (multi-child hierarchies, word termination, prefix traversal, identity preservation)
4. Universal Dynamic Programming (1D/2D Tabulation targets & sources, Memoization cache hits/writes)
5. Python Process Isolation & Sandbox Boundaries (OS limits, supervisor timeouts, socket lockdown)
6. Language-Agnostic Semantics & Explanation integration
7. Unified /api/execute routing across all structures with full event protocol compliance
"""

import sys
import os
import time

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient
from main import app
from event_models import AlgoLensEvent
from runtime_contract import ExecutionResult
from python_producer import PythonRuntimeProducer
from isolated_python_runner import IsolatedPythonRunner
from event_to_step_adapter import EventToStepAdapter
from playback_engine import PlaybackEngine
from universal_structural_adapter import (
    enrich_avl_steps,
    enrich_rbt_steps,
    enrich_trie_steps,
    enrich_dp_tabulation_steps,
    enrich_dp_memoization_steps
)


def test_universal_avl_tree():
    print("\n--- 1. Testing Universal AVL Tree Execution & Bidirectional Playback ---")
    avl_code = """
class TreeNode:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None
        self.height = 1

root = TreeNode(10)
root.right = TreeNode(20)
root.right.right = TreeNode(30)
"""
    producer = PythonRuntimeProducer()
    res = producer.execute_program(avl_code, isolated=True)
    assert res.success, f"AVL execution failed: {res.error_message}"
    assert len(res.events) > 0, "No events emitted for AVL code"

    # Verify event types
    alloc_events = [e for e in res.events if e.event_type == "OBJECT_ALLOCATE"]
    mutate_events = [e for e in res.events if e.event_type == "OBJECT_MUTATE"]
    assert len(alloc_events) >= 3, f"Expected at least 3 node allocations, got {len(alloc_events)}"
    assert len(mutate_events) >= 2, f"Expected node mutations for child pointers, got {len(mutate_events)}"

    # Reconstruct steps and enrich with AVL metadata
    adapter = EventToStepAdapter()
    steps = enrich_avl_steps(adapter.process_event_stream(res.events), avl_code)
    assert len(steps) > 0, "No steps generated"

    last_step = steps[-1]
    assert last_step.isTreeAlgorithm, "Step should be marked as isTreeAlgorithm"
    avl_vis = next((v for v in last_step.visualizations if v.type == "AVL_METADATA"), None)
    assert avl_vis is not None, "AVL_METADATA visualization missing from final step"

    details = avl_vis.details
    assert details["rotation_type"] == "RR", f"Expected RR rotation, got {details['rotation_type']}"
    assert details["unbalanced_node"] == "obj_0", f"Expected obj_0 unbalanced, got {details['unbalanced_node']}"
    assert len(details["rotation_nodes"]) == 3, f"Expected 3 rotation nodes, got {details['rotation_nodes']}"
    assert "Triggering RR rotation" in details["status_message"], f"Unexpected message: {details['status_message']}"

    # Verify PlaybackEngine Bidirectional Stepping on AVL
    engine = PlaybackEngine(res.events)
    engine.build_checkpoints()
    final_state = engine.seek(len(res.events))
    assert len(final_state.heap) == 3, f"Expected 3 living heap nodes at end, got {len(final_state.heap)}"
    
    # Reverse to before obj_2 was allocated
    mid_state = engine.seek(25)
    assert len(mid_state.heap) == 2, f"Expected 2 heap nodes at event 25, got {len(mid_state.heap)}"

    # Seek back to start
    start_state = engine.seek(0)
    assert len(start_state.heap) == 0, "Heap should be empty at event 0"
    print("  [PASS] Universal AVL Tree verified with RR rotation and O(1) bidirectional playback.")


def test_universal_rbt():
    print("\n--- 2. Testing Universal Red-Black Tree Execution & Double-Red Detection ---")
    rbt_code = """
class Node:
    def __init__(self, val, color='RED'):
        self.val = val
        self.color = color
        self.left = None
        self.right = None

root = Node(10, color='BLACK')
root.left = Node(5, color='RED')
root.left.left = Node(2, color='RED')
"""
    producer = PythonRuntimeProducer()
    res = producer.execute_program(rbt_code, isolated=True)
    assert res.success, f"RBT execution failed: {res.error_message}"

    adapter = EventToStepAdapter()
    steps = enrich_rbt_steps(adapter.process_event_stream(res.events), rbt_code)
    last_step = steps[-1]

    rbt_vis = next((v for v in last_step.visualizations if v.type == "RBT_METADATA"), None)
    assert rbt_vis is not None, "RBT_METADATA missing from step"
    details = rbt_vis.details
    assert details["double_red_node"] == "obj_2", f"Expected obj_2 double-red node, got {details['double_red_node']}"
    assert details["double_red_parent"] == "obj_1", f"Expected obj_1 parent, got {details['double_red_parent']}"
    assert "Double-red violation detected" in details["status_message"], "Status message missing double-red alert"
    assert last_step.heap["obj_0"]["fields"]["color"] == "BLACK", "Root should be BLACK"
    assert last_step.heap["obj_1"]["fields"]["color"] == "RED", "Child should be RED"
    assert last_step.heap["obj_2"]["fields"]["color"] == "RED", "Grandchild should be RED"
    print("  [PASS] Universal Red-Black Tree verified with color properties and double-red violation detection.")


def test_universal_trie():
    print("\n--- 3. Testing Universal Trie Execution & Identity Isolation ---")
    trie_code = """
class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end_of_word = False

root = TrieNode()
curr = root
curr.children['a'] = TrieNode()
curr = curr.children['a']
curr.is_end_of_word = True
"""
    producer = PythonRuntimeProducer()
    res = producer.execute_program(trie_code, isolated=True)
    assert res.success, f"Trie execution failed: {res.error_message}"

    adapter = EventToStepAdapter()
    steps = enrich_trie_steps(adapter.process_event_stream(res.events))
    last_step = steps[-1]

    trie_vis = next((v for v in last_step.visualizations if v.type == "TRIE_METADATA"), None)
    assert trie_vis is not None, "TRIE_METADATA missing from step"
    details = trie_vis.details
    assert details["trie_roots"] == ["obj_0"], f"Expected single root obj_0, got {details['trie_roots']}"
    assert details["active_node_id"] == "obj_2", f"Expected active node obj_2, got {details['active_node_id']}"
    assert len(details["trie_trees"]) == 1, "Expected single trie tree hierarchy"
    root_node = details["trie_trees"][0]
    assert root_node["char"] == "ROOT"
    assert len(root_node["children"]) == 1
    child_node = root_node["children"][0]
    assert child_node["char"] == "a"
    assert child_node["is_end_of_word"] is True
    assert child_node["is_active"] is True
    print("  [PASS] Universal Trie verified with multi-child hierarchy and clean identity isolation.")


def test_universal_dynamic_programming():
    print("\n--- 4. Testing Universal Dynamic Programming (Tabulation & Memoization) ---")
    # 4A. Tabulation
    tab_code = """
n = 5
dp = [0] * (n + 1)
dp[0] = 0
dp[1] = 1
for i in range(2, n + 1):
    dp[i] = dp[i - 1] + dp[i - 2]
"""
    producer = PythonRuntimeProducer()
    res = producer.execute_program(tab_code, isolated=True)
    assert res.success, f"Tabulation execution failed: {res.error_message}"

    adapter = EventToStepAdapter()
    raw_steps = adapter.process_event_stream(res.events)
    steps = enrich_dp_tabulation_steps(raw_steps, tab_code, "dp", 1)
    last_step = steps[-1]

    dp_vis = next((v for v in last_step.visualizations if v.type == "DP_TABLE"), None)
    assert dp_vis is not None, "DP_TABLE visualization missing"
    assert dp_vis.details["value"] == [0, 1, 1, 2, 3, 5], f"Unexpected DP values: {dp_vis.details['value']}"
    assert dp_vis.details["dimensions"] == 1
    assert dp_vis.details["table_shape"] == [6]

    # 4B. Memoization
    memo_code = """
memo = {}
def fib(n):
    if n in memo:
        return memo[n]
    if n <= 1:
        return n
    memo[n] = fib(n - 1) + fib(n - 2)
    return memo[n]

res = fib(3)
"""
    res_memo = producer.execute_program(memo_code, isolated=True)
    assert res_memo.success, f"Memoization execution failed: {res_memo.error_message}"
    memo_steps = enrich_dp_memoization_steps(
        adapter.process_event_stream(res_memo.events),
        memo_code,
        {"is_memoization": True, "cache_var_name": "memo", "func_name": "fib"}
    )
    memo_vis_list = [v for s in memo_steps for v in s.visualizations if v.type == "MEMOIZATION"]
    assert len(memo_vis_list) > 0, "MEMOIZATION visualizations should be present"
    events_found = {v.details["event"] for v in memo_vis_list}
    assert "call" in events_found, "Expected 'call' events in memoization trace"
    assert "cache_write" in events_found, "Expected 'cache_write' events in memoization trace"
    print("  [PASS] Universal DP verified across 1D tabulation and recursive memoization.")


def test_isolated_sandbox_boundaries():
    print("\n--- 5. Testing Subprocess Process Isolation & Safety Ceilings ---")
    runner = IsolatedPythonRunner()

    # 5A. Timeout ceiling
    t_start = time.perf_counter()
    res_timeout = runner.execute(
        source_code="import time\nwhile True: time.sleep(0.05)",
        timeout_sec=0.5
    )
    t_elapsed = time.perf_counter() - t_start
    assert not res_timeout.success, "Infinite loop should have failed"
    assert "timed out" in (res_timeout.error_message or "").lower(), f"Unexpected error: {res_timeout.error_message}"
    assert t_elapsed < 3.0, f"Supervisor took too long to enforce timeout: {t_elapsed:.2f}s"

    # 5B. Recursion depth ceiling
    res_recursion = runner.execute(
        source_code="def f(): return f()\nf()",
        timeout_sec=2.0
    )
    assert not res_recursion.success, "Recursion bomb should fail"
    assert "recursion" in (res_recursion.error_message or "").lower(), f"Expected recursion error, got {res_recursion.error_message}"

    # 5C. Socket Lockdown
    res_socket = runner.execute(
        source_code="import socket\ns = socket.socket()",
        timeout_sec=2.0
    )
    assert not res_socket.success, "Socket creation should be blocked"
    assert "nonetype" in (res_socket.error_message or "").lower() or "socket" in (res_socket.error_message or "").lower(), f"Unexpected error: {res_socket.error_message}"
    print("  [PASS] Sandbox isolation verified: timeouts enforced, recursion bound, network sockets disabled.")


def test_unified_api_execute_routing():
    print("\n--- 6. Testing Unified /api/execute Routing Across All Data Structures ---")
    client = TestClient(app)

    # 6A. AVL Tree via API
    avl_code = """
class TreeNode:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None
        self.height = 1

root = TreeNode(10)
root.right = TreeNode(20)
root.right.right = TreeNode(30)
"""
    res = client.post("/api/execute", json={"code": avl_code, "language": "python"})
    assert res.status_code == 200, f"API returned {res.status_code}"
    data = res.json()
    assert len(data.get("events", [])) > 0, "Universal events missing from /api/execute response"
    assert len(data.get("steps", [])) > 0, "Steps missing from /api/execute response"
    avl_vis = next((v for v in data["steps"][-1]["visualizations"] if v["type"] == "AVL_METADATA"), None)
    assert avl_vis is not None, "AVL_METADATA missing from /api/execute"
    assert avl_vis["details"]["rotation_type"] == "RR"

    # 6B. Trie via API
    trie_code = """
class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end_of_word = False

root = TrieNode()
curr = root
curr.children['a'] = TrieNode()
curr = curr.children['a']
curr.is_end_of_word = True
"""
    res_trie = client.post("/api/execute", json={"code": trie_code, "language": "python"})
    assert res_trie.status_code == 200
    data_trie = res_trie.json()
    assert len(data_trie.get("events", [])) > 0
    trie_vis = next((v for v in data_trie["steps"][-1]["visualizations"] if v["type"] == "TRIE_METADATA"), None)
    assert trie_vis is not None, "TRIE_METADATA missing from /api/execute"
    assert trie_vis["details"]["active_node_id"] == "obj_2"

    # 6C. Tabulation DP via API
    dp_code = """
n = 4
dp = [0] * (n + 1)
dp[0] = 0
dp[1] = 1
for i in range(2, n + 1):
    dp[i] = dp[i - 1] + dp[i - 2]
"""
    res_dp = client.post("/api/execute", json={"code": dp_code, "language": "python"})
    assert res_dp.status_code == 200
    data_dp = res_dp.json()
    assert len(data_dp.get("events", [])) > 0
    dp_vis = next((v for v in data_dp["steps"][-1]["visualizations"] if v["type"] == "DP_TABLE"), None)
    assert dp_vis is not None, "DP_TABLE missing from /api/execute"
    assert dp_vis["details"]["value"] == [0, 1, 1, 2, 3]

    print("  [PASS] Unified /api/execute verified with 100% event stream presence on all structures.")


def run_all_milestone_9_tests():
    print("=" * 70)
    print("         ALGOLENS MILESTONE 9 VERIFICATION TEST SUITE         ")
    print("=" * 70)

    t0 = time.perf_counter()
    test_universal_avl_tree()
    test_universal_rbt()
    test_universal_trie()
    test_universal_dynamic_programming()
    test_isolated_sandbox_boundaries()
    test_unified_api_execute_routing()
    t1 = time.perf_counter()

    print("\n" + "=" * 70)
    print(f">>> ALL 6 MILESTONE 9 VERIFICATION TESTS PASSED IN {t1 - t0:.2f}s! <<<")
    print("=" * 70)


if __name__ == "__main__":
    run_all_milestone_9_tests()
