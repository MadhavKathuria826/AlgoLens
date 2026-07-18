import ast

def extract_names(node):
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        names = set()
        for elt in node.elts:
            names.update(extract_names(elt))
        return names
    return set()

def extract_subscript_info(node):
    if not isinstance(node, ast.Subscript):
        return None, []
    
    # Check if nested subscript (e.g. dp[i][j])
    if isinstance(node.value, ast.Subscript):
        base_name, indices = extract_subscript_info(node.value)
        if base_name:
            if isinstance(node.slice, ast.Tuple):
                indices.extend(node.slice.elts)
            else:
                indices.append(node.slice)
            return base_name, indices
            
    if isinstance(node.value, ast.Name):
        base_name = node.value.id
        if isinstance(node.slice, ast.Tuple):
            indices = list(node.slice.elts)
        else:
            indices = [node.slice]
        return base_name, indices
        
    return None, []

def references_any_names(node, target_names):
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id in target_names:
            return True
    return False

def references_params(node, param_names):
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id in param_names:
            return True
    return False

def is_recursive_call(call_node, func_name):
    if isinstance(call_node.func, ast.Name) and call_node.func.id == func_name:
        return True
    if isinstance(call_node.func, ast.Attribute) and isinstance(call_node.func.value, ast.Name) and call_node.func.value.id == 'self' and call_node.func.attr == func_name:
        return True
    return False

def has_cache_decorator(func_node):
    for dec in func_node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id in ('cache', 'lru_cache'):
            return True
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id in ('cache', 'lru_cache'):
            return True
        if isinstance(dec, ast.Attribute) and isinstance(dec.value, ast.Name) and dec.value.id == 'functools' and dec.attr in ('cache', 'lru_cache'):
            return True
        if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and isinstance(dec.func.value, ast.Name) and dec.func.value.id == 'functools' and dec.func.attr in ('cache', 'lru_cache'):
            return True
    return False

def find_cache_var_in_lookup(test_node):
    if isinstance(test_node, ast.Compare):
        if len(test_node.ops) == 1 and isinstance(test_node.ops[0], (ast.In, ast.NotIn)):
            right = test_node.comparators[0]
            if isinstance(right, ast.Name):
                return right.id
            if isinstance(right, ast.Attribute) and isinstance(right.value, ast.Name) and right.value.id == 'self':
                return f"self.{right.attr}"
    if isinstance(test_node, ast.Call) and isinstance(test_node.func, ast.Attribute) and test_node.func.attr == 'get':
        val = test_node.func.value
        if isinstance(val, ast.Name):
            return val.id
        if isinstance(val, ast.Attribute) and isinstance(val.value, ast.Name) and val.value.id == 'self':
            return f"self.{val.attr}"
    if isinstance(test_node, ast.BoolOp):
        for val in test_node.values:
            var = find_cache_var_in_lookup(val)
            if var:
                return var
    return None

def get_memo_lookup_var(func_node):
    for stmt in func_node.body[:4]:
        if isinstance(stmt, ast.If):
            var = find_cache_var_in_lookup(stmt.test)
            if var:
                return var
    return None

def has_cache_write(func_node, cache_var_name):
    for child in ast.walk(func_node):
        if isinstance(child, (ast.Assign, ast.AnnAssign)):
            targets = child.targets if isinstance(child, ast.Assign) else [child.target]
            for target in targets:
                if isinstance(target, ast.Subscript):
                    base, _ = extract_subscript_info(target)
                    if base == cache_var_name or (cache_var_name.startswith('self.') and isinstance(target.value, ast.Attribute) and f"self.{target.value.attr}" == cache_var_name):
                        return True
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and child.func.attr == 'add':
            val = child.func.value
            if isinstance(val, ast.Name) and val.id == cache_var_name:
                return True
            if isinstance(val, ast.Attribute) and isinstance(val.value, ast.Name) and val.value.id == 'self' and f"self.{val.attr}" == cache_var_name:
                return True
    return False

