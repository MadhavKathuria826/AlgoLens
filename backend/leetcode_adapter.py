import ast

def detect_entry_point(code: str) -> dict:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {"has_invocation": True}
        
    # Check for top level call
    class TopLevelCallVisitor(ast.NodeVisitor):
        def __init__(self):
            self.has_call = False
            
        def visit_Call(self, node):
            self.has_call = True
            
        def visit_FunctionDef(self, node):
            pass # ignore calls inside functions
            
        def visit_ClassDef(self, node):
            pass # ignore calls inside classes

    visitor = TopLevelCallVisitor()
    visitor.visit(tree)
    if visitor.has_call:
        return {"has_invocation": True}

    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    
    if classes:
        target_class = classes[-1]
        methods = [n for n in target_class.body if isinstance(n, ast.FunctionDef) and not n.name.startswith('_')]
        
        if len(methods) > 1:
            return {
                "has_invocation": False,
                "is_ambiguous": True,
                "candidates": [m.name for m in methods],
                "class_name": target_class.name
            }
        elif len(methods) == 1:
            m = methods[0]
            # Note: default-valued params are currently treated as required.
            # Deferring UX handling for optional params for now.
            params = [a.arg for a in m.args.args if a.arg != 'self']
            return {
                "has_invocation": False,
                "is_ambiguous": False,
                "target": m.name,
                "params": params,
                "is_class": True,
                "class_name": target_class.name
            }
            
    if funcs:
        target_func = funcs[-1]
        # Note: default-valued params are currently treated as required.
        # Deferring UX handling for optional params for now.
        params = [a.arg for a in target_func.args.args]
        return {
            "has_invocation": False,
            "is_ambiguous": False,
            "target": target_func.name,
            "params": params,
            "is_class": False,
            "class_name": None
        }
        
    return {"has_invocation": True}

def build_driver_code(entry_info: dict, test_case_literals: str) -> str:
    lines = test_case_literals.strip().split('\n')
    valid_driver_lines = []
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        try:
            stmt = ast.parse(line).body[0]
            if not isinstance(stmt, ast.Assign):
                raise ValueError("Only assignments are allowed in test cases.")
            ast.literal_eval(stmt.value)
            valid_driver_lines.append(line)
        except Exception as e:
            raise ValueError(f"Invalid test case line '{line}': {e}")
            
    params = entry_info.get("params", [])
    param_str = ", ".join(params)
    
    if entry_info.get("is_class"):
        call_str = f"result = {entry_info['class_name']}().{entry_info['target']}({param_str})"
    else:
        call_str = f"result = {entry_info['target']}({param_str})"
        
    valid_driver_lines.append(call_str)
    
    return "\n" + "\n".join(valid_driver_lines)
