import sys
import ast

code = """
class Node:
    def __init__(self, val):
        self.val = val
        self.next = None

def foo():
    pass

foo()
"""

tree = ast.parse(code)
ast_map = {}
for node in ast.walk(tree):
    if hasattr(node, 'lineno'):
        ast_map[node.lineno] = node

def trace_calls(frame, event, arg):
    if event == 'call':
        func_name = frame.f_code.co_name
        lineno = frame.f_lineno
        node = ast_map.get(lineno)
        node_type = type(node).__name__ if node else "None"
        print(f"call: {func_name} at line {lineno}, node: {node_type}")
    return trace_calls

sys.settrace(trace_calls)
exec(code, {})
sys.settrace(None)
