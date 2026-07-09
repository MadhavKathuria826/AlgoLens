import sys
import json
sys.path.append(r"C:\Users\hp\Desktop\Visualization\DSA Visualizer\backend")

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

print("\n==================================================")
print("CASE: twoSum(object)")
print("==================================================")
payload = {
  "code": "class Solution(object):\n    def twoSum(self, nums, target):\n        return []",
  "test_case": "nums = [2,7]\ntarget = 9"
}
resp = client.post("/api/execute", json=payload)
resp_json = resp.json()
if 'steps' in resp_json:
    steps_len = len(resp_json['steps'])
    resp_json['steps'] = f"[{steps_len} steps]"
print(f"JSON RESPONSE:\n{json.dumps(resp_json, indent=2)}")
