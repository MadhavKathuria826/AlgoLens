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

run_test("CASE 1: Bare function, no test_case supplied at all", {
  "code": "def twoSum(nums, target):\n    for i in range(len(nums)):\n        for j in range(i+1, len(nums)):\n            if nums[i] + nums[j] == target:\n                return [i, j]"
})

run_test("CASE 2: Zero-param method, specifically named countToTen", {
  "code": "class Solution:\n    def countToTen(self):\n        return [i for i in range(10)]"
})

run_test("CASE 8: nums = [2,7,11,15]", {
  "code": "class Solution:\n    def twoSum(self, nums, target):\n        return []",
  "test_case": "nums = [2,7,11,15]\n\n# my target value\ntarget = 9"
})
