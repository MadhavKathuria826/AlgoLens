import json
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from tracer import Tracer

code = """
import heapq

h = []

for x in [50,40,30,20,10]:
    heapq.heappush(h, x)
"""

tracer = Tracer()
steps = tracer.run_code(code)

out = []
for s in steps:
    out.append({
        "step_number": s.step_number,
        "line_number": s.line_number,
        "event_type": s.event_type,
        "locals": s.locals,
        "heap": s.heap,
        "visualizations": [v.model_dump() for v in s.visualizations]
    })

with open("trace_output.json", "w") as f:
    json.dump(out, f, indent=2)
