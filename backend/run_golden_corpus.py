import os
import json
import pytest
from golden_corpus import GOLDEN_TEST_CASES
from cpp_interpreter import CPPInterpreter

def test_golden_corpus_all_cases():
    results = {}
    print("\n--- Running AlgoLens 22 Golden Test Corpus Cases ---")
    for key, test_data in GOLDEN_TEST_CASES.items():
        code = test_data["code"]
        entry_func = test_data["entry_func"]
        args = test_data["args"]
        
        interpreter = CPPInterpreter(max_recursion_depth=100, max_total_steps=500)
        steps, ret_val = interpreter.interpret(code, entry_func, args)
        
        assert steps is not None and len(steps) > 0, f"Case {key} returned 0 steps"
        print(f"  [PASS] {key}: {len(steps)} steps generated. Return value: {ret_val}")
        
        # Format baseline trace summary
        trace_summary = {
            "step_count": len(steps),
            "return_value": str(ret_val),
            "line_sequence": [s.line_number for s in steps]
        }
        results[key] = trace_summary

    output_path = os.path.join(os.path.dirname(__file__), "golden_corpus_baseline.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved baseline trace summary to {output_path}")

if __name__ == "__main__":
    test_golden_corpus_all_cases()
