import os
import sys
import ctypes.util
from clang.cindex import Index, CursorKind, TypeKind, Config

def configure_libclang():
    if Config().library_file or Config().library_path:
        return
    try:
        import clang.native
        native_dir = os.path.dirname(clang.native.__file__)
        for fname in ('libclang.so', 'libclang.so.1', 'libclang.dll', 'libclang.dylib'):
            fpath = os.path.join(native_dir, fname)
            if os.path.exists(fpath):
                Config.set_library_file(fpath)
                return
    except Exception:
        pass
    for p in sys.path:
        for sub in ('clang/native', 'libclang/native', 'libclang'):
            native_dir = os.path.join(p, sub)
            if os.path.isdir(native_dir):
                for fname in ('libclang.so', 'libclang.so.1', 'libclang.dll', 'libclang.dylib'):
                    fpath = os.path.join(native_dir, fname)
                    if os.path.exists(fpath):
                        Config.set_library_file(fpath)
                        return
    linux_paths = [
        '/usr/lib/x86_64-linux-gnu/libclang.so',
        '/usr/lib/x86_64-linux-gnu/libclang.so.1',
        '/usr/lib/llvm-14/lib/libclang.so',
        '/usr/lib/llvm-13/lib/libclang.so',
        '/usr/lib/llvm-12/lib/libclang.so',
        '/usr/lib/libclang.so',
    ]
    for lp in linux_paths:
        if os.path.exists(lp):
            Config.set_library_file(lp)
            return
    found = ctypes.util.find_library('clang') or ctypes.util.find_library('clang-14') or ctypes.util.find_library('clang-13')
    if found:
        try:
            Config.set_library_file(found)
            return
        except Exception:
            pass

configure_libclang()

DEFAULT_HEADER_MOCKS = """
namespace std {
    struct string {};
    template<typename T>
    struct vector {
        T& operator[](int idx);
        int size();
        void push_back(const T& val);
        bool empty();
    };
    template<typename T>
    struct stack {
        void push(const T& val);
        void pop();
        T& top();
        bool empty();
        int size();
    };
    template<typename T>
    struct queue {
        void push(const T& val);
        void pop();
        T& front();
        T& back();
        bool empty();
        int size();
    };
    template<typename K, typename V>
    struct map {
        V& operator[](const K& key);
        int count(const K& key);
        void erase(const K& key);
        int size();
        bool empty();
    };
    template<typename K, typename V>
    struct unordered_map {
        V& operator[](const K& key);
        int count(const K& key);
        void erase(const K& key);
        int size();
        bool empty();
    };
    template<typename T>
    struct set {
        void insert(const T& val);
        void erase(const T& val);
        int count(const T& val);
        int size();
        bool empty();
    };
    template<typename T>
    struct unordered_set {
        void insert(const T& val);
        void erase(const T& val);
        int count(const T& val);
        int size();
        bool empty();
    };
}
"""

def parse_cpp_ast(code: str, use_header_mocks: bool = True):
    index = Index.create()
    full_code = (DEFAULT_HEADER_MOCKS + "\n" + code) if use_header_mocks else code
    tu = index.parse('test.cpp', unsaved_files=[('test.cpp', full_code)])
    header_lines_count = len(DEFAULT_HEADER_MOCKS.splitlines()) if use_header_mocks else 0
    return tu, header_lines_count

def find_decl_ref(cursor):
    if cursor.kind == CursorKind.DECL_REF_EXPR:
        return cursor
    for child in cursor.get_children():
        ref = find_decl_ref(child)
        if ref:
            return ref
    return None

def find_all_decl_refs(cursor):
    refs = []
    if cursor.kind == CursorKind.DECL_REF_EXPR:
        refs.append(cursor.spelling)
    for child in cursor.get_children():
        refs.extend(find_all_decl_refs(child))
    return refs

def find_all_var_decls(cursor):
    decls = []
    if cursor.kind == CursorKind.VAR_DECL:
        decls.append(cursor.spelling)
    for child in cursor.get_children():
        decls.extend(find_all_var_decls(child))
    return decls

