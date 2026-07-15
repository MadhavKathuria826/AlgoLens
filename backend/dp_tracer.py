import sys
import ast
import copy
import types
from typing import List
from models import Step, VisualizationData
from dp_classifier import (
    classify_tabulation,
    classify_memoization,
    extract_subscript_info,
    references_params
)

# --- Pure AST / Evaluation Utilities ---

def eval_ast_node(node, globals_dict, locals_dict):
    try:
        expr = ast.Expression(body=node)
        code_obj = compile(expr, '<string>', 'eval')
        return eval(code_obj, globals_dict, locals_dict)
    except Exception:
        return None

def build_ast_map(code: str) -> dict:
    try:
        tree = ast.parse(code)
        ast_map = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.stmt) and hasattr(node, 'lineno'):
                ast_map[node.lineno] = node
        return ast_map
    except Exception:
        return {}

def resolve_loop_bounds(code: str, context_locals: dict, context_globals: dict) -> list:
    try:
        tree = ast.parse(code)
    except Exception:
        return []
        
    bounds = []
    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == 'range':
                args = node.iter.args
                stop_expr = args[0] if len(args) == 1 else args[1]
                val = eval_ast_node(stop_expr, context_globals, context_locals)
                if isinstance(val, int):
                    bounds.append(val)
    return bounds

def make_key(args, kwargs):
    if len(args) == 1 and not kwargs:
        return str(args[0])
    key_parts = list(args)
    if kwargs:
        for k in sorted(kwargs.keys()):
            key_parts.append((k, kwargs[k]))
    return str(tuple(key_parts))

# --- Tabulation Trace Processor ---

def post_process_tabulation(steps: List[Step], code: str, table_var_name: str, dimensions: int) -> List[Step]:
    ast_map = build_ast_map(code)
    
    # 1. Resolve table_shape
    table_shape = None
    for step in reversed(steps):
        vis = next((v for v in step.visualizations if v.type == 'Array' and v.details.get('name') == table_var_name), None)
        if vis and 'value' in vis.details:
            val = vis.details['value']
            if isinstance(val, list):
                if dimensions == 2 and len(val) > 0 and isinstance(val[0], list):
                    table_shape = [len(val), len(val[0])]
                else:
                    table_shape = [len(val)]
                break
                
    if not table_shape:
        last_locals = {}
        if steps:
            last_locals = steps[-1].locals or {}
        bounds = resolve_loop_bounds(code, last_locals, {})
        if len(bounds) >= dimensions:
            table_shape = bounds[:dimensions]
        else:
            table_shape = [10] * dimensions

    # 2. Add DP_TABLE details to each step
    for curr_idx, step in enumerate(steps):
        eval_locals = {}
        if step.locals:
            for k, v in step.locals.items():
                try:
                    if isinstance(v, str):
                        if v.isdigit():
                            eval_locals[k] = int(v)
                        elif v.startswith('-') and v[1:].isdigit():
                            eval_locals[k] = int(v)
                        else:
                            try:
                                eval_locals[k] = float(v)
                            except ValueError:
                                eval_locals[k] = v
                    else:
                        eval_locals[k] = v
                except Exception:
                    eval_locals[k] = v
                    
        array_vis = next((v for v in step.visualizations if v.type == 'Array' and v.details.get('name') == table_var_name), None)
        if not array_vis:
            continue
            
        array_val = array_vis.details.get('value', [])
        
        node = ast_map.get(step.line_number)
        target = None
        sources = []
        written_val = None
        
        if node and isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for tgt in targets:
                base, idx_nodes = extract_subscript_info(tgt)
                if base == table_var_name:
                    target = []
                    for idx_node in idx_nodes:
                        val = eval_ast_node(idx_node, {}, eval_locals)
                        if isinstance(val, int):
                            target.append(val)
                            
                    rhs = node.value
                    if rhs:
                        for child in ast.walk(rhs):
                            if isinstance(child, ast.Subscript):
                                r_base, r_idx_nodes = extract_subscript_info(child)
                                if r_base == table_var_name:
                                    src = []
                                    for r_idx_node in r_idx_nodes:
                                        r_val = eval_ast_node(r_idx_node, {}, eval_locals)
                                        if isinstance(r_val, int):
                                            src.append(r_val)
                                    if len(src) == len(idx_nodes):
                                        sources.append(src)
                                        
        # Lookahead to get the actual written value from a subsequent step
        if target:
            found_future = False
            try:
                for future_idx in range(curr_idx + 1, len(steps)):
                    future_step = steps[future_idx]
                    future_vis = next((v for v in future_step.visualizations if v.type in ('Array', 'DP_TABLE') and v.details.get('name') == table_var_name), None)
                    if future_vis:
                        future_val = future_vis.details.get('value', [])
                        if len(target) == 1 and target[0] < len(future_val):
                            written_val = future_val[target[0]]
                            array_val = copy.deepcopy(array_val)
                            array_val[target[0]] = written_val
                            found_future = True
                            break
                        elif len(target) == 2 and target[0] < len(future_val) and target[1] < len(future_val[target[0]]):
                            written_val = future_val[target[0]][target[1]]
                            array_val = copy.deepcopy(array_val)
                            array_val[target[0]][target[1]] = written_val
                            found_future = True
                            break
            except Exception:
                pass
                
            if not found_future:
                try:
                    if len(target) == 1 and target[0] < len(array_val):
                        written_val = array_val[target[0]]
                    elif len(target) == 2 and target[0] < len(array_val) and target[1] < len(array_val[target[0]]):
                        written_val = array_val[target[0]][target[1]]
                except Exception:
                    pass

        dp_details = {
            "name": table_var_name,
            "value": copy.deepcopy(array_val),
            "obj_id": array_vis.details.get("obj_id", f"list_{id(array_val)}"),
            "dimensions": dimensions,
            "table_shape": table_shape
        }
        if target is not None:
            dp_details["target"] = target
            dp_details["sources"] = sources
            dp_details["target_value"] = written_val
            
        step.visualizations = [v for v in step.visualizations if v != array_vis]
        step.visualizations.append(VisualizationData(
            type="DP_TABLE",
            details=dp_details
        ))
        
    return steps

