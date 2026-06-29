import sys
import os

# Add backend directory to path
sys.path.append(os.path.dirname(__file__))

from tracer import Tracer

code = """
class Node:
    def __init__(self, val):
        self.val = val
        self.left = None
        self.right = None

class BST:
    def __init__(self):
        self.root = None

    def insert(self, val):
        self.root = self._insert(self.root, val)

    def _insert(self, node, val):
        if not node:
            return Node(val)
        if val < node.val:
            node.left = self._insert(node.left, val)
        else:
            node.right = self._insert(node.right, val)
        return node

bst = BST()
# Large list literal to test compression
values = [
    50,
    25,
    75,
    12,
    37,
    60,
    85,
    6,
    18,
    30
]

for v in values:
    bst.insert(v)
"""

tracer = Tracer()
steps = tracer.run_code(code)
print(f"Original frames: {tracer.original_frame_count}")
print(f"Compressed frames: {len(tracer.steps)}")
print(f"Dropped frames: {tracer.dropped_frames}")
