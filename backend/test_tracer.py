import json
from tracer import Tracer

code = """
def factorial(n):
    if n == 0:
        return 1
    return n * factorial(n - 1)

result = factorial(3)
"""

t = Tracer()
steps = t.run_code(code)

out = []
for s in steps:
    out.append({
        "step": s.step_number,
        "line": s.line_number,
        "event": s.event_type,
        "visualizations": [v.dict() for v in s.visualizations]
    })
import os

out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'debug', 'tracer_output.json'))
with open(out_path, "w") as f:
    json.dump(out, f, indent=2)
