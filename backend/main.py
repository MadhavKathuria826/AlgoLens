import os
import sys
import uuid
import time
import json
import logging
import subprocess
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from models import CodeExecutionRequest, CodeExecutionResponse
from tracer import Tracer
from parser import validate_code
from leetcode_adapter import detect_entry_point, build_driver_code

logging.basicConfig(level=logging.INFO)
telemetry_logger = logging.getLogger("algolens.telemetry")

app = FastAPI(title="AlgoLens API")

# Workstream 7: GZip Response Compression for large event payloads (>1KB)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Workstream 8: CORS Hardening with configurable origins
raw_cors = os.getenv("CORS_ORIGINS", "")
if raw_cors.strip():
    allowed_origins = [o.strip() for o in raw_cors.split(",") if o.strip()]
else:
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://algolens.dev",
        "https://algolens.vercel.app"
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"]
)

# Workstream 5: Request ID Correlation Middleware
@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    req_id = request.headers.get("x-request-id") or request.headers.get("X-Request-ID")
    if not req_id:
        req_id = f"req_{uuid.uuid4().hex[:12]}"
    request.state.request_id = req_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response

@app.get("/api/version")
def get_version():
    commit_sha = os.getenv("RENDER_GIT_COMMIT", "")
    if not commit_sha:
        try:
            commit_sha = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
        except Exception as e:
            commit_sha = f"unknown: {e}"
    return {
        "commit": commit_sha,
        "version": "2.1.0-m10",
        "architecture": "universal-event-protocol-v2.1",
        "status": "production-ready"
    }

def _log_telemetry(req_id: str, lang: str, t_start: float, events: list, steps: list, success: bool, error: str = None, cache_status: str = None):
    dt_ms = (time.perf_counter() - t_start) * 1000.0
    payload = {
        "event": "execution_telemetry",
        "request_id": req_id,
        "language": lang,
        "duration_ms": round(dt_ms, 2),
        "event_count": len(events) if events else 0,
        "step_count": len(steps) if steps else 0,
        "success": success,
        "cache_status": cache_status or "N/A"
    }
    if error:
        payload["error_summary"] = str(error).splitlines()[0] if str(error) else ""
    telemetry_logger.info(json.dumps(payload))

