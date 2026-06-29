import ast

def validate_code(code: str):
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"Syntax Error: {e.msg} at line {e.lineno}")
        
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name != 'heapq':
                    raise ValueError(f"Importing '{alias.name}' is not allowed. Only 'heapq' is permitted.")
        elif isinstance(node, ast.AsyncFunctionDef) or isinstance(node, ast.Await):
            raise ValueError("Async operations are not supported in Phase 1.")
