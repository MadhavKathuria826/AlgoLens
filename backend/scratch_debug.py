import sys
import os
sys.path.append(r"C:\Users\hp\Desktop\Visualization\DSA Visualizer\backend")
from tracer import Tracer

code = """
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

class DiagnosticTracer(Tracer):
    def __init__(self):
        super().__init__()
        self.raw_frames = []

    def trace_calls(self, frame, event, arg):
        if len(self.raw_frames) > 10000:
            raise ValueError("Exceeded maximum debug trace frame count of 10000. Aborting to prevent infinite loop.")
        if event in ('call', 'line', 'return'):
            filename = frame.f_code.co_filename
            if filename != "<string>":
                return None
            func_name = frame.f_code.co_name
            lineno = frame.f_lineno
            self.raw_frames.append((event, lineno, func_name))
        return super().trace_calls(frame, event, arg)

t = DiagnosticTracer()
t.run_code(code)
print("RAW FRAMES LEN:", len(t.raw_frames))
print("RETAINED STEPS LEN:", len(t.steps))
print("DROPPED COUNT IN TRACER:", t.dropped_frames)

# Compare them side-by-side or count unmatched
print("RETAINED STEPS:")
for s in t.steps:
    print(f"Step {s.step_number}: {[v.type for v in s.visualizations]} (Line {s.line_number})")
if t.steps and t.steps[-1].visualizations and t.steps[-1].visualizations[0].type == "Error":
    print("ERROR MSG:", t.steps[-1].visualizations[0].details.get("msg"))