@app.post("/api/execute", response_model=CodeExecutionResponse)
def execute_code(request: CodeExecutionRequest, req: Request = None, res: Response = None):
    req_id = getattr(getattr(req, "state", None), "request_id", None) or f"req_{uuid.uuid4().hex[:12]}"
    t_start = time.perf_counter()
    lang = (request.language or 'python').lower()
    if (request.language or '').lower() in ('cpp', 'c++'):
        import cpp_classifier
        try:
            entry_info = cpp_classifier.detect_entry_point(request.code, request.selected_method)
            if entry_info.get("is_ambiguous"):
                candidates = [c["name"] for c in entry_info.get("candidates", [])]
                _log_telemetry(req_id, "cpp", t_start, [], [], True)
                return CodeExecutionResponse(steps=[], needs_disambiguation=True, candidates=candidates, request_id=req_id)

            entry_func = entry_info.get("name")
            if not entry_func and entry_info.get("candidates"):
                entry_func = entry_info["candidates"][0]["name"]
            if not entry_func:
                entry_func = "main"

            params = entry_info.get("params", [])
            args = []
            if params and entry_func != "main":
                if not request.test_case:
                    _log_telemetry(req_id, "cpp", t_start, [], [], True)
                    return CodeExecutionResponse(steps=[], needs_test_case=True, params=params, request_id=req_id)
                import cpp_adapter
                test_case_data = cpp_adapter.parse_test_case(request.test_case)
                args = [test_case_data.get(p["name"]) for p in params]

            # Try NativeCompilationPipeline first (Universal LanguageRuntimeProducer)
            from native_runner import NativeCompilationPipeline
            from event_to_step_adapter import EventToStepAdapter
            try:
                native_pipeline = NativeCompilationPipeline()
                native_res = native_pipeline.execute_program(request.code, entry_func=entry_func, args=args)
                if native_res.success and native_res.events:
                    adapter = EventToStepAdapter()
                    steps = adapter.process_event_stream(native_res.events)
                    is_tree = cpp_classifier.classify_tree(request.code).get("is_tree", False)
                    is_linked_list = cpp_classifier.classify_linked_list(request.code).get("is_linked_list", False)
                    for step in steps:
                        if is_tree:
                            step.isTreeAlgorithm = True
                        elif is_linked_list:
                            step.isLinkedListAlgorithm = True
                    _log_telemetry(req_id, "cpp", t_start, native_res.events, steps, True)
                    return CodeExecutionResponse(
                        steps=steps,
                        events=native_res.events,
                        user_stdout=native_res.user_stdout,
                        diagnostics=native_res.compiler_diagnostics,
                        request_id=req_id
                    )
            except Exception as native_e:
                logging.warning(f"Native compilation pipeline fallback: {native_e}")

            # Fallback to CPPInterpreter with events
            from cpp_interpreter import CPPInterpreter
            interpreter = CPPInterpreter(max_recursion_depth=request.max_recursion_depth or 1000)
            events, steps, ret_val = interpreter.interpret_with_events(request.code, entry_func, args)

            is_tree = cpp_classifier.classify_tree(request.code).get("is_tree", False)
            is_linked_list = cpp_classifier.classify_linked_list(request.code).get("is_linked_list", False)
            for step in steps:
                if is_tree:
                    step.isTreeAlgorithm = True
                elif is_linked_list:
                    step.isLinkedListAlgorithm = True

            _log_telemetry(req_id, "cpp", t_start, events, steps, True)
            return CodeExecutionResponse(steps=steps, events=events, request_id=req_id)
        except Exception as e:
            _log_telemetry(req_id, "cpp", t_start, [], [], False, error=str(e))
            return CodeExecutionResponse(steps=[], error=str(e), request_id=req_id)



    try:
        validate_code(request.code)
    except ValueError as e:
        _log_telemetry(req_id, "python", t_start, [], [], False, error=str(e))
        return CodeExecutionResponse(steps=[], error=str(e), request_id=req_id)
        
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
            _log_telemetry(req_id, "python", t_start, [], [], True)
            return CodeExecutionResponse(steps=[], needs_disambiguation=True, candidates=candidates, request_id=req_id)
                
        if not entry_info.get("params"):
            try:
                driver_code = build_driver_code(entry_info, "")
                logging.info(f"Synthesized driver code:\n{driver_code}")
                print(f"Synthesized driver code:\n{driver_code}")
                request.code += driver_code
            except ValueError as e:
                _log_telemetry(req_id, "python", t_start, [], [], False, error=str(e))
                return CodeExecutionResponse(steps=[], error=str(e), request_id=req_id)
        else:
            if not request.test_case:
                _log_telemetry(req_id, "python", t_start, [], [], True)
                return CodeExecutionResponse(steps=[], needs_test_case=True, params=entry_info.get("params", []), request_id=req_id)
                
            try:
                driver_code = build_driver_code(entry_info, request.test_case)
                logging.info(f"Synthesized driver code:\n{driver_code}")
                print(f"Synthesized driver code:\n{driver_code}")
                request.code += driver_code
            except ValueError as e:
                _log_telemetry(req_id, "python", t_start, [], [], False, error=str(e))
                return CodeExecutionResponse(steps=[], error=str(e), request_id=req_id)
            
    from avl_classifier import classify_avl
    from avl_tracer import run_avl_tracer
    from rbt_classifier import classify_rbt
    from rbt_tracer import run_rbt_tracer
    from trie_classifier import classify_trie
    from trie_tracer import run_trie_tracer
    from dp_tracer import run_dp_tracer
    from dp_classifier import classify_tabulation, classify_memoization
    try:
        avl_res = classify_avl(request.code)
        rbt_res = classify_rbt(request.code)
        trie_res = classify_trie(request.code)
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

        # Universal Python Runtime Producer with Subprocess Sandbox Isolation (M7-M9)
        from python_producer import PythonRuntimeProducer
        from event_to_step_adapter import EventToStepAdapter
        from universal_structural_adapter import (
            enrich_avl_steps,
            enrich_rbt_steps,
            enrich_trie_steps,
            enrich_dp_tabulation_steps,
            enrich_dp_memoization_steps
        )

        producer = PythonRuntimeProducer()
        exec_res = producer.execute_program(
            source_code=request.code,
            timeout_sec=12.0,
            max_recursion_depth=request.max_recursion_depth or 1000,
            isolated=True
        )

        if not exec_res.success and exec_res.error_message:
            _log_telemetry(req_id, lang, t_start, exec_res.events or [], [], False, error=exec_res.error_message)
            return CodeExecutionResponse(
                steps=[],
                error=exec_res.error_message,
                events=exec_res.events,
                user_stdout=exec_res.user_stdout,
                diagnostics=exec_res.diagnostics,
                request_id=req_id
            )

        adapter = EventToStepAdapter()
        steps = adapter.process_event_stream(exec_res.events)

        # Apply structural enrichments
        if avl_res.get("is_avl"):
            steps = enrich_avl_steps(steps, request.code)
        elif rbt_res.get("is_rbt"):
            steps = enrich_rbt_steps(steps, request.code)
        elif trie_res.get("is_trie"):
            steps = enrich_trie_steps(steps)
        elif tab_res and tab_res.get("is_tabulation"):
            steps = enrich_dp_tabulation_steps(steps, request.code, tab_res["table_var_name"], tab_res["dimensions"])
        elif memo_res and memo_res.get("is_memoization"):
            steps = enrich_dp_memoization_steps(steps, request.code, memo_res)

        _log_telemetry(req_id, lang, t_start, exec_res.events or [], steps, True)
        return CodeExecutionResponse(
            steps=steps,
            events=exec_res.events,
            user_stdout=exec_res.user_stdout,
            diagnostics=exec_res.diagnostics,
            recurrence_relations=recurrence_relations,
            request_id=req_id
        )
    except Exception as e:
        _log_telemetry(req_id, lang, t_start, [], [], False, error=str(e))
        return CodeExecutionResponse(steps=[], error=str(e), request_id=req_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