def is_backtracking_cache(func_node, cache_var_name):
    for child in ast.walk(func_node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and child.func.attr in ('remove', 'discard', 'pop', 'delete'):
            val = child.func.value
            if isinstance(val, ast.Name) and val.id == cache_var_name:
                return True
            if isinstance(val, ast.Attribute) and isinstance(val.value, ast.Name) and val.value.id == 'self' and f"self.{val.attr}" == cache_var_name:
                return True
        if isinstance(child, ast.Delete):
            for target in child.targets:
                if isinstance(target, ast.Subscript):
                    base, _ = extract_subscript_info(target)
                    if base == cache_var_name or (cache_var_name.startswith('self.') and isinstance(target.value, ast.Attribute) and f"self.{target.value.attr}" == cache_var_name):
                        return True
    return False

def classify_tabulation(code: str):
    try:
        tree = ast.parse(code)
    except Exception:
        return {"is_tabulation": False, "dimensions": 1, "confidence": 0.0, "table_var_name": "", "recurrence_relations": []}
        
    class TabulationVisitor(ast.NodeVisitor):
        def __init__(self):
            self.loop_vars = []
            self.found = False
            self.dimensions = 1
            self.confidence = 0.0
            self.table_var_name = ""
            self.recurrence_lines = []
            
        def visit_For(self, node):
            names = extract_names(node.target)
            self.loop_vars.append(names)
            self.generic_visit(node)
            self.loop_vars.pop()
            
        def visit_While(self, node):
            names = set()
            for child in ast.walk(node.test):
                if isinstance(child, ast.Name):
                    names.add(child.id)
            self.loop_vars.append(names)
            self.generic_visit(node)
            self.loop_vars.pop()
            
        def visit_Assign(self, node):
            self.check_assignment(node.targets, node.value)
            self.generic_visit(node)
            
        def visit_AnnAssign(self, node):
            if node.value:
                self.check_assignment([node.target], node.value)
            self.generic_visit(node)
            
        def check_assignment(self, targets, value):
            all_active_loop_vars = set()
            for s in self.loop_vars:
                all_active_loop_vars.update(s)
                
            if not all_active_loop_vars:
                return
                
            for target in targets:
                base_name, lhs_indices = extract_subscript_info(target)
                if not base_name or not lhs_indices:
                    continue
                    
                lhs_indexed_by_loop = any(references_any_names(idx, all_active_loop_vars) for idx in lhs_indices)
                if not lhs_indexed_by_loop:
                    continue
                    
                rhs_subscripts = []
                for child in ast.walk(value):
                    if isinstance(child, ast.Subscript):
                        r_name, r_indices = extract_subscript_info(child)
                        if r_name == base_name:
                            rhs_subscripts.append((child, r_indices))
                            
                if rhs_subscripts:
                    for r_node, rhs_indices in rhs_subscripts:
                        if len(rhs_indices) != len(lhs_indices):
                            continue
                        
                        is_diff = False
                        for lhs_idx, rhs_idx in zip(lhs_indices, rhs_indices):
                            try:
                                lhs_str = ast.unparse(lhs_idx).strip()
                                rhs_str = ast.unparse(rhs_idx).strip()
                                if lhs_str != rhs_str:
                                    is_diff = True
                            except Exception:
                                pass
                                
                        if is_diff:
                            self.found = True
                            self.table_var_name = base_name
                            self.dimensions = min(2, len(lhs_indices))
                            self.confidence = 1.0
                            try:
                                recurrence_str = ast.unparse(target).strip() + " = " + ast.unparse(value).strip()
                                if recurrence_str not in self.recurrence_lines:
                                    self.recurrence_lines.append(recurrence_str)
                            except Exception:
                                pass
                            return

    visitor = TabulationVisitor()
    visitor.visit(tree)
    return {
        "is_tabulation": visitor.found,
        "dimensions": visitor.dimensions,
        "confidence": visitor.confidence,
        "table_var_name": visitor.table_var_name,
        "recurrence_relations": visitor.recurrence_lines
    }

def classify_memoization(code: str):
    try:
        tree = ast.parse(code)
    except Exception:
        return {"is_memoization": False, "cache_type": "decorator", "confidence": 0.0, "cache_var_name": None, "recurrence_relations": []}
        
    class MemoizationVisitor(ast.NodeVisitor):
        def __init__(self):
            self.found = False
            self.cache_type = "decorator"
            self.confidence = 0.0
            self.cache_var_name = None
            self.recurrence_lines = []
            
        def visit_FunctionDef(self, node):
            func_name = node.name
            
            # g. Extract recurrence lines (return statements with recursive calls)
            for child in ast.walk(node):
                if isinstance(child, ast.Return) and child.value:
                    has_rec = False
                    for sub in ast.walk(child.value):
                        if isinstance(sub, ast.Call) and is_recursive_call(sub, func_name):
                            has_rec = True
                            break
                    if has_rec:
                        try:
                            rec_str = ast.unparse(child).strip()
                            if rec_str not in self.recurrence_lines:
                                self.recurrence_lines.append(rec_str)
                        except Exception:
                            pass

            if self.found:
                return
                
            param_names = {arg.arg for arg in node.args.args if arg.arg not in ('self', 'cls')}
            
            # a. Check recursion
            has_recursion = False
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    if is_recursive_call(child, func_name):
                        has_recursion = True
                        break
                        
            # b. Check cache decorator
            decorator_cache = has_cache_decorator(node)
            
            if decorator_cache:
                self.found = has_recursion
                self.cache_type = "decorator"
                self.confidence = 1.0 if has_recursion else 0.0
                self.cache_var_name = None
                return
                
            # c. Check manual lookup
            lookup_var = get_memo_lookup_var(node)
            
            if lookup_var:
                # d. Check if lookup key references params
                key_references_params = False
                for child in ast.walk(node):
                    if isinstance(child, ast.If):
                        var = find_cache_var_in_lookup(child.test)
                        if var == lookup_var:
                            if isinstance(child.test, ast.Compare):
                                if references_params(child.test.left, param_names):
                                    key_references_params = True
                            elif isinstance(child.test, ast.Call) and child.test.args:
                                if references_params(child.test.args[0], param_names):
                                    key_references_params = True
                            elif isinstance(child.test, ast.BoolOp):
                                for val in child.test.values:
                                    if isinstance(val, ast.Compare) and references_params(val.left, param_names):
                                        key_references_params = True
                                    elif isinstance(val, ast.Call) and val.args and references_params(val.args[0], param_names):
                                        key_references_params = True
                                        
                # e. Check if there's a cache write
                write_present = has_cache_write(node, lookup_var)
                
                # f. Check backtracking
                backtracking = is_backtracking_cache(node, lookup_var)
                
                # Verify write type
                has_set_write = False
                for child in ast.walk(node):
                    if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and child.func.attr == 'add':
                        val = child.func.value
                        if isinstance(val, ast.Name) and val.id == lookup_var:
                            has_set_write = True
                        elif isinstance(val, ast.Attribute) and isinstance(val.value, ast.Name) and val.value.id == 'self' and val.attr == lookup_var.split('.')[-1]:
                            has_set_write = True
                            
                c_type = "manual_set" if has_set_write else "manual_dict"
                
                signals = [has_recursion, lookup_var is not None, write_present, key_references_params, not backtracking]
                matched_count = sum(1 for s in signals if s)
                
                if matched_count == 5:
                    self.found = True
                    self.cache_type = c_type
                    self.confidence = 1.0
                    self.cache_var_name = lookup_var
                    return
                elif matched_count >= 3:
                    self.confidence = max(self.confidence, 0.2 * matched_count)
                    
            self.generic_visit(node)

    visitor = MemoizationVisitor()
    visitor.visit(tree)
    return {
        "is_memoization": visitor.found,
        "cache_type": visitor.cache_type,
        "confidence": visitor.confidence,
        "cache_var_name": visitor.cache_var_name,
        "recurrence_relations": visitor.recurrence_lines
    }
