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
        
    entry_info = detect_entry_point(request.code)
    logging.info(f"Entry point info: {entry_info}")
    print(f"Entry point info: {entry_info}")
    
    if entry_info.get("has_invocation"):
        logging.info("Using explicit invocation branch")
        print("Using explicit invocation branch")
    else:
        is_ambig = entry_info.get("is_ambiguous", False)
        candidates = entry_info.get("candidates", [])
        
        if is_ambig:
            if request.selected_method and request.selected_method in candidates:
                import ast
                tree = ast.parse(request.code)
                target_class = [n for n in tree.body if isinstance(n, ast.ClassDef)][-1]
                m = next(n for n in target_class.body if isinstance(n, ast.FunctionDef) and n.name == request.selected_method)
                params = [a.arg for a in m.args.args if a.arg != 'self']
                entry_info = {
                    "has_invocation": False,
                    "is_ambiguous": False,
                    "target": m.name,
                    "params": params,
                    "is_class": True,
                    "class_name": target_class.name
                }
            else:
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
            
    tracer = Tracer()
    try:
        steps = tracer.run_code(request.code, request.max_recursion_depth)
        return CodeExecutionResponse(steps=steps)
    except Exception as e:
        return CodeExecutionResponse(steps=[], error=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
