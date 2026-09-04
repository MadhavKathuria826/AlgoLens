"""
AlgoLens Native Compilation & Execution Pipeline (Milestone 3 Prototype)
Coordinates:
1. Source-level AST instrumentation via CPPInstrumentor
2. Isolated temporary workspace compilation via host C++ compiler (Clang++ preferred)
3. Direct native process execution with timeout and output stream demultiplexing
4. Parsing and validation of native JSON Lines stream into AlgoLensEvent models
"""

import os
import sys
import time
import shutil
import tempfile
import subprocess
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

# Ensure backend root is on sys.path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from event_models import AlgoLensEvent
from cpp_instrumentor import CPPInstrumentor, UnsupportedConstructError


class NativeExecutionResult(BaseModel):
    success: bool
    events: List[AlgoLensEvent] = Field(default_factory=list)
    user_stdout: str = ""
    compiler_diagnostics: str = ""
    runtime_stderr: str = ""
    exit_code: int = 0
    compiler_name: str = ""
    compiler_version: str = ""
    compile_time_ms: float = 0.0
    execution_time_ms: float = 0.0
    total_time_ms: float = 0.0
    instrumented_code: Optional[str] = None
    error_message: Optional[str] = None


class NativeCompilationPipeline:
    """
    Manages native C++ compilation, execution, and event capture.
    """

    EVENT_PREFIX = "[ALGOLENS_EVENT] "

    def __init__(self, compiler_override: Optional[str] = None):
        self.instrumentor = CPPInstrumentor()
        self.compiler_path, self.compiler_name, self.compiler_version = self._detect_compiler(compiler_override)
        self.runtime_header_dir = os.path.join(BACKEND_DIR, "native_runtime")

    def _detect_compiler(self, override: Optional[str] = None) -> Tuple[str, str, str]:
        """Detects host C++ compiler (Clang++ preferred, falling back to g++)."""
        candidates = [override] if override else ["clang++", "g++", "clang"]
        for c in candidates:
            if not c:
                continue
            path = shutil.which(c)
            if path:
                try:
                    res = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5)
                    version_str = res.stdout.splitlines()[0] if res.stdout else "unknown"
                    return path, c, version_str
                except Exception:
                    pass
        raise RuntimeError("No compatible native C++ compiler found (clang++ or g++ required in PATH).")

    def compile_and_run(
        self,
        source_code: str,
        entry_func: str = "main",
        args: List[Any] = None,
        timeout_sec: float = 5.0,
        max_events: int = 50000
    ) -> NativeExecutionResult:
        """
        Full native pipeline: instrument -> compile -> execute -> parse events.
        """
        t_total_start = time.perf_counter()

        # Step 1: Instrument Source Code
        try:
            instrumented = self.instrumentor.instrument(source_code, entry_func=entry_func, args=args)
        except UnsupportedConstructError as e:
            return NativeExecutionResult(
                success=False,
                error_message=str(e),
                compiler_name=self.compiler_name,
                compiler_version=self.compiler_version
            )
        except SyntaxError as e:
            return NativeExecutionResult(
                success=False,
                error_message=f"Syntax Error during AST analysis: {e}",
                compiler_name=self.compiler_name,
                compiler_version=self.compiler_version
            )
        except Exception as e:
            return NativeExecutionResult(
                success=False,
                error_message=f"Instrumentation failed: {e}",
                compiler_name=self.compiler_name,
                compiler_version=self.compiler_version
            )

        # Step 2: Isolated Compilation in Temporary Directory
        temp_dir = tempfile.mkdtemp(prefix="algolens_native_")
        src_path = os.path.join(temp_dir, "app.cpp")
        exe_path = os.path.join(temp_dir, "app.exe" if sys.platform == "win32" else "app")

        try:
            with open(src_path, "w", encoding="utf-8") as f:
                f.write(instrumented)

            compile_cmd = [
                self.compiler_path,
                "-std=c++17",
                "-O0",
                "-g",
                f"-I{self.runtime_header_dir}",
                src_path,
                "-o",
                exe_path
            ]

            t_compile_start = time.perf_counter()
            compile_res = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=15)
            compile_ms = (time.perf_counter() - t_compile_start) * 1000.0

            if compile_res.returncode != 0:
                return NativeExecutionResult(
                    success=False,
                    exit_code=compile_res.returncode,
                    compiler_diagnostics=compile_res.stderr,
                    error_message=f"Native compilation failed with exit code {compile_res.returncode}",
                    compiler_name=self.compiler_name,
                    compiler_version=self.compiler_version,
                    compile_time_ms=compile_ms,
                    instrumented_code=instrumented
                )

            # Step 3: Native Process Execution
            t_exec_start = time.perf_counter()
            try:
                run_res = subprocess.run(
                    [exe_path],
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec
                )
                exec_ms = (time.perf_counter() - t_exec_start) * 1000.0
            except subprocess.TimeoutExpired:
                return NativeExecutionResult(
                    success=False,
                    error_message=f"Execution timed out after {timeout_sec}s",
                    compiler_name=self.compiler_name,
                    compiler_version=self.compiler_version,
                    compile_time_ms=compile_ms,
                    instrumented_code=instrumented
                )

            # Step 4: Demultiplex Event Stream and User Stdout
            events: List[AlgoLensEvent] = []
            user_stdout_lines = []

            for line in run_res.stdout.splitlines():
                if line.startswith(self.EVENT_PREFIX):
                    json_str = line[len(self.EVENT_PREFIX):].strip()
                    try:
                        import json
                        ev_dict = json.loads(json_str)
                        event = AlgoLensEvent(**ev_dict)
                        events.append(event)
                        if len(events) >= max_events:
                            return NativeExecutionResult(
                                success=False,
                                events=events,
                                error_message=f"Event budget exhausted (maximum {max_events} events exceeded)",
                                compiler_name=self.compiler_name,
                                compiler_version=self.compiler_version,
                                compile_time_ms=compile_ms,
                                execution_time_ms=exec_ms
                            )
                    except Exception as pe:
                        return NativeExecutionResult(
                            success=False,
                            error_message=f"Failed to parse native event JSON: {pe}\nPayload: {json_str}",
                            compiler_name=self.compiler_name,
                            compiler_version=self.compiler_version,
                            compile_time_ms=compile_ms,
                            execution_time_ms=exec_ms
                        )
                else:
                    user_stdout_lines.append(line)

            total_ms = (time.perf_counter() - t_total_start) * 1000.0

            return NativeExecutionResult(
                success=(run_res.returncode == 0),
                events=events,
                user_stdout="\n".join(user_stdout_lines),
                runtime_stderr=run_res.stderr,
                exit_code=run_res.returncode,
                compiler_name=self.compiler_name,
                compiler_version=self.compiler_version,
                compile_time_ms=compile_ms,
                execution_time_ms=exec_ms,
                total_time_ms=total_ms,
                instrumented_code=instrumented,
                error_message=None if run_res.returncode == 0 else f"Runtime process exited with code {run_res.returncode}"
            )

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
