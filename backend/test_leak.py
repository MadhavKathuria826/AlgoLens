import json
from tracer import Tracer

code = """
class Node:
    def __init__(self, val):
        self.val = val
        self.next = None

head = Node(10)
x = 1  # Add a line to see locals after assignment
"""

tracer = Tracer()
steps = tracer.run_code(code)

out = []
for s in steps:
    out.append(s.model_dump())

import os

out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'debug', 'leak_output.json'))
with open(out_path, "w") as f:
    json.dump(out, f, indent=2)
print("Done")
