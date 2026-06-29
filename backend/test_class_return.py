import sys
def trace(f,e,a):
    if e == 'return':
        print(f"return from {f.f_code.co_name}, arg: {type(a)} {a}")
    return trace

sys.settrace(trace)
class Node:
    pass
sys.settrace(None)
