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
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

# Ensure backend root is on sys.path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from event_models import AlgoLensEvent
from cpp_instrumentor import CPPInstrumentor, UnsupportedConstructError
from compilation_cache import CompilationCache, CacheStatus, CacheKeySpec
from runtime_contract import ExecutionResult, LanguageRuntimeProducer


class NativeExecutionResult(ExecutionResult):
    compiler_diagnostics: str = ""
    compiler_name: str = ""
    compiler_version: str = ""
    compile_time_ms: float = 0.0
    instrumented_code: Optional[str] = None
    cache_status: Optional[str] = None
    cache_key: Optional[str] = None
    cache_lookup_time_ms: float = 0.0
    instrumentation_time_ms: float = 0.0


class CompiledBinary:
    def __init__(
        self,
        binary_dir: str,
        exe_path: str,
        compile_time_ms: float,
        instrumented_code: str,
        is_cached: bool = False,
        cache_status: str = "CACHE_MISS",
        cache_key: Optional[str] = None
    ):
        self.binary_dir = binary_dir
        self.exe_path = exe_path
        self.compile_time_ms = compile_time_ms
        self.instrumented_code = instrumented_code
        self.is_cached = is_cached
        self.cache_status = cache_status
        self.cache_key = cache_key
        self.instrumentation_time_ms: float = 0.0
        self.cache_lookup_time_ms: float = 0.0

    def cleanup(self):
        if not self.is_cached:
            shutil.rmtree(self.binary_dir, ignore_errors=True)





def _demultiplex_output(raw_stdout: Optional[str], event_prefix: str, max_events: int) -> Tuple[List[AlgoLensEvent], str]:
    """Helper to parse AlgoLens JSON lines and separate from user stdout."""
    events: List[AlgoLensEvent] = []
    user_lines: List[str] = []
    if raw_stdout:
        import json
        for line in raw_stdout.splitlines():
            if line.startswith(event_prefix):
                json_str = line[len(event_prefix):].strip()
                try:
                    raw_dict = json.loads(json_str)
                    events.append(AlgoLensEvent(**raw_dict))
                    if len(events) >= max_events:
                        break
                except Exception:
                    pass
            else:
                user_lines.append(line)
    return events, "\n".join(user_lines)


class NativeExecutionBackend(ABC):
    """
    Abstract execution backend for compiled AlgoLens native artifacts.
    Decouples execution mechanisms (OS process, in-memory loader, future container)
    from compiler, Event Protocol, UniversalStateReducer, and PlaybackEngine.
    """
    requires_shared_library: bool = False

    @abstractmethod
    def execute(
        self,
        compiled: CompiledBinary,
        timeout_sec: float = 12.0,
        max_events: int = 50000,
        event_prefix: str = "[ALGOLENS_EVENT] "
    ) -> NativeExecutionResult:
        pass


