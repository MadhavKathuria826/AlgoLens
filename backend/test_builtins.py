import sys
sys.path.append(r"C:\Users\hp\Desktop\Visualization\DSA Visualizer\backend")
from tracer import Tracer

def test_snippet(name, code_snippet):
    tracer = Tracer()
    steps = tracer.run_code(code_snippet)
    # Check if the last step is an error
    if steps and steps[-1].event_type == 'error':
        print(f"FAIL: {name} -> {steps[-1].visualizations[0].details['msg']}")
    else:
        print(f"PASS: {name}")

tests = {
    "object": "class A(object): pass",
    "Exception": "try:\n    raise Exception('test')\nexcept Exception:\n    pass",
    "ValueError": "try:\n    raise ValueError('test')\nexcept ValueError:\n    pass",
    "TypeError": "try:\n    raise TypeError('test')\nexcept TypeError:\n    pass",
    "super": "class A:\n    def f(self): pass\nclass B(A):\n    def f(self): super().f()\nB().f()",
    "isinstance": "isinstance(1, int)",
    "staticmethod": "class A:\n    @staticmethod\n    def f(): pass",
    "classmethod": "class A:\n    @classmethod\n    def f(cls): pass",
}

for name, snippet in tests.items():
    test_snippet(name, snippet)
