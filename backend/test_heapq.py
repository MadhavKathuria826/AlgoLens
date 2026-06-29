import sys
import os

# Add backend directory to path
sys.path.append(os.path.dirname(__file__))

from tracer import Tracer

code = """import heapq

heap = []

heapq.heappush(heap, 50)
heapq.heappush(heap, 20)
heapq.heappush(heap, 10)
"""

tracer = Tracer()
steps = tracer.run_code(code)

print(f"Total compressed frames generated: {len(steps)}\n")
for i, step in enumerate(steps):
    arrays = [v.details['value'] for v in step.visualizations if v.type == 'Array']
    print(f"Frame {i}: Line {step.line_number} -> Arrays: {arrays}")
