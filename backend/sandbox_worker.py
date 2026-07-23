import sys
import os
import json
import traceback

def apply_linux_resource_limits():
    """Apply strict OS-level resource limits on Linux systems (e.g., Render)."""
    try:
        import resource
        
        # 1. CPU Time Limit (5 seconds CPU time)
        resource.setrlimit(resource.RLIMIT_CPU, (5, 6))
        
        # 2. Virtual Memory Ceiling (256 MB)
        mem_bytes = 256 * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        except (ValueError, OSError):
            pass
            
        # 3. Disable Subprocess Creation (0 max user processes / forks)
        try:
            resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
        except (ValueError, OSError):
            pass
            
        # 4. Restrict File Descriptors to Stdin, Stdout, Stderr only (0-2)
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (3, 3))
        except (ValueError, OSError):
            pass
    except ImportError:
        # Non-Linux system (e.g. Windows local development)
        pass

def sanitize_environment_and_modules():
    """Purge environment variables, disable sockets, and scrub sys.modules."""
    # Clear sensitive environment variables from subprocess memory
    os.environ.clear()

    # Disable socket creation (No network access)
    try:
        import socket
        socket.socket = None
        socket.create_connection = None
    except Exception:
        pass

    # Block dangerous modules in sys.modules
    dangerous_modules = [
        'subprocess', 'os', 'sys', 'socket', 'ctypes', 'shutil', 'glob',
        'importlib', 'multiprocessing', 'threading', '_thread', 'builtins',
        'pickle', 'urllib', 'http', 'ftplib', 'poplib', 'imaplib', 'smtplib'
    ]
    for mod in dangerous_modules:
        if mod in sys.modules and mod != 'sys' and mod != 'os':
            sys.modules[mod] = None

def main():
    apply_linux_resource_limits()

    # Read input payload from stdin
    raw_input = sys.stdin.read()
    if not raw_input:
        sys.stderr.write(json.dumps({"error": "Empty input payload"}))
        sys.exit(1)

    try:
        payload = json.loads(raw_input)
        code = payload.get("code", "")
        max_recursion_depth = payload.get("max_recursion_depth", 1000)
    except Exception as e:
        sys.stderr.write(json.dumps({"error": f"Invalid JSON payload: {e}"}))
        sys.exit(1)

    # Pre-import Tracer and all dependencies before scrubbing sys.modules
    from tracer import Tracer
    tracer = Tracer()

    # Sanitize environment and block modules right before code execution
    sanitize_environment_and_modules()

    # Temporarily redirect stdout to stderr during execution so tracer prints don't corrupt JSON stdout
    old_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        steps = tracer.run_code(code, max_recursion_depth)
    finally:
        sys.stdout = old_stdout

    # Format output steps as JSON dicts
    serialized_steps = []
    for s in steps:
        if hasattr(s, '__dict__'):
            d = dict(s.__dict__)
            if 'visualizations' in d:
                d['visualizations'] = [v.__dict__ if hasattr(v, '__dict__') else v for v in d['visualizations']]
            serialized_steps.append(d)
        else:
            serialized_steps.append(s)

    sys.stdout.write(json.dumps({"steps": serialized_steps, "error": None}))
    sys.stdout.flush()

if __name__ == "__main__":
    main()
