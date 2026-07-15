import sys
import os
import json
sys.path.append(r"C:\Users\hp\Desktop\Visualization\DSA Visualizer\backend")
from dp_tracer import run_dp_tracer

FIB_TAB_1D = """
def fib(n):
    dp = [0] * (n + 1)
    dp[0] = 0
    if n > 0:
        dp[1] = 1
    for i in range(2, n + 1):
        dp[i] = dp[i-1] + dp[i-2]
    return dp[n]
fib(5)
"""

MIN_EDIT_DISTANCE_2D = """
def min_edit_distance(word1, word2):
    m, n = len(word1), len(word2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
        
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if word1[i-1] == word2[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])
    return dp[m][n]
min_edit_distance("abc", "yaby")
"""

FIB_MANUAL_DEEP = """
memo = {}
def fib(n):
    if n in memo:
        return memo[n]
    if n <= 1:
        return n
    memo[n] = fib(n - 1) + fib(n - 2)
    return memo[n]
fib(5)
"""

# Note: we use fib(5) for the screenshot simulation to match the active recursion stack 5 -> 4 -> 3 at step 7

def save_mock(filename, code):
    steps = run_dp_tracer(code)
    # Serialize steps to dict
    serialized = []
    for s in steps:
        serialized.append({
            "step_number": s.step_number,
            "line_number": s.line_number,
            "event_type": s.event_type,
            "locals": s.locals,
            "heap": s.heap,
            "visualizations": [
                {
                    "type": v.type,
                    "details": v.details
                } for v in s.visualizations
            ]
        })
        
    out_dir = r"C:\Users\hp\Desktop\Visualization\DSA Visualizer\frontend\public\mocks"
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, filename), "w") as f:
        json.dump({"steps": serialized, "code": code}, f, indent=2)
    print(f"Saved {filename}")

if __name__ == "__main__":
    save_mock("fib_tab_1d.json", FIB_TAB_1D)
    save_mock("min_edit_distance_2d.json", MIN_EDIT_DISTANCE_2D)
    save_mock("fib_manual_deep.json", FIB_MANUAL_DEEP)
