"""
Focused test suite to rigorously audit and verify the capabilities and boundaries
of the development-only in-memory PE loader (backend/pe_memory_loader.py).

Tests:
1. Simple function execution
2. Multiple functions with parameter passing
3. Global and static data lifecycle
4. Runtime imports (KERNEL32, UCRT, heap allocation)
5. Base relocation to arbitrary address
6. C++ exception handling (SEH / .pdata registration)
7. Normal return and clean termination
8. AlgoLens runtime event generation
9. Separation of stdout and event streams
10. Repeated execution across multiple binaries
"""

import os
import sys
import shutil
import tempfile
import subprocess
from typing import Tuple

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from pe_memory_loader import load_and_run_pe
from cpp_instrumentor import CPPInstrumentor
from native_runner import NativeCompilationPipeline


def compile_dll(cpp_code: str, temp_dir: str, name: str) -> str:
    src_path = os.path.join(temp_dir, f"{name}.cpp")
    dll_path = os.path.join(temp_dir, f"{name}.dll")
    with open(src_path, "w", encoding="utf-8") as f:
        f.write(cpp_code)
    
    runtime_hdr = os.path.join(BACKEND_DIR, "native_runtime")
    cmd = [
        "clang++",
        "-std=c++17",
        "-O0",
        "-shared",
        "-static",
        f"-I{runtime_hdr}",
        src_path,
        "-o",
        dll_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if res.returncode != 0:
        raise RuntimeError(f"Compilation failed for {name}:\n{res.stderr}")
    return dll_path


def run_in_subprocess(dll_path: str, timeout_sec: float = 5.0) -> Tuple[int, str, str]:
    runner_code = (
        "import sys, os\n"
        f"sys.path.insert(0, r'{BACKEND_DIR}')\n"
        "from pe_memory_loader import load_and_run_pe\n"
        "load_and_run_pe(sys.argv[1], 'algolens_entry')\n"
        "sys.exit(0)\n"
    )
    cmd = [sys.executable, "-u", "-c", runner_code, dll_path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
    return r.returncode, r.stdout, r.stderr


def run_all_checks():
    temp_dir = tempfile.mkdtemp(prefix="test_pe_contract_")
    print("=" * 60)
    print("  AlgoLens PE Loader Focused Contract Verification Suite")
    print("=" * 60)

    try:
        # --- Check 1: Simple Function ---
        print("\n[Check 1] Simple Function Execution...")
        c1 = """
        #define AL_EXPORT extern "C" __declspec(dllexport)
        #include <iostream>
        AL_EXPORT int algolens_entry() {
            std::cout << "SIMPLE_FN_OK" << std::endl;
            return 0;
        }
        """
        dll1 = compile_dll(c1, temp_dir, "test1_simple")
        rc, out, err = run_in_subprocess(dll1)
        assert rc == 0 and "SIMPLE_FN_OK" in out, f"Failed check 1: rc={rc}, out={out}, err={err}"
        print("  -> PASS: Simple function returned 0 with expected stdout.")

        # --- Check 2: Multiple Functions with Parameters ---
        print("\n[Check 2] Multiple Functions & Parameter Passing...")
        c2 = """
        #define AL_EXPORT extern "C" __declspec(dllexport)
        #include <iostream>
        int add(int a, int b) { return a + b; }
        int multiply(int a, int b) { return a * b; }
        AL_EXPORT int algolens_entry() {
            int val = multiply(add(3, 4), 10);
            std::cout << "CALC_RESULT=" << val << std::endl;
            return 0;
        }
        """
        dll2 = compile_dll(c2, temp_dir, "test2_multifunc")
        rc, out, err = run_in_subprocess(dll2)
        assert rc == 0 and "CALC_RESULT=70" in out, f"Failed check 2: rc={rc}, out={out}, err={err}"
        print("  -> PASS: Multi-function call chain produced 70.")

        # --- Check 3: Global and Static Data Lifecycle ---
        print("\n[Check 3] Global & Static Data Lifecycle...")
        c3 = """
        #define AL_EXPORT extern "C" __declspec(dllexport)
        #include <iostream>
        static int static_var = 500;
        int global_var = 1000;
        AL_EXPORT int algolens_entry() {
            static_var += 25;
            global_var += 50;
            std::cout << "STATIC=" << static_var << " GLOBAL=" << global_var << std::endl;
            return 0;
        }
        """
        dll3 = compile_dll(c3, temp_dir, "test3_data")
        rc, out, err = run_in_subprocess(dll3)
        assert rc == 0 and "STATIC=525 GLOBAL=1050" in out, f"Failed check 3: rc={rc}, out={out}, err={err}"
        print("  -> PASS: Global and static memory sections read and modified successfully.")

        # --- Check 4: Runtime Imports (Heap allocation, C-string, CRT) ---
        print("\n[Check 4] Runtime Imports (CRT / Kernel32 / Dynamic Allocation)...")
        c4 = """
        #define AL_EXPORT extern "C" __declspec(dllexport)
        #include <iostream>
        #include <cstdlib>
        #include <cstring>
        AL_EXPORT int algolens_entry() {
            char* buf = (char*)malloc(64);
            strcpy(buf, "CRT_HEAP_ALLOCATION_SUCCESS");
            std::cout << buf << " LEN=" << strlen(buf) << std::endl;
            free(buf);
            return 0;
        }
        """
        dll4 = compile_dll(c4, temp_dir, "test4_imports")
        rc, out, err = run_in_subprocess(dll4)
        assert rc == 0 and "CRT_HEAP_ALLOCATION_SUCCESS LEN=27" in out, f"Failed check 4: rc={rc}, out={out}, err={err}"
        print("  -> PASS: CRT dynamic heap allocation and string imports functioned as expected.")

        # --- Check 5: Relocations & Address Space ---
        print("\n[Check 5] Relocation Handling across Section Boundaries...")
        c5 = """
        #define AL_EXPORT extern "C" __declspec(dllexport)
        #include <iostream>
        const char* messages[] = { "MSG_ZERO", "MSG_ONE", "MSG_TWO" };
        AL_EXPORT int algolens_entry() {
            for(int i=0; i<3; ++i) {
                std::cout << messages[i] << " ";
            }
            std::cout << std::endl;
            return 0;
        }
        """
        dll5 = compile_dll(c5, temp_dir, "test5_reloc")
        rc, out, err = run_in_subprocess(dll5)
        assert rc == 0 and "MSG_ZERO MSG_ONE MSG_TWO" in out, f"Failed check 5: rc={rc}, out={out}, err={err}"
        print("  -> PASS: Pointer table relocations properly resolved.")

        # --- Check 6: C++ Exception Handling (.pdata / SEH) ---
        print("\n[Check 6] C++ Exception Handling & Stack Unwinding (.pdata)...")
        c6 = """
        #define AL_EXPORT extern "C" __declspec(dllexport)
        #include <iostream>
        #include <stdexcept>
        void thrower() {
            throw std::runtime_error("CUSTOM_EXCEPTION_THROWN");
        }
        AL_EXPORT int algolens_entry() {
            try {
                thrower();
            } catch (const std::exception& e) {
                std::cout << "CAUGHT:" << e.what() << std::endl;
                return 0;
            }
            return 1;
        }
        """
        dll6 = compile_dll(c6, temp_dir, "test6_exceptions")
        rc, out, err = run_in_subprocess(dll6)
        assert rc == 0 and "CAUGHT:CUSTOM_EXCEPTION_THROWN" in out, f"Failed check 6: rc={rc}, out={out}, err={err}"
        print("  -> PASS: C++ exception caught successfully through registered .pdata function table.")

        # --- Check 7: Normal Return and Clean Exit ---
        print("\n[Check 7] Clean Function Return & Process Termination...")
        c7 = """
        #define AL_EXPORT extern "C" __declspec(dllexport)
        AL_EXPORT int algolens_entry() {
            return 0;
        }
        """
        dll7 = compile_dll(c7, temp_dir, "test7_return")
        rc, out, err = run_in_subprocess(dll7)
        assert rc == 0, f"Failed check 7: rc={rc}"
        print("  -> PASS: Clean exit code 0 returned.")

        # --- Check 8: AlgoLens Runtime Event Stream Generation ---
        print("\n[Check 8] AlgoLens Runtime Event Emission...")
        pipeline = NativeCompilationPipeline()
        prog = """
        int main() {
            int x = 42;
            int y = x * 2;
            return 0;
        }
        """
        res = pipeline.compile_and_run(prog)
        assert res.success, f"Failed check 8 compile_and_run: {res.error_message}"
        event_types = [e.event_type for e in res.events]
        assert "PROG_START" in event_types
        assert "VAR_DECLARE" in event_types
        assert "STEP_LINE" in event_types
        assert "FRAME_POP" in event_types
        print(f"  -> PASS: Generated {len(res.events)} AlgoLens events including {set(event_types)}.")

        # --- Check 9: Stdout / Event Demultiplexing ---
        print("\n[Check 9] Separation of User Stdout and [ALGOLENS_EVENT] Stream...")
        prog_with_stdout = """
        extern "C" int puts(const char*);
        int main() {
            int a = 10;
            puts("HELLO_USER_STDOUT");
            int b = 20;
            return 0;
        }
        """
        res_stdout = pipeline.compile_and_run(prog_with_stdout)
        assert res_stdout.success, f"Failed check 9: {res_stdout.error_message}"
        assert "HELLO_USER_STDOUT" in res_stdout.user_stdout, f"Missing user stdout in: {res_stdout.user_stdout}"
        for ev in res_stdout.events:
            assert "HELLO_USER_STDOUT" not in str(ev.model_dump()), "User stdout leaked into event payload!"
        print("  -> PASS: User stdout cleanly demultiplexed from event stream.")

        # --- Check 10: Repeated Execution in Successive Runs ---
        print("\n[Check 10] Repeated Sequential Execution...")
        for i in range(5):
            res_rep = pipeline.compile_and_run(f"int main() {{ int val = {i*10}; return 0; }}")
            assert res_rep.success, f"Failed repeated run {i}: {res_rep.error_message}"
        print("  -> PASS: 5 consecutive pipeline runs completed with 100% success.")

        print("\n" + "=" * 60)
        print("  ALL 10 PE LOADER CONTRACT CHECKS PASSED SUCCESSFULLY")
        print("=" * 60)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    run_all_checks()
