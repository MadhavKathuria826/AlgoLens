from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models import CodeExecutionRequest, CodeExecutionResponse
from tracer import Tracer
from parser import validate_code
from leetcode_adapter import detect_entry_point, build_driver_code
import logging
logging.basicConfig(level=logging.INFO)
app = FastAPI(title="AlgoLens API")

# Allow frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/execute", response_model=CodeExecutionResponse)
def execute_code(request: CodeExecutionRequest):
    try:
        validate_code(request.code)
    except ValueError as e:
        return CodeExecutionResponse(steps=[], error=str(e))
        
    entry_info = detect_entry_point(request.code, request.selected_method)
    logging.info(f"Entry point info: {entry_info}")
    print(f"Entry point info: {entry_info}")
    
    if entry_info.get("has_invocation"):
        logging.info("Using explicit invocation branch")
        print("Using explicit invocation branch")
    else:
        is_ambig = entry_info.get("is_ambiguous", False)
        candidates = entry_info.get("candidates", [])
        
        if is_ambig:
            return CodeExecutionResponse(steps=[], needs_disambiguation=True, candidates=candidates)
                
        if not entry_info.get("params"):
            try:
                driver_code = build_driver_code(entry_info, "")
                logging.info(f"Synthesized driver code:\n{driver_code}")
                print(f"Synthesized driver code:\n{driver_code}")
                request.code += driver_code
            except ValueError as e:
                return CodeExecutionResponse(steps=[], error=str(e))
        else:
            if not request.test_case:
                return CodeExecutionResponse(steps=[], needs_test_case=True, params=entry_info.get("params", []))
                
            try:
                driver_code = build_driver_code(entry_info, request.test_case)
                logging.info(f"Synthesized driver code:\n{driver_code}")
                print(f"Synthesized driver code:\n{driver_code}")
                request.code += driver_code
            except ValueError as e:
                return CodeExecutionResponse(steps=[], error=str(e))
            
    from avl_classifier import classify_avl
    from avl_tracer import run_avl_tracer
    from rbt_classifier import classify_rbt
    from rbt_tracer import run_rbt_tracer
    from dp_tracer import run_dp_tracer
    from dp_classifier import classify_tabulation, classify_memoization
    try:
        avl_res = classify_avl(request.code)
        rbt_res = classify_rbt(request.code)
        recurrence_relations = []
        try:
            tab_res = classify_tabulation(request.code)
            memo_res = classify_memoization(request.code)
            if tab_res.get("recurrence_relations"):
                recurrence_relations.extend(tab_res["recurrence_relations"])
            if memo_res.get("recurrence_relations"):
                recurrence_relations.extend(memo_res["recurrence_relations"])
        except Exception:
            pass

        if avl_res["is_avl"]:
            steps = run_avl_tracer(request.code)
        elif rbt_res["is_rbt"]:
            steps = run_rbt_tracer(request.code)
        else:
            steps = run_dp_tracer(request.code)
            if steps is None:
                tracer = Tracer()
                steps = tracer.run_code(request.code, request.max_recursion_depth)
        return CodeExecutionResponse(steps=steps, recurrence_relations=recurrence_relations)
    except Exception as e:
        return CodeExecutionResponse(steps=[], error=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