def get_subscript_info(cursor):
    """
    Returns (base_name, index_expr_cursor) if cursor represents a subscript access.
    Otherwise returns None.
    """
    if cursor.kind == CursorKind.ARRAY_SUBSCRIPT_EXPR:
        children = list(cursor.get_children())
        if len(children) >= 2:
            base_ref = find_decl_ref(children[0])
            if base_ref:
                return base_ref.spelling, children[1]
    elif cursor.kind == CursorKind.CALL_EXPR and cursor.spelling == 'operator[]':
        children = list(cursor.get_children())
        if len(children) >= 3:
            base_ref = find_decl_ref(children[0])
            if base_ref:
                return base_ref.spelling, children[2]
    return None

def extract_index_expr(cursor):
    """
    Returns (var_name, offset_int) if it is a simple variable or variable +/- offset.
    Otherwise returns (None, 0).
    """
    ref = find_decl_ref(cursor)
    if cursor.kind == CursorKind.DECL_REF_EXPR:
        return cursor.spelling, 0
    
    if cursor.kind == CursorKind.BINARY_OPERATOR:
        children = list(cursor.get_children())
        if len(children) == 2:
            left_ref = find_decl_ref(children[0])
            if left_ref and children[1].kind == CursorKind.INTEGER_LITERAL:
                var_name = left_ref.spelling
                lit_val = 0
                tokens = list(children[1].get_tokens())
                if tokens:
                    try:
                        lit_val = int(tokens[0].spelling)
                    except ValueError:
                        pass
                
                op = None
                for t in cursor.get_tokens():
                    if t.spelling in ('+', '-'):
                        op = t.spelling
                        break
                
                if op == '-':
                    return var_name, -lit_val
                elif op == '+':
                    return var_name, lit_val
                
    for child in cursor.get_children():
        var_name, offset = extract_index_expr(child)
        if var_name:
            return var_name, offset
            
    return None, 0

def is_self_pointer_field(field_cursor, parent_name):
    t_sp = field_cursor.type.spelling
    if '*' in t_sp and parent_name in t_sp:
        return True
    for child in field_cursor.get_children():
        if child.kind == CursorKind.TYPE_REF:
            if parent_name in child.spelling:
                return True
    return False

