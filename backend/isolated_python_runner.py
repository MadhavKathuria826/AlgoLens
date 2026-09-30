"""
AlgoLens Isolated Python Runner (Milestone 9)
Provides sandboxed, isolated subprocess execution for PythonRuntimeProducer.

Enforces:
1. Process isolation: User code NEVER executes in the FastAPI/Uvicorn server process.
2. OS-level resource limits (RLIMIT_CPU, RLIMIT_AS, RLIMIT_NPROC, RLIMIT_NOFILE on Linux).
3. Strict execution timeout and subprocess lifecycle management (SIGTERM/SIGKILL on expiration).
4. Sanitized environment (scrubbed secrets and environment variables).
5. Network lockdown (socket creation blocked).
6. Clean stdout / stderr demultiplexing.
"""

import sys
import os
import json
import subprocess
import time
from typing import List, Dict, Any, Optional

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from event_models import AlgoLensEvent
from runtime_contract import ExecutionResult


def apply_linux_resource_limits(timeout_sec: float = 12.0):
    """Applies strict OS-level resource limits when running on Linux (e.g. Docker / Render)."""
    try:
        import resource

        # 1. CPU Time Limit (timeout + grace period)
        cpu_limit = max(1, int(timeout_sec + 2))
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit + 2))
        except (ValueError, OSError):
            pass

        # 2. Virtual Memory Ceiling (256 MB)
        mem_bytes = 256 * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        except (ValueError, OSError):
            pass

        # 3. Limit Process/Thread Creation (prevent fork bombs)
        try:
            resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
        except (ValueError, OSError):
            pass

        # 4. Restrict File Descriptors
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        except (ValueError, OSError):
            pass

    except ImportError:
        # Non-Linux host (e.g. Windows development)
        pass


def sanitize_worker_environment():
    """Scrubs sensitive environment variables and restricts network sockets."""
    # Retain only essential OS variables
    safe_keys = {"PATH", "SYSTEMROOT", "WINDIR", "PYTHONPATH", "LANG", "LC_ALL", "TMP", "TEMP"}
    current_keys = list(os.environ.keys())
    for k in current_keys:
        if k.upper() not in safe_keys:
            os.environ.pop(k, None)

    # Disable socket creation (block outbound network access)
    try:
        import socket
        socket.socket = None
        socket.create_connection = None
    except Exception:
        pass

    # Disable subprocess spawning (block child process creation and fork attempts)
    try:
        import subprocess
        subprocess.Popen = None
        subprocess.call = None
        subprocess.run = None
        subprocess.check_output = None
        subprocess.check_call = None
    except Exception:
        pass


def run_worker_process():
    """Subprocess entrypoint: reads JSON execution request from stdin and runs in isolation."""
    try:
        raw_input = sys.stdin.read()
        if not raw_input:
            sys.stderr.write("Empty payload received by isolated worker.\n")
            sys.exit(1)

        payload = json.loads(raw_input)
        source_code = payload.get("source_code", "")
        entry_func = payload.get("entry_func")
        args = payload.get("args")
        timeout_sec = payload.get("timeout_sec", 12.0)
        max_events = payload.get("max_events", 50000)
        max_recursion_depth = payload.get("max_recursion_depth", 1000)

        # Apply sandboxing
        apply_linux_resource_limits(timeout_sec)
        sanitize_worker_environment()

        # Import producer inside isolated subprocess
        from python_producer import PythonRuntimeProducer
        producer = PythonRuntimeProducer()

        # Execute in-process within this worker subprocess
        result = producer.execute_program(
            source_code=source_code,
            entry_func=entry_func,
            args=args,
            timeout_sec=timeout_sec,
            max_events=max_events,
            max_recursion_depth=max_recursion_depth,
            isolated=False  # Crucial: runs locally inside this worker process
        )

        # Serialize result to stdout
        output_json = json.dumps(result.model_dump())
        sys.stdout.write(output_json)
        sys.stdout.flush()
        sys.exit(0)

    except Exception as e:
        err_res = ExecutionResult(
            success=False,
            error_message=f"Isolated worker error: {str(e)}",
            diagnostics=str(e)
        )
        sys.stdout.write(json.dumps(err_res.model_dump()))
        sys.stdout.flush()
        sys.exit(0)


