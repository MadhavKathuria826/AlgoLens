from tracer import Tracer
import json

code = """
class Node:
    def __init__(self, val):
        self.val = val
        self.next = None

head = Node(10)
"""

tracer = Tracer()
steps = tracer.run_code(code)

found_node_frame = False
for s in steps:
    for v in s.visualizations:
        if v.type == 'Function' and getattr(v.details, 'func', v.details.get('func', '')) == 'Node':
            found_node_frame = True
            print("Found frame!")

if not found_node_frame:
    print("Clean! No Node frame found.")