def classify_tabulation(code: str) -> dict:
    try:
        index = Index.create()
        header_mocks = """
namespace std {
    template<typename T>
    struct vector {
        T& operator[](int idx);
        int size();
    };
    template<typename T, unsigned long long N>
    struct array {
        T& operator[](int idx);
        int size();
    };
}
"""
        full_code = header_mocks + "\n" + code
        tu = index.parse('test.cpp', unsaved_files=[('test.cpp', full_code)])
    except Exception:
        return {"is_tabulation": False, "dimensions": 1, "confidence": 0.0, "table_var_name": "", "recurrence_relations": []}
        
    loop_vars_stack = []
    found_tabulation = False
    table_var_name = ""
    dimensions = 1
    recurrence_relations = []
    
    def references_any_names(cursor, names):
        for ref in find_all_decl_refs(cursor):
            if ref in names:
                return True
        return False

    def get_subscript_dimensions(cursor):
        dims = 0
        curr = cursor
        while curr:
            sub = get_subscript_info(curr)
            if sub:
                dims += 1
                children = list(curr.get_children())
                if children:
                    curr = children[0]
                else:
                    break
            else:
                break
        return max(1, dims)

    def check_assignment(lhs, rhs, active_loop_vars, original_lines):
        nonlocal found_tabulation, table_var_name, dimensions
        
        sub_info = get_subscript_info(lhs)
        if not sub_info:
            return
        
        base_name, lhs_index_node = sub_info
        
        if not references_any_names(lhs_index_node, active_loop_vars):
            return
            
        rhs_subscripts = []
        def collect_rhs_subscripts(cursor):
            s_info = get_subscript_info(cursor)
            if s_info and s_info[0] == base_name:
                rhs_subscripts.append(s_info[1])
            for child in cursor.get_children():
                collect_rhs_subscripts(child)
                
        collect_rhs_subscripts(rhs)
        
        if not rhs_subscripts:
            return
            
        lhs_var, lhs_offset = extract_index_expr(lhs_index_node)
        
        has_offset_diff = False
        for rhs_idx_node in rhs_subscripts:
            rhs_var, rhs_offset = extract_index_expr(rhs_idx_node)
            if lhs_var == rhs_var and lhs_offset != rhs_offset:
                has_offset_diff = True
                break
                
        if has_offset_diff:
            found_tabulation = True
            table_var_name = base_name
            dimensions = get_subscript_dimensions(lhs)
            
            header_lines_count = len(full_code.splitlines()) - len(original_lines)
            start_line = lhs.extent.start.line - header_lines_count - 1
            end_line = rhs.extent.end.line - header_lines_count - 1
            
            if 0 <= start_line < len(original_lines):
                src_line = "\n".join(original_lines[start_line:end_line + 1]).strip()
                if src_line and src_line not in recurrence_relations:
                    recurrence_relations.append(src_line)

    original_lines = code.splitlines()

    def visit(cursor):
        if cursor.kind in (CursorKind.FOR_STMT, CursorKind.WHILE_STMT, CursorKind.DO_STMT):
            children = list(cursor.get_children())
            loop_vars = set()
            if children:
                for child in children[:3]:
                    loop_vars.update(find_all_var_decls(child))
                    loop_vars.update(find_all_decl_refs(child))
            
            loop_vars_stack.append(loop_vars)
            for child in cursor.get_children():
                visit(child)
            loop_vars_stack.pop()
            
        elif cursor.kind == CursorKind.BINARY_OPERATOR:
            tokens = list(cursor.get_tokens())
            is_assignment = any(t.spelling == '=' for t in tokens)
            if is_assignment:
                children = list(cursor.get_children())
                if len(children) >= 2:
                    active_loop_vars = set()
                    for lv in loop_vars_stack:
                        active_loop_vars.update(lv)
                    check_assignment(children[0], children[1], active_loop_vars, original_lines)
            for child in cursor.get_children():
                visit(child)
        else:
            for child in cursor.get_children():
                visit(child)

    visit(tu.cursor)
    
    return {
        "is_tabulation": found_tabulation,
        "dimensions": dimensions,
        "confidence": 1.0 if found_tabulation else 0.0,
        "table_var_name": table_var_name,
        "recurrence_relations": recurrence_relations
    }