# --- Memoization Tracing Engines ---

def get_decorator_line_number(func):
    try:
        frame = sys._getframe(2)
        if frame and frame.f_code.co_filename == "<string>":
            return frame.f_lineno
    except Exception:
        pass
    try:
        return func.__code__.co_firstlineno
    except Exception:
        return 0

class DecoratorMemoTracer:
    def __init__(self):
        self.steps: List[Step] = []
        self.step_counter = 0
        self.call_depth = 0
        
    def add_step(self, event: str, key: str, value=None, line_number=0):
        self.step_counter += 1
        details = {
            "event": event,
            "key": key,
            "call_depth": self.call_depth
        }
        if event == "cache_write":
            details["value"] = value
            
        vis = VisualizationData(
            type="MEMOIZATION",
            details=details
        )
        self.steps.append(Step(
            step_number=self.step_counter,
            line_number=line_number,
            visualizations=[vis],
            event_type="line"
        ))
        
    def make_decorator(self):
        def decorator_wrapper(func):
            cache_store = {}
            def wrapped(*args, **kwargs):
                key = make_key(args, kwargs)
                line_no = get_decorator_line_number(func)
                if key in cache_store:
                    self.call_depth += 1
                    self.add_step("cache_hit", key, line_number=line_no)
                    self.call_depth -= 1
                    return cache_store[key]
                else:
                    self.call_depth += 1
                    self.add_step("call", key, line_number=line_no)
                    res = func(*args, **kwargs)
                    cache_store[key] = res
                    self.add_step("cache_write", key, res, line_number=line_no)
                    self.call_depth -= 1
                    return res
            return wrapped
        return decorator_wrapper

class ManualMemoTracer:
    def __init__(self, func_name: str, cache_var_name: str):
        self.func_name = func_name
        self.cache_var_name = cache_var_name
        self.steps: List[Step] = []
        self.step_counter = 0
        self.call_depth = 0
        self.known_keys = set()
        
    def add_step(self, event: str, key: str, value=None, line_number=0):
        self.step_counter += 1
        details = {
            "event": event,
            "key": key,
            "call_depth": self.call_depth
        }
        if event == "cache_write":
            details["value"] = value
            
        vis = VisualizationData(
            type="MEMOIZATION",
            details=details
        )
        self.steps.append(Step(
            step_number=self.step_counter,
            line_number=line_number,
            visualizations=[vis],
            event_type="line"
        ))
        
    def trace_fn(self, frame, event, arg):
        filename = frame.f_code.co_filename
        if filename != "<string>":
            return None
            
        func_name = frame.f_code.co_name
        if func_name != self.func_name:
            return self.trace_fn
            
        if event == 'call':
            self.call_depth += 1
            param_names = sorted(frame.f_locals.keys())
            args = [frame.f_locals[p] for p in param_names if p not in ('self', 'cls')]
            key = str(args[0]) if len(args) == 1 else str(tuple(args))
            raw_key = args[0] if len(args) == 1 else tuple(args)
            
            memo_val = frame.f_locals.get(self.cache_var_name) or frame.f_globals.get(self.cache_var_name)
            if memo_val is not None and (raw_key in memo_val or key in memo_val):
                self.add_step("cache_hit", key, line_number=frame.f_lineno)
            else:
                self.add_step("call", key, line_number=frame.f_lineno)
                
        elif event == 'return':
            self.check_for_writes(frame)
            self.call_depth -= 1
            
        elif event == 'line':
            self.check_for_writes(frame)
            
        return self.trace_fn

    def check_for_writes(self, frame):
        memo_val = frame.f_locals.get(self.cache_var_name) or frame.f_globals.get(self.cache_var_name)
        if memo_val is not None:
            current_keys = set()
            if isinstance(memo_val, dict):
                current_keys = set(memo_val.keys())
            elif isinstance(memo_val, set):
                current_keys = set(memo_val)
                
            new_keys = current_keys - self.known_keys
            for k in new_keys:
                stringified_k = str(k)
                val = memo_val[k] if isinstance(memo_val, dict) else None
                self.add_step("cache_write", stringified_k, val, line_number=frame.f_lineno)
                self.known_keys.add(k)


