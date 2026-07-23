import json
import sys
import os

# Ensure backend directory is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sandbox_runner import run_sandboxed_python

payloads = [
    {
        "id": "PAYLOAD_1_SHELL_OUT",
        "name": "1. Shell-out attempt: __import__('subprocess').run(['ls'])",
        "code": "__import__('subprocess').run(['ls'])"
    },
    {
        "id": "PAYLOAD_2_EVAL_COMPILE",
        "name": "2. Eval/compile escape attempt: eval(compile('1+1', '', 'eval'))",
        "code": "eval(compile('1+1', '', 'eval'))"
    },
    {
        "id": "PAYLOAD_3_BUILTIN_REFLECTION",
        "name": "3. Builtin reflection escape attempt: getattr(__builtins__, '__import__')('os')",
        "code": "getattr(__builtins__, '__import__')('os')"
    },
    {
        "id": "PAYLOAD_4_FORK_THREAD_SPAWN",
        "name": "4. Fork bomb / thread spawn attempt: import _thread; _thread.start_new_thread(lambda: None, ())",
        "code": "import _thread\n_thread.start_new_thread(lambda: None, ())"
    },
    {
        "id": "PAYLOAD_5_INFINITE_LOOP",
        "name": "5. Infinite loop (CPU/Wall-clock timeout test): while True: pass",
        "code": "while True:\n    pass"
    },
    {
        "id": "PAYLOAD_6_LARGE_MEMORY_ALLOC",
        "name": "6. Large memory allocation test: x = [0] * (10**9)",
        "code": "x = [0] * (10**9)"
    },
    {
        "id": "PAYLOAD_7_ENV_EXFILTRATION",
        "name": "7. Process environment / procfs exfiltration attempt: open('/proc/self/environ').read()",
        "code": "try:\n    import os\n    env_val = os.environ\nexcept Exception:\n    env_val = open('/proc/self/environ').read()"
    }
]

print("=" * 80)
print("RUNNING PROCESS ISOLATION SANDBOX SECURITY VERIFICATION GATE PASS")
print("=" * 80)

def serialize_step(s):
    if hasattr(s, '__dict__'):
        d = dict(s.__dict__)
        if 'visualizations' in d:
            d['visualizations'] = [v.__dict__ if hasattr(v, '__dict__') else v for v in d['visualizations']]
        return d
    return s

for p in payloads:
    print(f"\n--- {p['name']} ---")
    print(f"PAYLOAD:\n{p['code']}\n")
    steps = run_sandboxed_python(p['code'])
    print("SANDBOX RESPONSE STEPS / ERROR:")
    for s in steps:
        print(json.dumps(serialize_step(s), indent=2))
    print("-" * 80)