class IsolatedPythonRunner:
    """Supervisor that spawns and controls isolated Python execution subprocesses."""

    def __init__(self, python_executable: Optional[str] = None):
        self.python_executable = python_executable or sys.executable

    def execute(
        self,
        source_code: str,
        entry_func: Optional[str] = None,
        args: Optional[List[Any]] = None,
        timeout_sec: float = 12.0,
        max_events: int = 50000,
        max_recursion_depth: int = 1000
    ) -> ExecutionResult:
        payload = {
            "source_code": source_code,
            "entry_func": entry_func,
            "args": args,
            "timeout_sec": timeout_sec,
            "max_events": max_events,
            "max_recursion_depth": max_recursion_depth
        }
        encoded_payload = json.dumps(payload).encode("utf-8")

        # Prepare sanitized environment for child process
        clean_env = {
            "PATH": os.environ.get("PATH", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "WINDIR": os.environ.get("WINDIR", ""),
            "PYTHONPATH": BACKEND_DIR,
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
            "TMP": os.environ.get("TMP", "/tmp"),
            "TEMP": os.environ.get("TEMP", "/tmp")
        }

        cmd = [self.python_executable, os.path.join(BACKEND_DIR, "isolated_python_runner.py")]

        popen_kwargs = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "env": clean_env,
            "cwd": BACKEND_DIR
        }

        # On POSIX / Linux containers, if running as root, drop child worker execution to algolens-sandbox
        if sys.platform != "win32" and hasattr(os, "getuid") and os.getuid() == 0:
            try:
                import pwd
                sb_entry = pwd.getpwnam("algolens-sandbox")
                popen_kwargs["user"] = sb_entry.pw_uid
                popen_kwargs["group"] = sb_entry.pw_gid
            except (KeyError, ImportError):
                pass

        proc = None
        try:
            proc = subprocess.Popen(cmd, **popen_kwargs)

            # Enforce supervisor timeout (with grace period for flush)
            try:
                stdout_data, stderr_data = proc.communicate(
                    input=encoded_payload,
                    timeout=timeout_sec + 2.0
                )
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                return ExecutionResult(
                    success=False,
                    error_message=f"Execution timed out after {timeout_sec:.1f}s (process killed by supervisor).",
                    diagnostics=f"Timeout ceiling: {timeout_sec}s"
                )

            if proc.returncode != 0:
                err_text = stderr_data.decode("utf-8", errors="replace").strip()
                return ExecutionResult(
                    success=False,
                    error_message=err_text or f"Worker process terminated abnormally with exit code {proc.returncode}.",
                    diagnostics=f"exit_code: {proc.returncode}"
                )

            raw_out = stdout_data.decode("utf-8", errors="replace").strip()
            if not raw_out:
                err_text = stderr_data.decode("utf-8", errors="replace").strip()
                return ExecutionResult(
                    success=False,
                    error_message=err_text or "Worker produced empty execution output.",
                    diagnostics=""
                )

            data = json.loads(raw_out)
            # Reconstruct typed AlgoLensEvent list
            if "events" in data and isinstance(data["events"], list):
                data["events"] = [AlgoLensEvent(**e) for e in data["events"]]

            return ExecutionResult(**data)

        except Exception as e:
            if proc is not None:
                try:
                    proc.kill()
                except Exception:
                    pass
            return ExecutionResult(
                success=False,
                error_message=f"Failed to execute program in sandbox: {str(e)}",
                diagnostics=str(e)
            )


if __name__ == "__main__":
    run_worker_process()
