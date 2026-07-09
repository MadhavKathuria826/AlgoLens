import sys
import json
sys.path.append(r"C:\Users\hp\Desktop\Visualization\DSA Visualizer\backend")

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def run_test(case_name, payload):
    print(f"\n{'='*50}\n{case_name}\n{'='*50}")
    resp = client.post("/api/execute", json=payload)
    
    resp_json = resp.json()
    if 'steps' in resp_json:
        steps_len = len(resp_json['steps'])
        resp_json['steps'] = f"[{steps_len} steps]"
    print(f"JSON RESPONSE:\n{json.dumps(resp_json, indent=2)}")

run_test("CASE 1: Bare function, no class", {
    "code": "def twoSum(nums, target):\n    return [0, 1]",
    "test_case": "nums = [2,7]\ntarget = 9"
})

run_test("CASE 2: Method with 0 params after self", {
    "code": "class Solution:\n    def do_something(self):\n        return 1"
})

run_test("CASE 3: Malicious/non-literal test case", {
    "code": "class Solution:\n    def twoSum(self, nums, target):\n        return [0, 1]",
    "test_case": "nums = __import__('os').listdir()\ntarget = 9"
})

run_test("CASE 4: Test case referencing a function call", {
    "code": "class Solution:\n    def twoSum(self, nums, target):\n        return [0, 1]",
    "test_case": "nums = [2,7]\ntarget = len([1,2,3])"
})

run_test("CASE 5: Test case with nested structures", {
    "code": "class Solution:\n    def numIslands(self, grid, target):\n        return 0",
    "test_case": "grid = [[1,2],[3,4]]\ntarget = 5"
})

run_test("CASE 6: Method with default arg", {
    "code": "class Solution:\n    def twoSum(self, nums, target=9):\n        return [0, 1]"
})

run_test("CASE 7: Already-invoked LeetCode-style code", {
    "code": "class Solution:\n    def twoSum(self, nums, target):\n        return [0, 1]\n\nres = Solution().twoSum([2,7], 9)"
})

run_test("CASE 8: Multi-line/trailing blank/comment", {
    "code": "class Solution:\n    def twoSum(self, nums, target):\n        return [0, 1]",
    "test_case": "nums = [2,7]\n\ntarget = 9\n# a comment\n\n"
})
