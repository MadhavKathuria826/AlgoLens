import sys
sys.path.append(r"C:\Users\hp\Desktop\Visualization\DSA Visualizer\backend")

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

print("--- TEST A: Normal already-working script with explicit invocation ---")
code_a = """
def my_func(x):
    return x * 2
res = my_func(5)
"""
resp_a = client.post("/api/execute", json={"code": code_a})
print("Response JSON keys:", resp_a.json().keys())
if resp_a.json().get('steps'):
    print("Steps count:", len(resp_a.json()['steps']))

print("\n--- TEST B: Bare class Solution with one method ---")
code_b = """
class Solution:
    def twoSum(self, nums: list[int], target: int) -> list[int]:
        return [0, 1]
"""
resp_b = client.post("/api/execute", json={"code": code_b})
print("Response JSON:", {k:v for k,v in resp_b.json().items() if k != 'steps'})

print("\n--- TEST C: Same snippet with a submitted test case ---")
resp_c = client.post("/api/execute", json={
    "code": code_b,
    "test_case": "nums = [2,7,11,15]\ntarget = 9"
})
steps_c = resp_c.json().get('steps', [])
print("Steps count:", len(steps_c))
if steps_c:
    last_step = steps_c[-1]
    print("Final step locals:", last_step.get('locals'))

print("\n--- TEST D: Class with two public methods ---")
code_d = """
class Solution:
    def methodOne(self, a):
        pass
    def methodTwo(self, b):
        pass
"""
resp_d = client.post("/api/execute", json={"code": code_d})
print("Response JSON:", {k:v for k,v in resp_d.json().items() if k != 'steps'})