def classify_memoization(code: str) -> dict:
    try:
        index = Index.create()
        header_mocks = """
namespace std {
    template<typename K, typename V>
    struct map {
        V& operator[](const K& key);
        int count(const K& key);
    };
    template<typename K, typename V>
    struct unordered_map {
        V& operator[](const K& key);
        int count(const K& key);
    };
    template<typename T>
    struct vector {
        T& operator[](int idx);
        int size();
    };
}
"""
        full_code = header_mocks + "\n" + code
        tu = index.parse('test.cpp', unsaved_files=[('test.cpp', full_code)])
    except Exception:
        return {"is_memoization": False, "cache_type": "manual", "confidence": 0.0, "cache_var_name": "", "recurrence_relations": []}

    original_lines = code.splitlines()
    header_lines_count = len(full_code.splitlines()) - len(original_lines)

    is_memo = False
    cache_var_name = ""
    recurrence_relations = []
    
    def is_recursive_call(cursor, func_name):
        return cursor.kind == CursorKind.CALL_EXPR and cursor.spelling == func_name

    for child in tu.cursor.get_children():
        if child.kind in (CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD):
            if child.location.file and child.location.file.name == 'test.cpp':
                func_name = child.spelling
                
                has_rec = False
                rec_calls = []
                def find_rec_calls(c):
                    if is_recursive_call(c, func_name):
                        rec_calls.append(c)
                    for ch in c.get_children():
                        find_rec_calls(ch)
                find_rec_calls(child)
                has_rec = len(rec_calls) > 0
                
                if not has_rec:
                    continue
                    
                cache_candidates = set()
                
                def find_cache_writes(c):
                    if c.kind == CursorKind.BINARY_OPERATOR:
                        tokens = list(c.get_tokens())
                        if any(t.spelling == '=' for t in tokens):
                            children = list(c.get_children())
                            if children:
                                sub = get_subscript_info(children[0])
                                if sub:
                                    cache_candidates.add(sub[0])
                    for ch in c.get_children():
                        find_cache_writes(ch)
                find_cache_writes(child)
                
                has_lookup = False
                detected_cache_var = ""
                def find_lookups(c):
                    nonlocal has_lookup, detected_cache_var
                    if c.kind == CursorKind.IF_STMT:
                        children = list(c.get_children())
                        if children:
                            cond = children[0]
                            for ref in find_all_decl_refs(cond):
                                if ref in cache_candidates:
                                    has_lookup = True
                                    detected_cache_var = ref
                                    break
                    for ch in c.get_children():
                        find_lookups(ch)
                find_lookups(child)
                
                def extract_recurrence_lines(c):
                    contains_rec = False
                    for sub in rec_calls:
                        if sub.extent.start.line >= c.extent.start.line and sub.extent.end.line <= c.extent.end.line:
                            contains_rec = True
                            break
                            
                    if contains_rec:
                        if c.kind in (CursorKind.RETURN_STMT, CursorKind.DECL_STMT, CursorKind.BINARY_OPERATOR):
                            start_line = c.extent.start.line - header_lines_count - 1
                            end_line = c.extent.end.line - header_lines_count - 1
                            if 0 <= start_line < len(original_lines):
                                src_line = "\n".join(original_lines[start_line:end_line + 1]).strip()
                                if src_line and src_line not in recurrence_relations:
                                    recurrence_relations.append(src_line)
                                return
                        for ch in c.get_children():
                            extract_recurrence_lines(ch)
                            
                extract_recurrence_lines(child)
                
                if has_rec and (has_lookup or len(cache_candidates) > 0):
                    is_memo = True
                    cache_var_name = detected_cache_var or (list(cache_candidates)[0] if cache_candidates else "")

    return {
        "is_memoization": is_memo,
        "cache_type": "manual",
        "confidence": 1.0 if is_memo else 0.0,
        "cache_var_name": cache_var_name,
        "recurrence_relations": recurrence_relations
    }

def classify_tree(code: str) -> dict:
    try:
        index = Index.create()
        tu = index.parse('test.cpp', unsaved_files=[('test.cpp', code)])
    except Exception:
        return {"is_tree": False, "node_type_name": None, "left_field": None, "right_field": None}

    def visit(cursor):
        if cursor.kind in (CursorKind.STRUCT_DECL, CursorKind.CLASS_DECL):
            if cursor.location.file and cursor.location.file.name == 'test.cpp':
                name = cursor.spelling
                left_field = None
                right_field = None
                
                for child in cursor.get_children():
                    if child.kind == CursorKind.FIELD_DECL:
                        if is_self_pointer_field(child, name):
                            if child.spelling == 'left':
                                left_field = 'left'
                            elif child.spelling == 'right':
                                right_field = 'right'
                
                if left_field and right_field:
                    return {
                        "is_tree": True,
                        "node_type_name": name,
                        "left_field": left_field,
                        "right_field": right_field
                    }
        for child in cursor.get_children():
            res = visit(child)
            if res and res["is_tree"]:
                return res
        return None

    res = visit(tu.cursor)
    if res:
        return res
    return {"is_tree": False, "node_type_name": None, "left_field": None, "right_field": None}

def classify_linked_list(code: str) -> dict:
    try:
        index = Index.create()
        tu = index.parse('test.cpp', unsaved_files=[('test.cpp', code)])
    except Exception:
        return {"is_linked_list": False, "node_type_name": None, "next_field": None}

    def visit(cursor):
        if cursor.kind in (CursorKind.STRUCT_DECL, CursorKind.CLASS_DECL):
            if cursor.location.file and cursor.location.file.name == 'test.cpp':
                name = cursor.spelling
                next_field = None
                
                for child in cursor.get_children():
                    if child.kind == CursorKind.FIELD_DECL:
                        if is_self_pointer_field(child, name):
                            if child.spelling == 'next':
                                next_field = 'next'
                
                if next_field:
                    return {
                        "is_linked_list": True,
                        "node_type_name": name,
                        "next_field": next_field
                    }
        for child in cursor.get_children():
            res = visit(child)
            if res and res["is_linked_list"]:
                return res
        return None

    res = visit(tu.cursor)
    if res:
        return res
    return {"is_linked_list": False, "node_type_name": None, "next_field": None}

