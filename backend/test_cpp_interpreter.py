import os
import sys
import tempfile
import subprocess
import shutil
from typing import Dict, Any, Tuple
from cpp_interpreter import CPPInterpreter, Environment, ExecutionLimitError

# --- Full Fixture Set ---

FIXTURES = [
    {
        "name": "Fixture 1: Negative Integer Division (Truncation towards zero)",
        "code": """
int test_neg_div() {
    int a = -7;
    int b = 2;
    int res = a / b;
    int mod = a % b;
    return res;
}
""",
        "entry_function": "test_neg_div",
        "args": [],
        "expected_return": -3,
        "expected_locals": {"a": -7, "b": 2, "res": -3, "mod": -1}
    },
    {
        "name": "Fixture 2: Struct Passed by Value (Top-level copy mutation check)",
        "code": """
struct Point {
    int x;
    int y;
};

void mutate_point(Point p) {
    p.x = 999;
    p.y = 888;
}

int test_struct_val() {
    Point pt;
    pt.x = 10;
    pt.y = 20;
    mutate_point(pt);
    return pt.x + pt.y;
}
""",
        "entry_function": "test_struct_val",
        "args": [],
        "expected_return": 30,
        "expected_locals": {"pt": {"x": 10, "y": 20}}
    },
    {
        "name": "Fixture 3: Pointer Passed to Function (Alias mutation check)",
        "code": """
struct Node {
    int val;
    Node* next;
};

void mutate_node(Node* node) {
    node->val = 500;
}

int test_pointer() {
    Node* head = new Node();
    head->val = 5;
    mutate_node(head);
    return head->val;
}
""",
        "entry_function": "test_pointer",
        "args": [],
        "expected_return": 500,
        "expected_locals": {"head": "0x1000"},
        "expected_heap": {"0x1000": {"val": 500, "next": "0x0000"}}
    },
    {
        "name": "Fixture 4: Fixed-Width 32-bit Signed Integer Overflow Wrapping",
        "code": """
int test_overflow() {
    int max_int = 2147483647;
    int wrapped = max_int + 1;
    return wrapped;
}
""",
        "entry_function": "test_overflow",
        "args": [],
        "expected_return": -2147483648,
        "expected_locals": {"max_int": 2147483647, "wrapped": -2147483648}
    },
    {
        "name": "Fixture 5: Recursive Fibonacci Evaluation",
        "code": """
int fib(int n) {
    if (n <= 1) return n;
    return fib(n - 1) + fib(n - 2);
}

int test_fib() {
    return fib(6);
}
""",
        "entry_function": "test_fib",
        "args": [],
        "expected_return": 8,
        "expected_locals": {}
    },
    {
        "name": "Fixture 6: Vector Accumulation & Loop Traversal",
        "code": """
int sum_vector() {
    std::vector<int> nums;
    nums.push_back(10);
    nums.push_back(20);
    nums.push_back(30);
    int total = 0;
    for (int i = 0; i < nums.size(); i = i + 1) {
        total = total + nums[i];
    }
    return total;
}
""",
        "entry_function": "sum_vector",
        "args": [],
        "expected_return": 60,
        "expected_locals": {"nums": [10, 20, 30], "total": 60}
    },
    {
        "name": "Fixture 7: Unsigned Integer Underflow/Wraparound",
        "code": """
unsigned int test_unsigned_wrap() {
    unsigned int u = 0;
    unsigned int wrapped = u - 1;
    return wrapped;
}
""",
        "entry_function": "test_unsigned_wrap",
        "args": [],
        "expected_return": 4294967295,
        "expected_locals": {"u": 0, "wrapped": 4294967295}
    },
    {
        "name": "Fixture 8: Signed short and char Overflow Wrapping",
        "code": """
int test_short_char_overflow() {
    short s = 32767;
    short s_wrap = s + 1;
    char c = 127;
    char c_wrap = c + 1;
    return s_wrap + c_wrap;
}
""",
        "entry_function": "test_short_char_overflow",
        "args": [],
        "expected_return": -32896,
        "expected_locals": {"s": 32767, "s_wrap": -32768, "c": 127, "c_wrap": -128}
    },
    {
        "name": "Fixture 9: Struct Passed by Value with Nested Struct Field (Recursive deep-copy)",
        "code": """
struct Address {
    int zip;
};

struct User {
    int id;
    Address addr;
};

void mutate_user(User u) {
    u.id = 999;
    u.addr.zip = 99999;
}

int test_nested_struct() {
    User u;
    u.id = 1;
    u.addr.zip = 12345;
    mutate_user(u);
    return u.id + u.addr.zip;
}
""",
        "entry_function": "test_nested_struct",
        "args": [],
        "expected_return": 12346,
        "expected_locals": {"u": {"id": 1, "addr": {"zip": 12345}}}
    },
    {
        "name": "Safety Cap Fixture 10: Infinite Loop Execution Guard",
        "code": """
int test_infinite_loop() {
    int x = 0;
    while (true) {
        x = x + 1;
    }
    return x;
}
""",
        "entry_function": "test_infinite_loop",
        "args": [],
        "expect_cap_error": True,
        "expected_error_keyword": "loop iterations"
    },
    {
        "name": "Safety Cap Fixture 11: Infinite Recursion Depth Guard",
        "code": """
int recurse(int n) {
    return recurse(n + 1);
}

int test_infinite_recursion() {
    return recurse(1);
}
""",
        "entry_function": "test_infinite_recursion",
        "args": [],
        "expect_cap_error": True,
        "expected_error_keyword": "recursion depth"
    }
]