def run_decorator_memo_tracer(code: str) -> List[Step]:
    tracer = DecoratorMemoTracer()
    
    mock_functools = types.ModuleType("functools")
    mock_functools.lru_cache = lambda *args, **kwargs: tracer.make_decorator()
    mock_functools.cache = tracer.make_decorator()
    
    def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "functools":
            return mock_functools
        return __builtins__["__import__"](name, globals, locals, fromlist, level)
        
    safe_builtins = {
        "__build_class__": __builtins__["__build_class__"],
        "__import__": mock_import,
        "print": print, "range": range, "len": len, "int": int, "str": str,
        "float": float, "bool": bool, "list": list, "abs": abs, "max": max,
        "min": min, "sum": sum, "True": True, "False": False, "None": None,
        "object": object, "Exception": Exception, "ValueError": ValueError,
        "TypeError": TypeError, "super": super, "isinstance": isinstance,
        "dict": dict, "tuple": tuple, "set": set, "enumerate": enumerate,
        "zip": zip, "map": map, "filter": filter
    }
    
    safe_globals = {
        "__builtins__": safe_builtins,
        "__name__": "__main__",
        "lru_cache": lambda *args, **kwargs: tracer.make_decorator(),
        "cache": tracer.make_decorator()
    }
    
    exec(code, safe_globals, safe_globals)
    return tracer.steps


def run_manual_memo_tracer(code: str, func_name: str, cache_var_name: str) -> List[Step]:
    manual_tracer = ManualMemoTracer(func_name, cache_var_name)
    
    safe_builtins = {
        "__build_class__": __builtins__["__build_class__"],
        "print": print, "range": range, "len": len, "int": int, "str": str,
        "float": float, "bool": bool, "list": list, "abs": abs, "max": max,
        "min": min, "sum": sum, "True": True, "False": False, "None": None,
        "object": object, "Exception": Exception, "ValueError": ValueError,
        "TypeError": TypeError, "super": super, "isinstance": isinstance,
        "dict": dict, "tuple": tuple, "set": set, "enumerate": enumerate,
        "zip": zip, "map": map, "filter": filter
    }
    
    safe_globals = {
        "__builtins__": safe_builtins,
        "__name__": "__main__"
    }
    
    old_trace = sys.gettrace()
    sys.settrace(manual_tracer.trace_fn)
    try:
        exec(code, safe_globals, safe_globals)
    finally:
        sys.settrace(old_trace)
        
    return manual_tracer.steps

# --- Main Runner Interface ---

def run_dp_tracer(code: str) -> List[Step]:
    """
    Unified entrypoint for DP tracing.
    1. Runs the classifiers to check if code is DP.
    2. If memoization is detected, runs specialized memoization tracer.
    3. If tabulation is detected, runs standard tracer first, then post-processes it.
    4. Otherwise, returns None (producing no DP trace output).
    """
    memo_res = classify_memoization(code)
    if memo_res["is_memoization"]:
        if memo_res["cache_type"] == "decorator":
            return run_decorator_memo_tracer(code)
        else:
            # For manual, extract the function name from code AST
            tree = ast.parse(code)
            func_name = None
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_name = node.name
                    break
            if func_name and memo_res["cache_var_name"]:
                return run_manual_memo_tracer(code, func_name, memo_res["cache_var_name"])
                
    tab_res = classify_tabulation(code)
    if tab_res["is_tabulation"]:
        from tracer import Tracer
        standard_tracer = Tracer()
        standard_steps = standard_tracer.run_code(code)
        return post_process_tabulation(
            standard_steps,
            code,
            tab_res["table_var_name"],
            tab_res["dimensions"]
        )
        
    return None
