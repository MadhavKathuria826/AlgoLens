import sys
import os
import json
import subprocess
from typing import List
from models import Step, VisualizationData

def run_sandboxed_python(code: str, max_recursion_depth: int = 1000) -> List[Step]:
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    worker_script = os.path.join(backend_dir, "sandbox_worker.py")

    payload_str = json.dumps({
        "code": code,
        "max_recursion_depth": max_recursion_depth
    })

    try:
        proc = subprocess.Popen(
            [sys.executable, worker_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        try:
            stdout_data, stderr_data = proc.communicate(input=payload_str, timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return [Step(
                step_number=1,
                line_number=0,
                event_type="error",
                visualizations=[VisualizationData(type="Error", details={"msg": "Execution Timed Out: CPU/wall-clock limit exceeded (5.0s)"})]
            )]

        if proc.returncode != 0:
            err_msg = stderr_data.strip() if stderr_data else f"Process terminated with exit code {proc.returncode}"
            if "MemoryError" in err_msg or proc.returncode in (-9, 137, 3221225477): # SIGKILL / Memory crash
                err_msg = "Execution Terminated: Memory ceiling or process limit exceeded."
            return [Step(
                step_number=1,
                line_number=0,
                event_type="error",
                visualizations=[VisualizationData(type="Error", details={"msg": err_msg})]
            )]

        try:
            res = json.loads(stdout_data)
            if res.get("error"):
                return [Step(
                    step_number=1,
                    line_number=0,
                    event_type="error",
                    visualizations=[VisualizationData(type="Error", details={"msg": res["error"]})]
                )]
            
            raw_steps = res.get("steps", [])
            steps = [Step(**s) if isinstance(s, dict) else s for s in raw_steps]
            return steps
        except Exception as parse_err:
            return [Step(
                step_number=1,
                line_number=0,
                event_type="error",
                visualizations=[VisualizationData(type="Error", details={"msg": f"Sandbox output parsing error: {parse_err}"})]
            )]

    except Exception as exc:
        return [Step(
            step_number=1,
            line_number=0,
            event_type="error",
            visualizations=[VisualizationData(type="Error", details={"msg": f"Sandbox initialization error: {exc}"})]
        )]