def detect_entry_point(code: str, selected_method: str = None) -> dict:
    try:
        index = Index.create()
        tu = index.parse('test.cpp', unsaved_files=[('test.cpp', code)])
    except Exception:
        return {"name": "", "return_type": "", "params": [], "candidates": [], "is_ambiguous": False}

    candidates = []
    has_main = False
    
    def visit(cursor):
        nonlocal has_main
        if cursor.kind in (CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD):
            if cursor.location.file and cursor.location.file.name == 'test.cpp':
                func_name = cursor.spelling
                if func_name == 'main':
                    has_main = True
                else:
                    params = []
                    for child in cursor.get_children():
                        if child.kind == CursorKind.PARM_DECL:
                            params.append({
                                "name": child.spelling,
                                "type": child.type.spelling
                            })
                    
                    is_class = cursor.kind == CursorKind.CXX_METHOD
                    class_name = None
                    if is_class and cursor.semantic_parent:
                        if cursor.semantic_parent.kind in (CursorKind.STRUCT_DECL, CursorKind.CLASS_DECL):
                            class_name = cursor.semantic_parent.spelling
                            
                    candidates.append({
                        "name": func_name,
                        "return_type": cursor.result_type.spelling,
                        "params": params,
                        "is_class": is_class,
                        "class_name": class_name
                    })
        for child in cursor.get_children():
            visit(child)

    visit(tu.cursor)

    if selected_method:
        for cand in candidates:
            if cand["name"] == selected_method:
                return {
                    "name": cand["name"],
                    "return_type": cand["return_type"],
                    "params": cand["params"],
                    "is_class": cand["is_class"],
                    "class_name": cand["class_name"],
                    "candidates": candidates,
                    "is_ambiguous": False
                }

    if has_main:
        return {
            "name": "main",
            "return_type": "int",
            "params": [],
            "is_class": False,
            "class_name": None,
            "candidates": candidates,
            "is_ambiguous": False,
            "has_invocation": True
        }

    if not candidates:
        return {"name": "", "return_type": "", "params": [], "candidates": [], "is_ambiguous": False}

    if len(candidates) > 1:
        return {
            "name": "",
            "return_type": "",
            "params": [],
            "candidates": candidates,
            "is_ambiguous": True
        }

    return {
        "name": candidates[0]["name"],
        "return_type": candidates[0]["return_type"],
        "params": candidates[0]["params"],
        "is_class": candidates[0]["is_class"],
        "class_name": candidates[0]["class_name"],
        "candidates": candidates,
        "is_ambiguous": False
    }

def classify_stl_containers(code: str) -> dict:
    """
    Scans C++ source code AST for declarations of std::stack, std::queue,
    std::map / std::unordered_map, and std::set / std::unordered_set.
    Returns dict mapping variable_name -> container_type ('stack', 'queue', 'map', 'set', 'vector').
    """
    try:
        tu, _ = parse_cpp_ast(code, use_header_mocks=True)
    except Exception:
        return {}

    container_types = {}

    def visit(cursor):
        if cursor.kind == CursorKind.VAR_DECL:
            if cursor.location.file and cursor.location.file.name == 'test.cpp':
                var_name = cursor.spelling
                type_spelling = cursor.type.spelling.lower()
                if 'stack<' in type_spelling:
                    container_types[var_name] = 'stack'
                elif 'queue<' in type_spelling:
                    container_types[var_name] = 'queue'
                elif 'map<' in type_spelling or 'unordered_map<' in type_spelling:
                    container_types[var_name] = 'map'
                elif 'set<' in type_spelling or 'unordered_set<' in type_spelling:
                    container_types[var_name] = 'set'
                elif 'vector<' in type_spelling:
                    container_types[var_name] = 'vector'

        for child in cursor.get_children():
            visit(child)

    visit(tu.cursor)
    return container_types
