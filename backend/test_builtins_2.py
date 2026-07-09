import sys
sys.path.append(r"C:\Users\hp\Desktop\Visualization\DSA Visualizer\backend")
from tracer import Tracer

def test_snippet(name, code_snippet):
    tracer = Tracer()
    steps = tracer.run_code(code_snippet)
    if steps and steps[-1].event_type == 'error':
        print(f"FAIL: {name} -> {steps[-1].visualizations[0].details['msg']}")
    else:
        print(f"PASS: {name}")

tests = {
    "dict": "dict(a=1)",
    "tuple": "tuple([1,2])",
    "set": "set([1,2])",
    "frozenset": "frozenset([1,2])",
    "enumerate": "list(enumerate([1]))",
    "zip": "list(zip([1],[2]))",
    "map": "list(map(lambda x: x, [1]))",
    "filter": "list(filter(lambda x: True, [1]))",
    "sorted": "sorted([2,1])",
    "reversed": "list(reversed([1,2]))",
    "any": "any([True])",
    "all": "all([True])",
    "next": "next(iter([1]))",
    "iter": "iter([1])",
    "divmod": "divmod(5,2)",
    "pow": "pow(2,3)",
    "round": "round(2.5)",
    "chr": "chr(97)",
    "ord": "ord('a')",
    "hasattr": "hasattr(1, '__class__')",
    "KeyError": "try:\n    raise KeyError('test')\nexcept KeyError:\n    pass",
    "IndexError": "try:\n    raise IndexError('test')\nexcept IndexError:\n    pass",
    "StopIteration": "try:\n    raise StopIteration('test')\nexcept StopIteration:\n    pass",
    "ZeroDivisionError": "try:\n    raise ZeroDivisionError('test')\nexcept ZeroDivisionError:\n    pass",
    "AttributeError": "try:\n    raise AttributeError('test')\nexcept AttributeError:\n    pass",
    "RuntimeError": "try:\n    raise RuntimeError('test')\nexcept RuntimeError:\n    pass",
    "NotImplementedError": "try:\n    raise NotImplementedError('test')\nexcept NotImplementedError:\n    pass"
}

for name, snippet in tests.items():
    test_snippet(name, snippet)
