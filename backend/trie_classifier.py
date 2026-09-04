import ast

def classify_trie(code: str) -> dict:
    """
    AST Classifier for Trie (Prefix Tree) structures.
    Detects classes and methods representing Trie or TrieNode.
    """
    try:
        tree = ast.parse(code)
    except Exception:
        return {"is_trie": False, "confidence": 0.0, "node_class_name": None}

    has_trie_class = False
    has_children = False
    has_trie_methods = False
    node_class_name = None

    class TrieVisitor(ast.NodeVisitor):
        def visit_ClassDef(self, node):
            nonlocal has_trie_class, has_children, node_class_name
            name_lower = node.name.lower()
            if 'trie' in name_lower or 'prefix' in name_lower:
                has_trie_class = True
                node_class_name = node.name

            # Look for self.children or self.is_end_of_word / is_word assignments inside class
            for child in ast.walk(node):
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        if isinstance(target, ast.Attribute):
                            if isinstance(target.value, ast.Name) and target.value.id == 'self':
                                attr = target.attr.lower()
                                if attr in ('children', 'child', 'nodes', 'is_end_of_word', 'is_word', 'isend', 'end'):
                                    has_children = True
                                    if not node_class_name:
                                        node_class_name = node.name
            self.generic_visit(node)

        def visit_FunctionDef(self, node):
            nonlocal has_trie_methods
            name_lower = node.name.lower()
            if any(m in name_lower for m in ('insert', 'startswith', 'starts_with', 'search_prefix')):
                has_trie_methods = True
            self.generic_visit(node)

    visitor = TrieVisitor()
    visitor.visit(tree)

    is_trie = (has_trie_class or has_children) and (has_trie_methods or has_children)

    return {
        "is_trie": is_trie,
        "confidence": 1.0 if is_trie else 0.0,
        "node_class_name": node_class_name
    }
