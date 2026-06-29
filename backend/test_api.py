import sys
import os

sys.path.append(os.path.dirname(__file__))

from main import execute_code
from models import CodeExecutionRequest

request = CodeExecutionRequest(code="""
import heapq
heap = []
heapq.heappush(heap, 10)
""")

response = execute_code(request)

if response.error:
    print(f"API ERROR: {response.error}")
else:
    print("API SUCCESS! Traced Steps:")
    for step in response.steps:
        arrays = [v.details['value'] for v in step.visualizations if v.type == 'Array']
        print(f"Line {step.line_number} -> Arrays: {arrays}")