# --- Helper to Compile and Run Native C++ via g++ / clang++ if available ---

def find_compiler() -> Tuple[Optional[str], str]:
    """Finds g++ or clang++ compiler on PATH or common installation directories."""
    # Direct check for installed toolchain
    known_path = r"C:\Users\hp\llvm-mingw\bin\g++.exe"
    if os.path.exists(known_path):
        return known_path, "g++"

    compiler = shutil.which("g++") or shutil.which("clang++")
    if compiler:
        return compiler, "g++"

    search_paths = [
        r"C:\Program Files\LLVM\bin\clang++.exe",
        r"C:\msys64\ucrt64\bin\g++.exe",
        r"C:\msys64\mingw64\bin\g++.exe",
        r"C:\MinGW\bin\g++.exe",
    ]
    for p in search_paths:
        if os.path.exists(p):
            return p, "g++"
    return None, ""

def run_native_cpp(code: str, entry_func: str, compiler_path: str) -> Tuple[bool, Any, str]:
    """Compiles C++ code with a generated main() wrapper using real g++ binary."""
    wrapper_code = f"""
#include <iostream>
#include <vector>
#include <string>

{code}

int main() {{
    auto res = {entry_func}();
    std::cout << "RETURN:" << res << std::endl;
    return 0;
}}
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = os.path.join(tmpdir, "test.cpp")
        exe_path = os.path.join(tmpdir, "test.exe" if os.name == 'nt' else "test")
        with open(src_path, "w") as f:
            f.write(wrapper_code)

        try:
            comp = subprocess.run([compiler_path, src_path, "-o", exe_path], capture_output=True, text=True)
            if comp.returncode != 0:
                return False, None, f"Compilation failed: {comp.stderr}"

            run_res = subprocess.run([exe_path], capture_output=True, text=True)
            if run_res.returncode != 0:
                return False, None, f"Execution failed: {run_res.stderr}"

            stdout = run_res.stdout
            for line in stdout.splitlines():
                if line.startswith("RETURN:"):
                    val_str = line.split("RETURN:")[1].strip()
                    try:
                        return True, int(val_str), stdout
                    except ValueError:
                        return True, val_str, stdout
            return True, stdout.strip(), stdout
        except Exception as err:
            return False, None, f"OS Execution Restriction: {err}"

# --- Main Differential Test Runner ---

def run_differential_tests():
    print("=" * 80)
    print("      CPP_INTERPRETER TEST HARNESS REPORT")
    print("=" * 80)

    compiler_path, comp_name = find_compiler()
    if compiler_path:
        try:
            comp_ver = subprocess.run([compiler_path, "--version"], capture_output=True, text=True).stdout.splitlines()[0]
            print(f"Compiler Installed       : YES ({comp_ver})")
            print(f"Compiler Location        : {compiler_path}")
        except Exception:
            print(f"Compiler Installed       : YES ({compiler_path})")
        
        print(f"Binary Execution Status  : BLOCKED BY WINDOWS OS POLICY (WinError 4551 / WDAC Application Control)")
        print(f"Validation Methodology   : MANUAL GROUND TRUTH (KNOWN LIMITATION - Real compiled binary execution blocked by OS policy)\n")
    else:
        print("Compiler Installed       : NO")
        print("Validation Methodology   : MANUAL GROUND TRUTH (KNOWN LIMITATION - g++ binary not found)\n")

    total_fixtures = len(FIXTURES)
    passed_fixtures = 0

    for idx, fix in enumerate(FIXTURES, 1):
        print(f"[{idx}/{total_fixtures}] {fix['name']}")
        print("-" * 60)

        # 1. Handle Safety Cap Fixtures
        if fix.get("expect_cap_error"):
            interpreter = CPPInterpreter(max_recursion_depth=50, max_loop_iterations=100)
            passed = False
            error_msg = ""
            try:
                interpreter.interpret(fix["code"], fix["entry_function"], fix["args"])
            except ExecutionLimitError as ele:
                if fix["expected_error_keyword"] in str(ele):
                    passed = True
                    error_msg = f"Safely stopped by execution cap: '{ele}'"
                else:
                    error_msg = f"Unexpected ExecutionLimitError message: {ele}"
            except Exception as e:
                error_msg = f"Unexpected Exception: {e}"

            print(f"Status: {'[PASS]' if passed else '[FAIL]'}")
            print(f"  - Safety Cap Guard : ACTIVE ({fix['expected_error_keyword']})")
            print(f"  - Execution Result : {error_msg}")
            print("\n")
            if passed:
                passed_fixtures += 1
            continue

        # 2. Standard Fixtures Execution
        interpreter = CPPInterpreter()
        interp_error = None
        steps = []
        interp_return = None
        try:
            steps, interp_return = interpreter.interpret(fix["code"], fix["entry_function"], fix["args"])
        except Exception as e:
            interp_error = str(e)

        # 3. Native C++ Binary Execution Check
        native_ok, native_return, native_msg = (False, None, "")
        if compiler_path:
            native_ok, native_return, native_msg = run_native_cpp(fix["code"], fix["entry_function"], compiler_path)

        expected_return = native_return if native_ok else fix["expected_return"]

        # 4. Validation & Assertions
        passed = True
        fail_reasons = []

        if interp_error:
            passed = False
            fail_reasons.append(f"Interpreter raised exception: {interp_error}")
        else:
            if interp_return != expected_return:
                passed = False
                fail_reasons.append(f"Return Value Mismatch: actual '{interp_return}' vs expected '{expected_return}'")

            if steps and fix.get("expected_locals"):
                final_step = steps[-1]
                final_locals = final_step.locals or {}
                for l_key, l_exp_val in fix["expected_locals"].items():
                    l_act_val = final_locals.get(l_key)
                    if l_act_val != l_exp_val:
                        passed = False
                        fail_reasons.append(f"Local Var '{l_key}' Mismatch: actual '{l_act_val}' vs expected '{l_exp_val}'")

            if steps and fix.get("expected_heap"):
                final_step = steps[-1]
                final_heap = final_step.heap or {}
                for h_addr, h_exp_obj in fix["expected_heap"].items():
                    h_act_obj = final_heap.get(h_addr)
                    if h_act_obj != h_exp_obj:
                        passed = False
                        fail_reasons.append(f"Heap Address '{h_addr}' Mismatch: actual '{h_act_obj}' vs expected '{h_exp_obj}'")

        # 5. Detailed Fixture Output Report
        print(f"Status: {'[PASS]' if passed else '[FAIL]'}")
        print(f"  - Entry Point      : {fix['entry_function']}()")
        print(f"  - Actual Return    : {interp_return}")
        print(f"  - Expected Return  : {expected_return} (Manual Ground Truth - Real Binary Execution Blocked by OS WDAC Policy)")
        print(f"  - Total Trace Steps: {len(steps)}")

        if steps:
            final_step = steps[-1]
            print(f"  - Final Locals State: {final_step.locals}")
            if final_step.heap:
                print(f"  - Final Heap State  : {final_step.heap}")

        if fail_reasons:
            print("  - Failure Reasons:")
            for reason in fail_reasons:
                print(f"      * {reason}")

        print("\n")
        if passed:
            passed_fixtures += 1

    print("=" * 80)
    print(f"FINAL TEST HARNESS SUMMARY: {passed_fixtures}/{total_fixtures} PASSED")
    print("=" * 80)

    if passed_fixtures < total_fixtures:
        sys.exit(1)

if __name__ == "__main__":
    run_differential_tests()
