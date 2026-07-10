import sys
import os

# Add backend directory to path
sys.path.append(os.path.dirname(__file__))

from tracer import Tracer
from leetcode_adapter import detect_entry_point, build_driver_code

# User's solution code (copied LeetCode style, has Optional[TreeNode] annotation)
code = """
class Solution:
    def maxDepth(self, root: Optional[TreeNode]) -> int:
        if not root:
            return 0
        return 1 + max(self.maxDepth(root.left), self.maxDepth(root.right))
"""

# Let's test with the first case: [3,9,20,null,null,15,7]
test_case_1 = "root = [3,9,20,null,null,15,7]"
entry_info_1 = detect_entry_point(code)
print("Entry info:", entry_info_1)

driver_code_1 = build_driver_code(entry_info_1, test_case_1)
print("\nGenerated driver code 1:\n", driver_code_1)

full_code_1 = code + driver_code_1

tracer_1 = Tracer()
steps_1 = tracer_1.run_code(full_code_1)

print("\nExecution status of case 1:")
errors_1 = [s for s in steps_1 if s.event_type == 'error']
if errors_1:
    print("FAILED with error:", errors_1[0].visualizations[0].details['msg'])
else:
    print("SUCCESS! Steps collected:", len(steps_1))
    print("Final variables:", steps_1[-1].locals)
    print("Final heap state:")
    import json
    # Print heap objects in a readable format
    for k, v in steps_1[-1].heap.items():
         print(f"  {k}: {v}")


# Let's test with the second case: [1,null,2,3]
test_case_2 = "root = [1,null,2,3]"
entry_info_2 = detect_entry_point(code)
driver_code_2 = build_driver_code(entry_info_2, test_case_2)
print("\nGenerated driver code 2:\n", driver_code_2)

full_code_2 = code + driver_code_2

tracer_2 = Tracer()
steps_2 = tracer_2.run_code(full_code_2)

print("\nExecution status of case 2:")
errors_2 = [s for s in steps_2 if s.event_type == 'error']
if errors_2:
    print("FAILED with error:", errors_2[0].visualizations[0].details['msg'])
else:
    print("SUCCESS! Steps collected:", len(steps_2))
    print("Final variables:", steps_2[-1].locals)
    print("Final heap state:")
    for k, v in steps_2[-1].heap.items():
         print(f"  {k}: {v}")
