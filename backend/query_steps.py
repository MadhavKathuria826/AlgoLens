import json
import os

path = r"C:\Users\hp\Desktop\Visualization\DSA Visualizer\frontend\public\mocks\fib_manual_deep.json"
with open(path) as f:
    data = json.load(f)

for idx, step in enumerate(data["steps"]):
    for vis in step["visualizations"]:
        if vis["type"] == "MEMOIZATION":
            d = vis["details"]
            print(f"StepIdx {idx}: Event: {d.get('event')}, Key: {d.get('key')}, Depth: {d.get('depth')}")
