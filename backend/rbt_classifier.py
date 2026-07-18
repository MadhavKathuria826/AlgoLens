import ast

def classify_rbt(code: str) -> dict:
    try:
        tree = ast.parse(code)
    except Exception:
        return {"is_rbt": False, "confidence": 0.0, "node_class_name": None}

    has_color = False
    has_fixup = False
    node_class_name = None

    class RBTVisitor(ast.NodeVisitor):
        def visit_ClassDef(self, node):
            nonlocal has_color, node_class_name
            # Look for self.color assignment inside class methods
            for child in ast.walk(node):
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        if isinstance(target, ast.Attribute):
                            if isinstance(target.value, ast.Name) and target.value.id == 'self':
                                if target.attr == 'color':
                                    has_color = True
                                    node_class_name = node.name
            self.generic_visit(node)

        def visit_FunctionDef(self, node):
            nonlocal has_fixup
            name_lower = node.name.lower()
            if any(term in name_lower for term in ('fixup', 'rebalance', 'insert_fixup', 'delete_fixup', 'color_flip', 'flip_colors')):
                has_fixup = True
            self.generic_visit(node)

    visitor = RBTVisitor()
    visitor.visit(tree)

    is_rbt = has_color or (has_color and has_fixup)
    
    return {
        "is_rbt": is_rbt,
        "confidence": 1.0 if is_rbt else 0.0,
        "node_class_name": node_class_name
    }
