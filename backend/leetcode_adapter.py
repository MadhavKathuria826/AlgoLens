import ast
import re

def get_annotation_type(node) -> str:
    if not node:
        return None
    try:
        source = ast.unparse(node)
        if "TreeNode" in source:
            return "TreeNode"
        elif "ListNode" in source:
            return "ListNode"
    except Exception:
        pass
    return None

def preprocess_test_case(test_case_literals: str) -> str:
    # Safe regex token replacement for null, true, false
    processed = re.sub(r'\bnull\b', 'None', test_case_literals)
    processed = re.sub(r'\btrue\b', 'True', processed)
    processed = re.sub(r'\bfalse\b', 'False', processed)
    return processed

def detect_entry_point(code: str, selected_method: str = None) -> dict:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {"has_invocation": True}
        
    class TopLevelCallVisitor(ast.NodeVisitor):
        def __init__(self):
            self.has_call = False
        def visit_Call(self, node):
            self.has_call = True
        def visit_FunctionDef(self, node):
            pass
        def visit_ClassDef(self, node):
            pass

    visitor = TopLevelCallVisitor()
    visitor.visit(tree)
    if visitor.has_call:
        return {"has_invocation": True}

    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    
    if classes:
        target_class = classes[-1]
        methods = [n for n in target_class.body if isinstance(n, ast.FunctionDef) and not n.name.startswith('_')]
        
        if len(methods) > 1 and not selected_method:
            return {
                "has_invocation": False,
                "is_ambiguous": True,
                "candidates": [m.name for m in methods],
                "class_name": target_class.name
            }
        
        m = None
        if selected_method and selected_method in [meth.name for meth in methods]:
            m = next(meth for meth in methods if meth.name == selected_method)
        elif len(methods) == 1:
            m = methods[0]
            
        if m:
            params = [a.arg for a in m.args.args if a.arg != 'self']
            param_types = {}
            for a in m.args.args:
                if a.arg == 'self':
                    continue
                t = get_annotation_type(a.annotation)
                if t:
                    param_types[a.arg] = t
                elif a.arg == 'root':
                    param_types[a.arg] = 'TreeNode'
                elif a.arg == 'head':
                    param_types[a.arg] = 'ListNode'
            return {
                "has_invocation": False,
                "is_ambiguous": False,
                "target": m.name,
                "params": params,
                "param_types": param_types,
                "is_class": True,
                "class_name": target_class.name
            }
            
    if funcs:
        target_func = funcs[-1]
        params = [a.arg for a in target_func.args.args]
        param_types = {}
        for a in target_func.args.args:
            t = get_annotation_type(a.annotation)
            if t:
                param_types[a.arg] = t
            elif a.arg == 'root':
                param_types[a.arg] = 'TreeNode'
            elif a.arg == 'head':
                param_types[a.arg] = 'ListNode'
        return {
            "has_invocation": False,
            "is_ambiguous": False,
            "target": target_func.name,
            "params": params,
            "param_types": param_types,
            "is_class": False,
            "class_name": None
        }
        
    return {"has_invocation": True}

def build_driver_code(entry_info: dict, test_case_literals: str) -> str:
    test_case_literals = preprocess_test_case(test_case_literals)
    lines = test_case_literals.strip().split('\n')
    valid_driver_lines = []
    assigned_vars = {}
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        try:
            stmt = ast.parse(line).body[0]
            if not isinstance(stmt, ast.Assign):
                raise ValueError("Only assignments are allowed in test cases.")
            ast.literal_eval(stmt.value)
            
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    assigned_vars[target.id] = line
                    
            valid_driver_lines.append(line)
        except Exception as e:
            raise ValueError(f"Invalid test case line '{line}': {e}")
            
    param_types = entry_info.get("param_types", {})
    for p, p_type in param_types.items():
        if p in assigned_vars:
            if p_type == 'TreeNode':
                valid_driver_lines.append(f"{p} = _deserialize_tree({p})")
            elif p_type == 'ListNode':
                valid_driver_lines.append(f"{p} = _deserialize_list({p})")
                
    params = entry_info.get("params", [])
    param_str = ", ".join(params)
    
    if entry_info.get("is_class"):
        call_str = f"result = {entry_info['class_name']}().{entry_info['target']}({param_str})"
    else:
        call_str = f"result = {entry_info['target']}({param_str})"
        
    valid_driver_lines.append(call_str)
    
    return "\n" + "\n".join(valid_driver_lines)
