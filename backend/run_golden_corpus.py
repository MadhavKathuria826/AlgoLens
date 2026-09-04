"""
AlgoLens Automated Golden Test Corpus Runner
Automated regression test suite executing all 22 benchmark categories and validating
semantic execution invariants against golden_corpus_baseline.json.
"""

import os
import sys
import json
import pytest
from golden_corpus import GOLDEN_TEST_CASES
from cpp_interpreter import CPPInterpreter
from semantic_comparator import SemanticComparator, SemanticMismatchError

BASELINE_PATH = os.path.join(os.path.dirname(__file__), "golden_corpus_baseline.json")

def run_regression_suite(record_mode: bool = False):
    """
    Executes the 22 Golden Test cases.
    If record_mode is True, saves current outputs as baseline.
    If record_mode is False, asserts zero semantic divergence against existing baseline.
    """
    baseline = {}
    if not record_mode:
        if not os.path.exists(BASELINE_PATH):
            raise FileNotFoundError(f"Baseline file not found at {BASELINE_PATH}. Run with --record first.")
        with open(BASELINE_PATH, "r") as f:
            baseline = json.load(f)

    results = {}
    failures = []
    print(f"\n--- Running AlgoLens 22 Golden Test Regression Suite (Record Mode={record_mode}) ---")

    for key, test_data in GOLDEN_TEST_CASES.items():
        code = test_data["code"]
        entry_func = test_data["entry_func"]
        args = test_data["args"]

        interpreter = CPPInterpreter(max_recursion_depth=100, max_total_steps=500)
        steps, ret_val = interpreter.interpret(code, entry_func, args)

        assert steps is not None and len(steps) > 0, f"Case {key} generated 0 steps"

        current_summary = {
            "step_count": len(steps),
            "return_value": str(ret_val),
            "line_sequence": [s.line_number for s in steps]
        }
        results[key] = current_summary

        if not record_mode:
            expected = baseline.get(key)
            if not expected:
                failures.append(f"Missing baseline for test case: {key}")
                continue

            # 1. Semantic return value check
            if str(ret_val) != str(expected.get("return_value")):
                failures.append(
                    f"[{key}] Return value mismatch: expected {expected.get('return_value')}, got {ret_val}"
                )

            # 2. Semantic trace invariants check
            passed, mismatches = SemanticComparator.compare_traces(steps, expected, key)
            if not passed:
                failures.extend(mismatches)
            else:
                print(f"  [PASS] {key}: {len(steps)} steps verified. Invariants match.")
        else:
            print(f"  [RECORDED] {key}: {len(steps)} steps.")

    if record_mode:
        with open(BASELINE_PATH, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nSuccessfully recorded baseline for all {len(results)} cases to {BASELINE_PATH}")
    else:
        if failures:
            error_msg = f"\nRegression failure in {len(failures)} assertion(s):\n" + "\n".join(f" - {f}" for f in failures)
            raise SemanticMismatchError(error_msg)
        print(f"\nAll 22 Golden Test cases verified successfully against baseline. Zero regressions detected.")

def test_golden_corpus_regression():
    """Pytest entrypoint for automated CI regression."""
    run_regression_suite(record_mode=False)

if __name__ == "__main__":
    is_record = "--record" in sys.argv
    run_regression_suite(record_mode=is_record)
