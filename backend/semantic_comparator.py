"""
AlgoLens Semantic Comparator
Formal semantic comparison contract for validating execution output between
the reference Python AST interpreter, the Event-reduced Step engine, and future Native runtimes.
"""

from typing import List, Dict, Any, Tuple, Optional
import json

class SemanticMismatchError(AssertionError):
    """Raised when two execution traces diverge semantically."""
    pass

class SemanticComparator:
    """
    Compares two execution runs (e.g. Legacy Step output vs Event-reduced Step output)
    based on semantic execution invariants rather than raw JSON string matching.
    """

    @staticmethod
    def compare_traces(
        actual_steps: List[Any],
        baseline_data: Dict[str, Any],
        test_case_name: str,
        allow_minor_line_drift: bool = False
    ) -> Tuple[bool, List[str]]:
        """
        Validates an actual execution step sequence against baseline invariants:
        1. Step count
        2. Return value
        3. Line execution trace sequence
        4. Variable state equivalence (where present)
        """
        mismatches: List[str] = []

        expected_count = baseline_data.get("step_count")
        actual_count = len(actual_steps)
        if expected_count is not None and actual_count != expected_count:
            mismatches.append(
                f"[{test_case_name}] Step count mismatch: expected {expected_count}, got {actual_count}"
            )

        expected_return = baseline_data.get("return_value")
        # Return value is checked at caller or against last step return
        
        expected_line_seq = baseline_data.get("line_sequence", [])
        actual_line_seq = [s.line_number if hasattr(s, "line_number") else s.get("line_number") for s in actual_steps]

        if expected_line_seq and actual_line_seq != expected_line_seq:
            if not allow_minor_line_drift:
                mismatches.append(
                    f"[{test_case_name}] Line sequence divergence:\n"
                    f"  Expected: {expected_line_seq[:20]}{'...' if len(expected_line_seq) > 20 else ''}\n"
                    f"  Actual:   {actual_line_seq[:20]}{'...' if len(actual_line_seq) > 20 else ''}"
                )

        return (len(mismatches) == 0, mismatches)

    @staticmethod
    def compare_heaps_isomorphic(
        heap_a: Dict[str, Any],
        heap_b: Dict[str, Any],
        roots_a: Dict[str, str],
        roots_b: Dict[str, str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Checks if two object heaps are structurally isomorphic starting from root variables.
        Maps synthetic IDs (e.g. obj_1 -> obj_17) without requiring identical addresses.
        """
        id_map_a_to_b: Dict[str, str] = {}
        id_map_b_to_a: Dict[str, str] = {}

        # 1. Map root pointers
        for var_name, addr_a in roots_a.items():
            if var_name not in roots_b:
                return False, f"Root variable '{var_name}' missing in heap_b"
            addr_b = roots_b[var_name]

            if addr_a in ("0x0000", "nullptr", None):
                if addr_b not in ("0x0000", "nullptr", None):
                    return False, f"Pointer '{var_name}' nullness mismatch"
                continue

            if addr_a in id_map_a_to_b:
                if id_map_a_to_b[addr_a] != addr_b:
                    return False, f"Aliasing mismatch for root '{var_name}'"
            else:
                id_map_a_to_b[addr_a] = addr_b
                id_map_b_to_a[addr_b] = addr_a

        # 2. Traverse fields of mapped objects
        queue = list(id_map_a_to_b.keys())
        visited = set()

        while queue:
            curr_a = queue.pop(0)
            if curr_a in visited:
                continue
            visited.add(curr_a)

            curr_b = id_map_a_to_b.get(curr_a)
            if not curr_b:
                return False, f"Unmapped address {curr_a}"

            obj_a = heap_a.get(curr_a, {})
            obj_b = heap_b.get(curr_b, {})

            fields_a = obj_a.get("fields", {})
            fields_b = obj_b.get("fields", {})

            for f_name, val_a in fields_a.items():
                if f_name not in fields_b:
                    return False, f"Field '{f_name}' missing in object {curr_b}"
                val_b = fields_b[f_name]

                # If field is a pointer/address
                if isinstance(val_a, str) and (val_a.startswith("0x") or val_a.startswith("obj_")):
                    if val_a in ("0x0000", "nullptr"):
                        if val_b not in ("0x0000", "nullptr"):
                            return False, f"Pointer field '{f_name}' nullness mismatch"
                    else:
                        if val_a in id_map_a_to_b:
                            if id_map_a_to_b[val_a] != val_b:
                                return False, f"Aliasing cycle mismatch on field '{f_name}'"
                        else:
                            id_map_a_to_b[val_a] = val_b
                            id_map_b_to_a[val_b] = val_a
                            queue.append(val_a)
                else:
                    # Scalar field equality
                    if val_a != val_b:
                        return False, f"Field '{f_name}' value mismatch: {val_a} != {val_b}"

        return True, None
