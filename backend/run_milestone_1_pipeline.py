"""
Milestone 1 Compatibility Pipeline Validation Test Suite
Validates that:
CPPInterpreter -> AlgoLens Events -> UniversalStateReducer -> EventToStepAdapter -> Steps
produces semantically identical execution traces to the legacy reference interpreter across all 22 Golden Test cases.
"""

import pytest
from golden_corpus import GOLDEN_TEST_CASES
from cpp_interpreter import CPPInterpreter
from semantic_comparator import SemanticComparator, SemanticMismatchError
from event_models import AlgoLensEvent


def test_milestone_1_all_22_golden_cases():
    print("\n--- Running Milestone 1 Compatibility Pipeline for all 22 Golden Test Cases ---")
    all_events_count = 0
    failures = []

    for key, test_data in GOLDEN_TEST_CASES.items():
        code = test_data["code"]
        entry_func = test_data["entry_func"]
        args = test_data["args"]

        # 1. Run Legacy Pipeline
        legacy_interpreter = CPPInterpreter(max_recursion_depth=100, max_total_steps=500)
        legacy_steps, legacy_ret = legacy_interpreter.interpret(code, entry_func, args)

        # 2. Run Compatibility Pipeline (Interpreter -> Events -> Reducer -> Adapter -> Steps)
        event_interpreter = CPPInterpreter(max_recursion_depth=100, max_total_steps=500)
        events, reconstructed_steps, event_ret = event_interpreter.interpret_with_events(code, entry_func, args)

        assert len(events) > 0, f"[{key}] No events generated"
        all_events_count += len(events)

        # 3. Assert Synthetic Identity Invariant (No raw C++ addresses in event keys)
        for ev in events:
            assert isinstance(ev, AlgoLensEvent), f"[{key}] Invalid event type: {type(ev)}"
            assert not ev.frame_id.startswith("0x"), f"[{key}] Frame ID leaked native address: {ev.frame_id}"
            assert not ev.scope_id.startswith("0x"), f"[{key}] Scope ID leaked native address: {ev.scope_id}"
            if ev.event_type == "OBJECT_ALLOCATE":
                assert ev.payload["object_id"].startswith("obj_"), f"[{key}] Non-synthetic object_id: {ev.payload['object_id']}"

        # 4. Compare return values
        if str(legacy_ret) != str(event_ret):
            failures.append(f"[{key}] Return value mismatch: legacy={legacy_ret}, compatibility={event_ret}")

        # 5. Compare step counts and line sequences
        baseline_summary = {
            "step_count": len(legacy_steps),
            "return_value": str(legacy_ret),
            "line_sequence": [s.line_number for s in legacy_steps]
        }
        passed, mismatches = SemanticComparator.compare_traces(reconstructed_steps, baseline_summary, key)
        if not passed:
            failures.extend(mismatches)
        else:
            print(f"  [PASS] {key}: {len(legacy_steps)} legacy steps == {len(reconstructed_steps)} adapted steps. Events: {len(events)}.")

    print(f"\nTotal AlgoLens events processed across 22 test cases: {all_events_count}")

    if failures:
        err = f"Milestone 1 Compatibility Pipeline failed on {len(failures)} assertion(s):\n" + "\n".join(f" - {f}" for f in failures)
        raise SemanticMismatchError(err)

    print("Milestone 1 Compatibility Pipeline: ALL 22 GOLDEN CASES PASSED WITH ZERO REGRESSIONS.")


if __name__ == "__main__":
    test_milestone_1_all_22_golden_cases()
