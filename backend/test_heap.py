from tracer import Tracer
import json

codes = {
    "Singly Linked List": """
class Node:
    def __init__(self, val, next=None):
        self.val = val
        self.next = next

head = Node(10)
head.next = Node(20)
head.next.next = Node(30)
""",
    "Doubly Linked List": """
class Node:
    def __init__(self, val, next=None, prev=None):
        self.val = val
        self.next = next
        self.prev = prev

head = Node(10)
n2 = Node(20)
n3 = Node(30)

head.next = n2
n2.prev = head
n2.next = n3
n3.prev = n2
""",
    "Circular Singly Linked List": """
class Node:
    def __init__(self, val, next=None):
        self.val = val
        self.next = next

head = Node(10)
n2 = Node(20)
n3 = Node(30)

head.next = n2
n2.next = n3
n3.next = head
""",
    "Circular Doubly Linked List": """
class Node:
    def __init__(self, val, next=None, prev=None):
        self.val = val
        self.next = next
        self.prev = prev

head = Node(10)
n2 = Node(20)
n3 = Node(30)

head.next = n2
n2.prev = head

n2.next = n3
n3.prev = n2

n3.next = head
head.prev = n3
"""
}

for name, code in codes.items():
    t = Tracer()
    steps = t.run_code(code)
    last_step = steps[-1]
    print(f"--- {name} ---")
    print("Locals:")
    print(json.dumps(last_step.locals, indent=2))
    print("Heap:")
    print(json.dumps(last_step.heap, indent=2))
    print("\n")
