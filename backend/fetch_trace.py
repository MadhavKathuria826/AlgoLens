import urllib.request
import json
import pprint

code = """
arr1 = [10, 20]
arr2 = [1, 2]
total = 0

for num in arr1:
    total += num
for item in arr2:
    total += item
"""

req = urllib.request.Request('http://localhost:8000/api/execute', data=json.dumps({'code': code}).encode('utf-8'), headers={'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req)
data = json.loads(resp.read().decode('utf-8'))

for i, step in enumerate(data['steps']):
    print(f"\n--- STEP {i} ---")
    print(f"Line: {step.get('line_number')}")
    print("Locals:", step.get('locals'))
    print("Visualizations:", json.dumps(step.get('visualizations')))