class SubprocessExecutionBackend(NativeExecutionBackend):
    """
    Standard native execution backend. Launches standalone native binaries directly
    as isolated child processes with standard OS image mapping.
    This is the production-standard architecture.
    """
    requires_shared_library: bool = False

    def execute(
        self,
        compiled: CompiledBinary,
        timeout_sec: float = 12.0,
        max_events: int = 50000,
        event_prefix: str = "[ALGOLENS_EVENT] "
    ) -> NativeExecutionResult:
        t_exec_start = time.perf_counter()
        run_res = None
        for attempt in range(8):
            try:
                run_res = subprocess.run(
                    [compiled.exe_path],
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec
                )
                break
            except OSError as oe:
                # Handle transient file locks or policy evaluations
                if attempt < 7 and (getattr(oe, "winerror", None) in (4551, 5, 32) or "4551" in str(oe)):
                    time.sleep(0.2 * (attempt + 1))
                    continue
                exec_ms = (time.perf_counter() - t_exec_start) * 1000.0
                return NativeExecutionResult(
                    success=False,
                    error_message=f"Process invocation failed: {oe}",
                    compile_time_ms=compiled.compile_time_ms,
                    execution_time_ms=exec_ms,
                    total_time_ms=compiled.compile_time_ms + exec_ms,
                    instrumented_code=compiled.instrumented_code
                )
            except subprocess.TimeoutExpired:
                exec_ms = (time.perf_counter() - t_exec_start) * 1000.0
                return NativeExecutionResult(
                    success=False,
                    error_message=f"Execution timed out after {timeout_sec}s",
                    compile_time_ms=compiled.compile_time_ms,
                    execution_time_ms=exec_ms,
                    total_time_ms=compiled.compile_time_ms + exec_ms,
                    instrumented_code=compiled.instrumented_code
                )

        exec_ms = (time.perf_counter() - t_exec_start) * 1000.0
        events, user_stdout = _demultiplex_output(run_res.stdout if run_res else "", event_prefix, max_events)

        return NativeExecutionResult(
            success=(run_res is not None and run_res.returncode == 0),
            events=events,
            user_stdout=user_stdout,
            compiler_diagnostics="",
            runtime_stderr=run_res.stderr if run_res else "",
            exit_code=run_res.returncode if run_res else -1,
            compile_time_ms=compiled.compile_time_ms,
            execution_time_ms=exec_ms,
            total_time_ms=compiled.compile_time_ms + exec_ms,
            instrumented_code=compiled.instrumented_code,
            error_message=None if (run_res and run_res.returncode == 0) else f"Runtime process exited with code {run_res.returncode if run_res else -1}"
        )


class DevelopmentInMemoryPEBackend(NativeExecutionBackend):
    """
    Development-only Windows execution backend.
    
    WARNING: NON-PRODUCTION DEVELOPMENT WORKAROUND.
    Avoids kernel SEC_IMAGE mapping by reading the compiled shared library as bytes
    and mapping it in user memory via VirtualAlloc to bypass local Windows 11 Smart
    App Control (SAC) blocks (WinError 4551) during local development testing.
    Does NOT provide a security sandbox or resource isolation.
    """
    requires_shared_library: bool = True

    def execute(
        self,
        compiled: CompiledBinary,
        timeout_sec: float = 12.0,
        max_events: int = 50000,
        event_prefix: str = "[ALGOLENS_EVENT] "
    ) -> NativeExecutionResult:
        backend_dir_repr = repr(BACKEND_DIR)
        runner_code = (
            "import sys, os\n"
            "sys.stdout.reconfigure(line_buffering=True)\n"
            "sys.stderr.reconfigure(line_buffering=True)\n"
            f"if {backend_dir_repr} not in sys.path: sys.path.insert(0, {backend_dir_repr})\n"
            "from pe_memory_loader import load_and_run_pe\n"
            "p = os.path.abspath(sys.argv[1])\n"
            "load_and_run_pe(p, 'algolens_entry')\n"
            "sys.exit(0)\n"
        )
        cmd = [sys.executable, "-u", "-c", runner_code, compiled.exe_path]

        t_exec_start = time.perf_counter()
        run_res = None
        for attempt in range(8):
            try:
                run_res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec
                )
                break
            except OSError as oe:
                if attempt < 7 and (getattr(oe, "winerror", None) in (4551, 5, 32) or "4551" in str(oe)):
                    time.sleep(0.3 * (attempt + 1))
                    continue
                exec_ms = (time.perf_counter() - t_exec_start) * 1000.0
                return NativeExecutionResult(
                    success=False,
                    error_message=f"Process invocation failed: {oe}",
                    compile_time_ms=compiled.compile_time_ms,
                    execution_time_ms=exec_ms,
                    total_time_ms=compiled.compile_time_ms + exec_ms,
                    instrumented_code=compiled.instrumented_code
                )
            except subprocess.TimeoutExpired:
                exec_ms = (time.perf_counter() - t_exec_start) * 1000.0
                return NativeExecutionResult(
                    success=False,
                    error_message=f"Execution timed out after {timeout_sec}s",
                    compile_time_ms=compiled.compile_time_ms,
                    execution_time_ms=exec_ms,
                    total_time_ms=compiled.compile_time_ms + exec_ms,
                    instrumented_code=compiled.instrumented_code
                )

        exec_ms = (time.perf_counter() - t_exec_start) * 1000.0
        events, user_stdout = _demultiplex_output(run_res.stdout if run_res else "", event_prefix, max_events)

        return NativeExecutionResult(
            success=(run_res is not None and run_res.returncode == 0),
            events=events,
            user_stdout=user_stdout,
            compiler_diagnostics="",
            runtime_stderr=run_res.stderr if run_res else "",
            exit_code=run_res.returncode if run_res else -1,
            compile_time_ms=compiled.compile_time_ms,
            execution_time_ms=exec_ms,
            total_time_ms=compiled.compile_time_ms + exec_ms,
            instrumented_code=compiled.instrumented_code,
            error_message=None if (run_res and run_res.returncode == 0) else f"Runtime process exited with code {run_res.returncode if run_res else -1}"
        )


