from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models import CodeExecutionRequest, CodeExecutionResponse
from tracer import Tracer
from parser import validate_code

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
        
    tracer = Tracer()
    try:
        steps = tracer.run_code(request.code, request.max_recursion_depth)
        return CodeExecutionResponse(steps=steps)
    except Exception as e:
        return CodeExecutionResponse(steps=[], error=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
