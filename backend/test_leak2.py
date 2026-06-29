from tracer import Tracer
import json

def test_run():
    tracer = Tracer()
    code = """
class Node:
    def __init__(self, val):
        self.val = val
        self.next = None

head = Node(10)
"""
    steps = tracer.run_code(code)
    out = json.dumps([s.model_dump() for s in steps])
    print("Contains __main__:", "__main__" in out)
    if "__main__" in out:
        for s in steps:
            for v in s.visualizations:
                if "class" in str(v.details):
                    print(v.details)
            for k, v in s.locals.items():
                if "class" in str(v):
                    print("locals:", k, v)
test_run()