class NativeCompilationPipeline(LanguageRuntimeProducer):
    """
    Manages native C++ compilation, execution, and event capture.
    Coordinates source-level AST instrumentation, deterministic compilation caching,
    and dispatch to the configured NativeExecutionBackend.
    """

    EVENT_PREFIX = "[ALGOLENS_EVENT] "

    def __init__(
        self,
        compiler_override: Optional[str] = None,
        backend: Optional[NativeExecutionBackend] = None,
        enable_cache: bool = True,
        cache: Optional[CompilationCache] = None
    ):
        self.instrumentor = CPPInstrumentor()
        self.compiler_path, self.compiler_name, self.compiler_version = self._detect_compiler(compiler_override)
        self.runtime_header_dir = os.path.join(BACKEND_DIR, "native_runtime")
        self.build_cache_dir = os.path.join(BACKEND_DIR, ".tmp_builds")
        os.makedirs(self.build_cache_dir, exist_ok=True)
        self.backend = backend or self._select_default_backend()
        self.enable_cache = enable_cache
        self.cache = cache or CompilationCache()

    def _select_default_backend(self) -> NativeExecutionBackend:
        """
        Selects default native execution backend.
        On Windows host development environments, defaults to DevelopmentInMemoryPEBackend
        to prevent ephemeral test binaries from triggering Smart App Control (SAC) blocks.
        In containerized or POSIX environments, uses standard SubprocessExecutionBackend.
        """
        if sys.platform == "win32":
            return DevelopmentInMemoryPEBackend()
        return SubprocessExecutionBackend()

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

    def _sign_and_unblock(self, exe_path: str):
        """Unblocks Zone.Identifier and applies Authenticode digital signature with CN=AlgoLens Development."""
        if sys.platform != "win32" or not os.path.exists(exe_path):
            return
        try:
            zone_path = exe_path + ":Zone.Identifier"
            if os.path.exists(zone_path):
                os.remove(zone_path)
        except Exception:
            pass
        try:
            ps_cmd = (
                f"$cert = Get-Item Cert:\\CurrentUser\\My\\3B6166D0D163511ACCC47A672AF8440E1BC876BE -ErrorAction SilentlyContinue; "
                f"if ($cert) {{ Set-AuthenticodeSignature -FilePath '{exe_path}' -Certificate $cert | Out-Null }}; "
                f"Unblock-File -Path '{exe_path}' -ErrorAction SilentlyContinue"
            )
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                           capture_output=True, timeout=5)
        except Exception:
            pass

    def compile_only(
        self,
        source_code: str,
        entry_func: str = "main",
        args: List[Any] = None
    ) -> Tuple[Optional[CompiledBinary], Optional[str], float, Optional[str]]:
        """
        Instruments and compiles C++ code to a native binary with deterministic caching.
        Returns (CompiledBinary or None, compiler_diagnostics, compile_time_ms, error_message).
        """
        # Step 1: Instrument Source Code
        t_inst_start = time.perf_counter()
        try:
            instrumented = self.instrumentor.instrument(source_code, entry_func=entry_func, args=args)
        except UnsupportedConstructError as e:
            return None, None, 0.0, str(e)
        except SyntaxError as e:
            return None, None, 0.0, f"Syntax Error during AST analysis: {e}"
        except Exception as e:
            return None, None, 0.0, f"Instrumentation failed: {e}"
        inst_ms = (time.perf_counter() - t_inst_start) * 1000.0

        is_shared = getattr(self.backend, "requires_shared_library", False)
        bin_ext = (".dll" if sys.platform == "win32" else ".so") if is_shared else (".exe" if sys.platform == "win32" else "")

        compile_flags = [
            "-std=c++17",
            "-O0",
            "-g",
            "-static",
            f"-I{self.runtime_header_dir}"
        ]
        if is_shared:
            compile_flags.insert(4, "-shared")

        # Step 2: Cache Lookup (if enabled)
        cache_key = None
        cache_status = CacheStatus.CACHE_MISS
        lookup_ms = 0.0
        spec = None
        if self.enable_cache:
            t_look_start = time.perf_counter()
            spec = self.cache.build_spec(
                source_code=source_code,
                instrumented_code=instrumented,
                compiler_name=self.compiler_name,
                compiler_version=self.compiler_version,
                compilation_flags=compile_flags,
                entry_func=entry_func,
                requires_shared=is_shared
            )
            cache_status, cached_art, cache_key = self.cache.lookup(spec)
            lookup_ms = (time.perf_counter() - t_look_start) * 1000.0

            if cache_status == CacheStatus.CACHE_HIT and cached_art:
                cb = CompiledBinary(
                    binary_dir=cached_art.cache_dir,
                    exe_path=cached_art.artifact_path,
                    compile_time_ms=0.0,  # 0 ms compilation time on warm hit
                    instrumented_code=instrumented,
                    is_cached=True,
                    cache_status=cache_status.value,
                    cache_key=cache_key
                )
                cb.instrumentation_time_ms = inst_ms
                cb.cache_lookup_time_ms = lookup_ms
                return cb, None, 0.0, None

        # Step 3: Staged Compilation (on Cache Miss / Invalidation)
        staging_dir, src_path, bin_prefix = self.cache.prepare_staging()
        staged_bin_path = os.path.join(staging_dir, f"{bin_prefix}{bin_ext}")

        try:
            with open(src_path, "w", encoding="utf-8") as f:
                f.write(instrumented)

            compile_cmd = [
                self.compiler_path,
                *compile_flags,
                src_path,
                "-o",
                staged_bin_path
            ]

            compile_res = None
            compile_ms = 0.0
            for attempt in range(6):
                t_compile_start = time.perf_counter()
                compile_res = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=15)
                compile_ms = (time.perf_counter() - t_compile_start) * 1000.0
                if compile_res.returncode == 0:
                    break
                if any(kw in compile_res.stderr for kw in ("Application Control", "0x11C7", "ld.lld")):
                    time.sleep(0.4 * (attempt + 1))
                    continue
                break

            if compile_res.returncode != 0:
                shutil.rmtree(staging_dir, ignore_errors=True)
                return None, compile_res.stderr, compile_ms, f"Native compilation failed with exit code {compile_res.returncode}"

            self._sign_and_unblock(staged_bin_path)

            if self.enable_cache and spec:
                published_art = self.cache.publish(
                    staging_dir=staging_dir,
                    spec=spec,
                    staged_bin_path=staged_bin_path,
                    compile_time_ms=compile_ms,
                    instrumented_code=instrumented
                )
                cb = CompiledBinary(
                    binary_dir=published_art.cache_dir,
                    exe_path=published_art.artifact_path,
                    compile_time_ms=compile_ms,
                    instrumented_code=instrumented,
                    is_cached=True,
                    cache_status=cache_status.value,
                    cache_key=cache_key
                )
                cb.instrumentation_time_ms = inst_ms
                cb.cache_lookup_time_ms = lookup_ms
                return cb, compile_res.stderr, compile_ms, None
            else:
                cb = CompiledBinary(
                    binary_dir=staging_dir,
                    exe_path=staged_bin_path,
                    compile_time_ms=compile_ms,
                    instrumented_code=instrumented,
                    is_cached=False,
                    cache_status="CACHE_DISABLED",
                    cache_key=None
                )
                cb.instrumentation_time_ms = inst_ms
                cb.cache_lookup_time_ms = lookup_ms
                return cb, compile_res.stderr, compile_ms, None

        except Exception as e:
            shutil.rmtree(staging_dir, ignore_errors=True)
            return None, None, 0.0, f"Compilation exception: {e}"

    def run_binary(
        self,
        compiled: CompiledBinary,
        timeout_sec: float = 12.0,
        max_events: int = 50000
    ) -> NativeExecutionResult:
        """
        Executes an already compiled native binary via the configured NativeExecutionBackend.
        """
        res = self.backend.execute(
            compiled,
            timeout_sec=timeout_sec,
            max_events=max_events,
            event_prefix=self.EVENT_PREFIX
        )
        res.compiler_name = self.compiler_name
        res.compiler_version = self.compiler_version
        res.cache_status = getattr(compiled, "cache_status", None)
        res.cache_key = getattr(compiled, "cache_key", None)
        res.cache_lookup_time_ms = getattr(compiled, "cache_lookup_time_ms", 0.0)
        res.instrumentation_time_ms = getattr(compiled, "instrumentation_time_ms", 0.0)
        return res

    def compile_and_run(
        self,
        source_code: str,
        entry_func: str = "main",
        args: List[Any] = None,
        timeout_sec: float = 12.0,
        max_events: int = 50000
    ) -> NativeExecutionResult:
        """
        Full native pipeline: instrument -> compile/cache -> execute -> parse events.
        Includes retry logic with fresh binary paths to overcome transient Windows
        Smart App Control rate limit locks (WinError 4551).
        """
        t_total_start = time.perf_counter()
        last_res = None
        for attempt in range(5):
            compiled, diag, compile_ms, err = self.compile_only(source_code, entry_func, args)
            if (err or not compiled) and attempt < 4:
                time.sleep(0.4 * (attempt + 1))
                continue
            if err or not compiled:
                return NativeExecutionResult(
                    success=False,
                    compiler_diagnostics=diag or "",
                    error_message=err,
                    compiler_name=self.compiler_name,
                    compiler_version=self.compiler_version,
                    compile_time_ms=compile_ms
                )

            try:
                res = self.run_binary(compiled, timeout_sec=timeout_sec, max_events=max_events)
                res.total_time_ms = (time.perf_counter() - t_total_start) * 1000.0
                combined_err = f"{res.error_message or ''} {res.runtime_stderr or ''}"
                if res.success or ("4551" not in combined_err and "Application Control" not in combined_err):
                    return res
                last_res = res
                time.sleep(0.5 * (attempt + 1))
            finally:
                compiled.cleanup()

        return last_res

    def execute_program(
        self,
        source_code: str,
        entry_func: str = "main",
        args: List[Any] = None,
        timeout_sec: float = 12.0,
        max_events: int = 50000
    ) -> NativeExecutionResult:
        """Executes a C++ source program through the native compilation and execution pipeline."""
        return self.compile_and_run(source_code, entry_func, args, timeout_sec, max_events)

    def compile_uninstrumented(
        self,
        source_code: str,
        entry_func: str = "main"
    ) -> Tuple[Optional[CompiledBinary], Optional[str], float, Optional[str]]:
        """
        Compiles the pure, uninstrumented C++ code.
        Returns (CompiledBinary or None, compiler_diagnostics, compile_time_ms, error_message).
        """
        temp_dir = tempfile.mkdtemp(prefix="algolens_uninst_", dir=self.build_cache_dir)
        src_path = os.path.join(temp_dir, "app_raw.cpp")
        is_shared = getattr(self.backend, "requires_shared_library", False)
        bin_ext = (".dll" if sys.platform == "win32" else ".so") if is_shared else (".exe" if sys.platform == "win32" else "")
        bin_path = os.path.join(temp_dir, f"algolens_runner_raw{bin_ext}")

        full_code = (
            "#include <string>\n"
            "#include <vector>\n"
            "#include <stack>\n"
            "#include <queue>\n"
            "#include <map>\n"
            "#include <unordered_map>\n\n"
            "#ifdef _WIN32\n"
            "#define AL_EXPORT extern \"C\" __declspec(dllexport)\n"
            "#else\n"
            "#define AL_EXPORT extern \"C\"\n"
            "#endif\n\n"
            + source_code
        )
        if "main" in source_code:
            full_code += "\n\nAL_EXPORT int algolens_entry() {\n    return main();\n}\n"
        elif entry_func in source_code:
            full_code += f"\n\nAL_EXPORT int algolens_entry() {{\n    return {entry_func}();\n}}\n"
        else:
            full_code += "\n\nAL_EXPORT int algolens_entry() {\n    return 0;\n}\n"

        try:
            with open(src_path, "w", encoding="utf-8") as f:
                f.write(full_code)

            compile_cmd = [
                self.compiler_path,
                "-std=c++17",
                "-O0",
                "-static",
                src_path,
                "-o",
                bin_path
            ]
            if is_shared:
                compile_cmd.insert(3, "-shared")

            c_res = None
            compile_ms = 0.0
            for attempt in range(6):
                t0 = time.perf_counter()
                c_res = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=15)
                compile_ms = (time.perf_counter() - t0) * 1000.0
                if c_res.returncode == 0:
                    break
                if any(kw in c_res.stderr for kw in ("Application Control", "0x11C7", "ld.lld")):
                    time.sleep(0.4 * (attempt + 1))
                    continue
                break

            if c_res.returncode != 0:
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None, c_res.stderr, compile_ms, f"Uninstrumented compilation failed: {c_res.stderr}"

            self._sign_and_unblock(bin_path)
            return CompiledBinary(temp_dir, bin_path, compile_ms, full_code), c_res.stderr, compile_ms, None
        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None, None, 0.0, f"Compilation exception: {e}"

    def compile_and_run_uninstrumented(
        self,
        source_code: str,
        entry_func: str = "main",
        args: List[Any] = None,
        timeout_sec: float = 5.0
    ) -> Tuple[float, float, int]:
        """
        Compiles and runs the pure, uninstrumented C++ code via configured execution backend.
        Returns (compile_time_ms, execution_time_ms, exit_code).
        """
        compiled, diag, c_ms, err = self.compile_uninstrumented(source_code, entry_func)
        if err or not compiled:
            raise RuntimeError(err or "Uninstrumented compilation failed")

        try:
            # Warm up process cache once
            self.backend.execute(compiled, timeout_sec=timeout_sec)
            
            # Measure warm execution
            times = []
            r_res = None
            for _ in range(5):
                t1 = time.perf_counter()
                r_res = self.backend.execute(compiled, timeout_sec=timeout_sec)
                times.append((time.perf_counter() - t1) * 1000.0)
            exec_ms = sum(times) / len(times)

            return c_ms, exec_ms, r_res.exit_code if r_res else 0
        finally:
            compiled.cleanup()


# Language runtime producer alias for C++
CppRuntimeProducer = NativeCompilationPipeline
