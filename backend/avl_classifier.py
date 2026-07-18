import ast

def classify_avl(code: str) -> dict:
    try:
        tree = ast.parse(code)
    except Exception:
        return {"is_avl": False, "confidence": 0.0, "node_class_name": None}

    has_height = False
    has_rotation = False
    has_delete = False
    node_class_name = None

    class AVLVisitor(ast.NodeVisitor):
        def visit_ClassDef(self, node):
            nonlocal has_height, node_class_name
            # Look for self.height assignment inside class methods
            for child in ast.walk(node):
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        if isinstance(target, ast.Attribute):
                            if isinstance(target.value, ast.Name) and target.value.id == 'self':
                                if target.attr == 'height':
                                    has_height = True
                                    node_class_name = node.name
            self.generic_visit(node)

        def visit_FunctionDef(self, node):
            nonlocal has_rotation, has_delete
            name_lower = node.name.lower()
            if any(term in name_lower for term in ('rotate', 'rebalance', 'balancefactor', 'getheight', 'get_height')):
                has_rotation = True
            if any(term in name_lower for term in ('delete', 'remove')):
                has_delete = True
            self.generic_visit(node)

    visitor = AVLVisitor()
    visitor.visit(tree)

    is_avl = has_height or has_rotation
    
    return {
        "is_avl": is_avl,
        "confidence": 1.0 if is_avl else 0.0,
        "node_class_name": node_class_name,
        "has_delete": has_delete
    }
