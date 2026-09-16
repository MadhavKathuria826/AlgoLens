"""
AlgoLens Native C++ Source-Level Instrumentor (Milestone 5)
Uses libclang AST inspection to perform syntax-preserving instrumentation:
- Function & Method entry & exit wrapping (FRAME_PUSH / FRAME_POP)
- Member method & constructor tracking with 'this' variable bindings
- First-class reference declarations and tracking
- Variable declaration tracking (VAR_DECLARE) with stack object registration (AL_STACK_ALLOC)
- Scalar and pointer assignment tracking (VAR_WRITE)
- Dynamic memory allocation wrapping (OBJECT_ALLOCATE via al_new)
- Dynamic memory deallocation wrapping (OBJECT_DEALLOCATE via al_delete)
- Struct/Class member field mutations (OBJECT_MUTATE via al_field_write) with dot-path support
- Pointer dereference mutations (OBJECT_MUTATE via al_deref_write) with multi-level pointer support
- Array, Vector, and String element updates
- Standard container & string semantic operations:
    - std::vector (push_back, pop_back, clear, at, operator[])
    - std::string (push_back, pop_back, clear, append, operator[])
    - std::stack / std::queue (push, pop)
    - std::map / std::unordered_map (operator[], erase, clear)
- Statement step locations (STEP_LINE) with original source line mapping
- Synthetic entry point (algolens_entry) generation for shared library runner
"""

import os
import sys
from typing import List, Tuple, Dict, Any, Optional, Set
from clang.cindex import Index, CursorKind, TypeKind, Cursor, TranslationUnit

import cpp_classifier  # Ensures libclang native library is configured


class UnsupportedConstructError(Exception):
    """Raised when user source contains C++ constructs not yet supported by the native runtime."""
    def __init__(self, construct: str, line: int = 0):
        super().__init__(f"Unsupported C++ construct for Native Execution: '{construct}' at line {line}")
        self.construct = construct
        self.line = line


class SourceEdit:
    def __init__(self, offset: int, text: str, priority: int = 0, is_replace: bool = False, end_offset: int = 0):
        self.offset = offset
        self.text = text
        self.priority = priority
        self.is_replace = is_replace
        self.end_offset = end_offset if is_replace else offset

    def __lt__(self, other):
        if self.offset != other.offset:
            return self.offset < other.offset
        return self.priority < other.priority


class CPPInstrumentor:
    """
    AST-directed source instrumentor.
    Injects AlgoLens runtime hooks into C++ source code while preserving evaluation semantics.
    """

    def __init__(self):
        self.index = Index.create()

    def _extract_member_chain(self, lhs: Cursor, source_code: str, offset_shift: int) -> Optional[Tuple[str, bool, str]]:
        """
        Extracts the root object expression, whether it is a pointer, and the dot-separated field path.
        Returns (root_obj_expr, is_root_ptr, field_path) or None.
        Handles:
          - Qualified member on object: r.topLeft.x -> ('r', False, 'topLeft.x')
          - Qualified member on pointer: pr->topLeft.x -> ('pr', True, 'topLeft.x')
          - Explicit this: this->count -> ('this', True, 'count')
          - Unqualified member in method: count -> ('this', True, 'count')
          - Pointer hop: a->next->val -> ('a->next', True, 'val')
        """
        curr = lhs
        fields = []
        while curr.kind == CursorKind.MEMBER_REF_EXPR:
            fields.append(curr.spelling)
            ch = list(curr.get_children())
            if not ch:
                return ("this", True, ".".join(reversed(fields)))
            if ch[0].type.kind == TypeKind.POINTER:
                root_expr = source_code[ch[0].extent.start.offset - offset_shift : ch[0].extent.end.offset - offset_shift].strip()
                return (root_expr, True, ".".join(reversed(fields)))
            curr = ch[0]

        if curr.kind == CursorKind.CXX_THIS_EXPR:
            return ("this", True, ".".join(reversed(fields)))

        is_ptr = (curr.type.kind == TypeKind.POINTER)
        root_expr = source_code[curr.extent.start.offset - offset_shift : curr.extent.end.offset - offset_shift].strip()
        return (root_expr, is_ptr, ".".join(reversed(fields)))

    def instrument(self, source_code: str, entry_func: str = "main", args: List[Any] = None) -> str:
        """
        Instruments C++ source code.
        Returns the transformed C++ source string with algolens_runtime.hpp included.
        """
        # Parse Translation Unit with mock preamble for std types
        mock_preamble = (
            "namespace std {\n"
            "    struct string {\n"
            "        string();\n"
            "        string(const char*);\n"
            "        void push_back(char);\n"
            "        void pop_back();\n"
            "        void clear();\n"
            "        void append(const string&);\n"
            "        char& operator[](int);\n"
            "        int size();\n"
            "        bool empty();\n"
            "    };\n"
            "    template<typename T> struct vector {\n"
            "        void push_back(const T&);\n"
            "        void pop_back();\n"
            "        void clear();\n"
            "        T& at(int);\n"
            "        T& operator[](int);\n"
            "        T& back();\n"
            "        int size();\n"
            "        bool empty();\n"
            "    };\n"
            "    template<typename T> struct stack {\n"
            "        void push(const T&);\n"
            "        void pop();\n"
            "        T top();\n"
            "        int size();\n"
            "        bool empty();\n"
            "    };\n"
            "    template<typename T> struct queue {\n"
            "        void push(const T&);\n"
            "        void pop();\n"
            "        T front();\n"
            "        int size();\n"
            "        bool empty();\n"
            "    };\n"
            "    template<typename K, typename V> struct map {\n"
            "        void erase(const K&);\n"
            "        void clear();\n"
            "        V& operator[](const K&);\n"
            "        int size();\n"
            "        bool empty();\n"
            "    };\n"
            "    template<typename K, typename V> struct unordered_map {\n"
            "        void erase(const K&);\n"
            "        void clear();\n"
            "        V& operator[](const K&);\n"
            "        int size();\n"
            "        bool empty();\n"
            "    };\n"
            "}\n"
        )
        offset_shift = len(mock_preamble)
        line_shift = mock_preamble.count("\n")
        full_source = mock_preamble + source_code

        tu = self.index.parse(
            "input.cpp",
            args=["-std=c++17"],
            unsaved_files=[("input.cpp", full_source)]
        )

        # Check for syntax errors from libclang
        diags = [d for d in tu.diagnostics if d.severity >= 3]
        if diags:
            diag_msgs = "\n".join([f"Line {d.location.line - line_shift}: {d.spelling}" for d in diags if d.location.line > line_shift])
            if diag_msgs:
                raise SyntaxError(f"C++ parsing errors:\n{diag_msgs}")

        edits: List[SourceEdit] = []
        found_functions: Dict[str, bool] = {}
        ret_counter = 0

        # Scan for unsupported constructs and dynamic allocation
        for cursor in tu.cursor.walk_preorder():
            if not cursor.location.file or cursor.location.file.name != "input.cpp" or cursor.location.line <= line_shift:
                continue
            k = cursor.kind
            # Reject classes with inheritance
            if k == CursorKind.CXX_BASE_SPECIFIER:
                raise UnsupportedConstructError("class inheritance", cursor.location.line - line_shift)

            # Wrap new expressions: new T -> ::algolens::al_new(new T, "T", line)
            if k == CursorKind.CXX_NEW_EXPR:
                start_off = cursor.extent.start.offset - offset_shift
                end_off = cursor.extent.end.offset - offset_shift
                new_text = source_code[start_off:end_off]
                t_spelling = cursor.type.spelling
                if t_spelling.endswith("*"):
                    t_spelling = t_spelling[:-1].strip()
                t_name = t_spelling.replace("struct ", "").replace("class ", "").strip()
                if not t_name:
                    t_name = "Object"
                new_line = cursor.location.line - line_shift
                wrapped = f"::algolens::al_new({new_text}, \"{t_name}\", {new_line})"
                edits.append(SourceEdit(start_off, wrapped, priority=10, is_replace=True, end_offset=end_off))

        # Process Function Declarations, Methods, and Constructors
        seen_callable_locations: Set[Tuple[int, int]] = set()
        for cursor in tu.cursor.walk_preorder():
            if not cursor.location.file or cursor.location.file.name != "input.cpp" or cursor.location.line <= line_shift:
                continue

            if cursor.kind in (CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD, CursorKind.CONSTRUCTOR):
                loc_key = (cursor.location.line, cursor.location.column)
                if loc_key in seen_callable_locations:
                    continue

                # Find compound statement body
                body_node = None
                for ch in cursor.get_children():
                    if ch.kind == CursorKind.COMPOUND_STMT:
                        body_node = ch
                        break

                if not body_node:
                    continue

                seen_callable_locations.add(loc_key)

                is_method = cursor.kind in (CursorKind.CXX_METHOD, CursorKind.CONSTRUCTOR)
                parent_class = cursor.semantic_parent.spelling if is_method and cursor.semantic_parent else ""
                fn_name = f"{parent_class}::{cursor.spelling}" if parent_class else cursor.spelling
                is_void = (cursor.kind == CursorKind.CONSTRUCTOR or cursor.result_type.kind == TypeKind.VOID)
                fn_line = cursor.location.line - line_shift
                found_functions[cursor.spelling] = is_void

                body_start = (body_node.extent.start.offset - offset_shift) + 1
                push_code = f"\n    AL_FRAME_PUSH(\"{fn_name}\", {fn_line});"
                if fn_name == entry_func and fn_name == "main":
                    push_code = f"\n    AL_PROG_START(\"main\", {fn_line});" + push_code

                if is_method:
                    push_code += f"\n    AL_VAR_DECLARE(\"this\", \"{parent_class}*\", this, {fn_line});"
                    if cursor.kind == CursorKind.CONSTRUCTOR:
                        init_fields = [ch.spelling for ch in cursor.get_children() if ch.kind == CursorKind.MEMBER_REF]
                        for f_name in init_fields:
                            push_code += f"\n    AL_FIELD_WRITE(this, \"{f_name}\", (this->{f_name}), {fn_line});"

                for ch in cursor.get_children():
                    if ch.kind == CursorKind.PARM_DECL:
                        p_name = ch.spelling
                        p_type = ch.type.spelling
                        push_code += f"\n    AL_VAR_DECLARE(\"{p_name}\", \"{p_type}\", {p_name}, {fn_line});"

                edits.append(SourceEdit(body_start, push_code, priority=1))

                # Process statements inside body recursively
                ret_counter = self._instrument_block(body_node, source_code, edits, ret_counter, offset_shift, line_shift)

                # Insert final FRAME_POP before closing brace if void or constructor
                body_end = (body_node.extent.end.offset - offset_shift) - 1
                if is_void:
                    pop_code = f"\n    AL_FRAME_POP_VOID({body_node.extent.end.line - line_shift});\n"
                    edits.append(SourceEdit(body_end, pop_code, priority=10))

        # Sort and apply edits in reverse order so character offsets remain valid
        edits.sort(key=lambda e: (e.offset, e.priority), reverse=True)

        transformed = source_code
        for e in edits:
            if e.is_replace:
                transformed = transformed[:e.offset] + e.text + transformed[e.end_offset:]
            else:
                transformed = transformed[:e.offset] + e.text + transformed[e.offset:]

        # Add Runtime Header include at the top
        header_inc = "#include \"algolens_runtime.hpp\"\n\n"
        transformed = header_inc + transformed

        # If entry_func is not main() and main() wasn't defined, synthesize main() driver
        export_decl = (
            "\n\n#ifdef _WIN32\n"
            "#define AL_EXPORT extern \"C\" __declspec(dllexport)\n"
            "#else\n"
            "#define AL_EXPORT extern \"C\" __attribute__((visibility(\"default\")))\n"
            "#endif\n\n"
        )
        if "main" in found_functions:
            driver = (
                export_decl +
                "AL_EXPORT int algolens_entry() {\n"
                "    return main();\n"
                "}\n"
            )
        elif entry_func in found_functions:
            is_void = found_functions.get(entry_func, False)
            call_code = f"    {entry_func}();\n    return 0;\n" if is_void else f"    return {entry_func}();\n"
            driver = (
                export_decl +
                f"AL_EXPORT int algolens_entry() {{\n"
                f"    AL_PROG_START(\"{entry_func}\", 1);\n"
                f"{call_code}"
                f"}}\n\n"
                f"int main() {{\n    return algolens_entry();\n}}\n"
            )
        else:
            driver = export_decl + "AL_EXPORT int algolens_entry() {\n    return 0;\n}\n"
        transformed += driver

        return transformed

    def _instrument_block(self, block_node: Cursor, source_code: str, edits: List[SourceEdit], ret_counter: int, offset_shift: int, line_shift: int) -> int:
        """Traverses statements inside a block and records necessary source edits."""
        for stmt in block_node.get_children():
            ret_counter = self._instrument_stmt(stmt, source_code, edits, ret_counter, offset_shift, line_shift)
        return ret_counter

    def _instrument_stmt(self, stmt: Cursor, source_code: str, edits: List[SourceEdit], ret_counter: int, offset_shift: int, line_shift: int) -> int:
        k = stmt.kind
        # Unwrap UNEXPOSED_EXPR if it wraps an underlying call or binary expression
        if k == CursorKind.UNEXPOSED_EXPR:
            ch_list = list(stmt.get_children())
            if ch_list:
                stmt = ch_list[0]
                k = stmt.kind

        line = stmt.location.line - line_shift
        stmt_start = stmt.extent.start.offset - offset_shift
        stmt_end = stmt.extent.end.offset - offset_shift

        # 1. Variable Declaration: int x = 5; or Node* n = new Node; or Point pt;
        if k == CursorKind.DECL_STMT:
            edits.append(SourceEdit(stmt_start, f"\n    AL_STEP_LINE({line});\n    ", priority=0))

            for ch in stmt.get_children():
                if ch.kind == CursorKind.VAR_DECL:
                    var_name = ch.spelling
                    type_str = ch.type.spelling
                    end_pos = source_code.find(";", stmt_end - 1)
                    if end_pos != -1:
                        ins_pos = end_pos + 1
                        if ch.type.kind != TypeKind.CONSTANTARRAY:
                            canon_kind = ch.type.get_canonical().kind
                            type_lower = type_str.lower()
                            is_container = any(c in type_lower for c in ["vector", "stack", "queue", "map"])
                            if canon_kind == TypeKind.RECORD and not is_container and not ("string" in type_lower):
                                decl_hook = f"\n    AL_STACK_ALLOC(&{var_name}, \"{type_str}\", {line});\n    AL_VAR_DECLARE(\"{var_name}\", \"{type_str}\", {var_name}, {line});"
                            else:
                                decl_hook = f"\n    AL_VAR_DECLARE(\"{var_name}\", \"{type_str}\", {var_name}, {line});"
                            edits.append(SourceEdit(ins_pos, decl_hook, priority=2))

        # 2. Assignment / Binary Operator: x = 10; or n->val = 10; or *p = 10; or m["k"] = v;
        elif k == CursorKind.BINARY_OPERATOR:
            edits.append(SourceEdit(stmt_start, f"\n    AL_STEP_LINE({line});\n    ", priority=0))

            children = list(stmt.get_children())
            if children:
                lhs = children[0]
                end_pos = source_code.find(";", stmt_end - 1)
                if end_pos != -1:
                    ins_pos = end_pos + 1
                    # 2a. Simple scalar write: x = 10;
                    if lhs.kind == CursorKind.DECL_REF_EXPR:
                        var_name = lhs.spelling
                        write_hook = f"\n    AL_VAR_WRITE(\"{var_name}\", {var_name}, {line});"
                        edits.append(SourceEdit(ins_pos, write_hook, priority=2))

                    # 2b. Array, Vector, or String index: arr[i] = v; or s[0] = 'a';
                    elif lhs.kind == CursorKind.ARRAY_SUBSCRIPT_EXPR:
                        arr_children = list(lhs.get_children())
                        if len(arr_children) >= 2:
                            arr_name = arr_children[0].spelling
                            idx_str = source_code[arr_children[1].extent.start.offset - offset_shift : arr_children[1].extent.end.offset - offset_shift].strip()
                            if idx_str.startswith("[") and idx_str.endswith("]"):
                                idx_str = idx_str[1:-1].strip()
                            arr_type = arr_children[0].type.spelling.lower()
                            if "map" in arr_type:
                                arr_hook = f"\n    AL_MAP_INSERT(\"{arr_name}\", ({idx_str}), {arr_name}[({idx_str})], {line});"
                            elif "string" in arr_type and not any(k in arr_type for k in ["vector", "map", "stack", "queue"]):
                                arr_hook = f"\n    AL_STRING_WRITE(\"{arr_name}\", {arr_name}, {line});"
                            else:
                                arr_hook = f"\n    AL_ARRAY_WRITE(\"{arr_name}\", ({idx_str}), {arr_name}[({idx_str})], {line});"
                            edits.append(SourceEdit(ins_pos, arr_hook, priority=2))

                    # 2c. Method call on LHS: m["alpha"] = 1; or v.at(0) = 1;
                    elif lhs.kind == CursorKind.CALL_EXPR:
                        op_children = list(lhs.get_children())
                        if len(op_children) >= 2:
                            c_name = op_children[0].spelling
                            key_node = op_children[-1]
                            key_str = source_code[key_node.extent.start.offset - offset_shift : key_node.extent.end.offset - offset_shift].strip()
                            if key_str.startswith("[") and key_str.endswith("]"):
                                key_str = key_str[1:-1].strip()
                            c_type = op_children[0].type.spelling.lower()
                            if "map" in c_type:
                                map_hook = f"\n    AL_MAP_INSERT(\"{c_name}\", ({key_str}), {c_name}[({key_str})], {line});"
                            elif "string" in c_type and not any(k in c_type for k in ["vector", "map", "stack", "queue"]):
                                map_hook = f"\n    AL_STRING_WRITE(\"{c_name}\", {c_name}, {line});"
                            else:
                                map_hook = f"\n    AL_ARRAY_WRITE(\"{c_name}\", ({key_str}), {c_name}[({key_str})], {line});"
                            edits.append(SourceEdit(ins_pos, map_hook, priority=2))

                    # 2d. Struct / Class member write: n->val = 10; or r.topLeft.x = 10; or count = 10;
                    elif lhs.kind == CursorKind.MEMBER_REF_EXPR:
                        chain_res = self._extract_member_chain(lhs, source_code, offset_shift)
                        if chain_res:
                            root_expr, is_ptr, dot_path = chain_res
                            obj_arg = root_expr if is_ptr else f"(&({root_expr}))"
                            lhs_str = source_code[lhs.extent.start.offset - offset_shift : lhs.extent.end.offset - offset_shift]
                            field_hook = f"\n    AL_FIELD_WRITE({obj_arg}, \"{dot_path}\", ({lhs_str}), {line});"
                            edits.append(SourceEdit(ins_pos, field_hook, priority=2))

                    # 2e. Pointer dereference write: *p = 10; or *pp = &x; or **pp = 20;
                    elif lhs.kind == CursorKind.UNARY_OPERATOR:
                        un_children = list(lhs.get_children())
                        if un_children:
                            ptr_expr = source_code[un_children[0].extent.start.offset - offset_shift : un_children[0].extent.end.offset - offset_shift]
                            lhs_str = source_code[lhs.extent.start.offset - offset_shift : lhs.extent.end.offset - offset_shift]
                            deref_hook = f"\n    AL_DEREF_WRITE({ptr_expr}, ({lhs_str}), {line});"
                            edits.append(SourceEdit(ins_pos, deref_hook, priority=2))

        # 3. Dynamic Deallocation: delete ptr;
        elif k == CursorKind.CXX_DELETE_EXPR:
            edits.append(SourceEdit(stmt_start, f"\n    AL_STEP_LINE({line});\n    ", priority=0))
            del_children = list(stmt.get_children())
            if del_children:
                ptr_str = source_code[del_children[0].extent.start.offset - offset_shift : del_children[0].extent.end.offset - offset_shift]
                replacement = f"delete ::algolens::al_delete({ptr_str}, {line})"
                end_pos = source_code.find(";", stmt_start)
                if end_pos != -1:
                    edits.append(SourceEdit(stmt_start, replacement, priority=5, is_replace=True, end_offset=end_pos))

        # 4. Container Operations or Function Calls: v.push_back(x); or st.push(x); or st.pop(); s.append("...");
        elif k == CursorKind.CALL_EXPR:
            edits.append(SourceEdit(stmt_start, f"\n    AL_STEP_LINE({line});\n    ", priority=0))
            end_pos = source_code.find(";", stmt_end - 1)
            if end_pos != -1:
                ins_pos = end_pos + 1
                call_children = list(stmt.get_children())
                if call_children and call_children[0].kind == CursorKind.MEMBER_REF_EXPR:
                    mem_ref = call_children[0]
                    method_name = mem_ref.spelling
                    mem_children = list(mem_ref.get_children())
                    if mem_children:
                        c_name = mem_children[0].spelling
                        c_type = mem_children[0].type.spelling.lower()
                        is_string = ("string" in c_type) and not any(k in c_type for k in ["map", "vector", "stack", "queue"])

                        if method_name == "push_back":
                            if is_string:
                                hook = f"\n    AL_STRING_WRITE(\"{c_name}\", {c_name}, {line});"
                                edits.append(SourceEdit(ins_pos, hook, priority=2))
                            elif len(call_children) >= 2:
                                arg_str = source_code[call_children[1].extent.start.offset - offset_shift : call_children[1].extent.end.offset - offset_shift]
                                hook = f"\n    AL_CONTAINER_PUSH(\"{c_name}\", \"ARRAY\", ({arg_str}), {line});"
                                edits.append(SourceEdit(ins_pos, hook, priority=2))

                        elif method_name == "pop_back":
                            if is_string:
                                hook = f"\n    AL_STRING_WRITE(\"{c_name}\", {c_name}, {line});"
                                edits.append(SourceEdit(ins_pos, hook, priority=2))
                            else:
                                hook = f"\n    AL_CONTAINER_POP(\"{c_name}\", \"ARRAY\", ({c_name}.back()), {line});\n"
                                edits.append(SourceEdit(stmt_start, hook, priority=1))

                        elif method_name == "append" and is_string:
                            hook = f"\n    AL_STRING_WRITE(\"{c_name}\", {c_name}, {line});"
                            edits.append(SourceEdit(ins_pos, hook, priority=2))

                        elif method_name == "clear":
                            if is_string:
                                hook = f"\n    AL_STRING_WRITE(\"{c_name}\", {c_name}, {line});"
                                edits.append(SourceEdit(ins_pos, hook, priority=2))
                            elif "map" in c_type:
                                hook = f"\n    AL_MAP_CLEAR(\"{c_name}\", {c_name}, {line});\n"
                                edits.append(SourceEdit(stmt_start, hook, priority=1))
                            else:
                                hook = f"\n    AL_CONTAINER_CLEAR(\"{c_name}\", \"ARRAY\", {c_name}, {line});\n"
                                edits.append(SourceEdit(stmt_start, hook, priority=1))

                        elif method_name == "erase" and "map" in c_type and len(call_children) >= 2:
                            arg_str = source_code[call_children[1].extent.start.offset - offset_shift : call_children[1].extent.end.offset - offset_shift]
                            hook = f"\n    AL_MAP_ERASE(\"{c_name}\", ({arg_str}), {c_name}, {line});\n"
                            edits.append(SourceEdit(stmt_start, hook, priority=1))

                        elif method_name == "push" and len(call_children) >= 2:
                            c_kind = "QUEUE" if "queue" in c_type else "STACK"
                            arg_str = source_code[call_children[1].extent.start.offset - offset_shift : call_children[1].extent.end.offset - offset_shift]
                            hook = f"\n    AL_CONTAINER_PUSH(\"{c_name}\", \"{c_kind}\", ({arg_str}), {line});"
                            edits.append(SourceEdit(ins_pos, hook, priority=2))

                        elif method_name == "pop":
                            c_kind = "QUEUE" if "queue" in c_type else "STACK"
                            acc = f"{c_name}.front()" if "queue" in c_type else f"{c_name}.top()"
                            hook = f"\n    AL_CONTAINER_POP(\"{c_name}\", \"{c_kind}\", ({acc}), {line});\n"
                            edits.append(SourceEdit(stmt_start, hook, priority=1))

        # 5. Return Statement: return expr;
        elif k == CursorKind.RETURN_STMT:
            children = list(stmt.get_children())
            end_pos = source_code.find(";", stmt_start)
            if end_pos != -1:
                if children:
                    ret_expr_str = source_code[children[0].extent.start.offset - offset_shift : children[0].extent.end.offset - offset_shift]
                    ret_var = f"__al_ret_{ret_counter}"
                    ret_counter += 1
                    replacement = f"{{\n        AL_STEP_LINE({line});\n        auto {ret_var} = ({ret_expr_str});\n        AL_FRAME_POP({line}, {ret_var});\n        return {ret_var};\n    }}"
                else:
                    replacement = f"{{\n        AL_STEP_LINE({line});\n        AL_FRAME_POP_VOID({line});\n        return;\n    }}"

                edits.append(SourceEdit(stmt_start, replacement, priority=5, is_replace=True, end_offset=end_pos + 1))

        # 6. If Statement: if (cond) { ... } else { ... }
        elif k == CursorKind.IF_STMT:
            edits.append(SourceEdit(stmt_start, f"\n    AL_STEP_LINE({line});\n    ", priority=0))
            children = list(stmt.get_children())
            if len(children) >= 2:
                then_branch = children[1]
                if then_branch.kind == CursorKind.COMPOUND_STMT:
                    ret_counter = self._instrument_block(then_branch, source_code, edits, ret_counter, offset_shift, line_shift)
                else:
                    if then_branch.kind != CursorKind.RETURN_STMT:
                        edits.append(SourceEdit(then_branch.extent.start.offset - offset_shift, "{\n", priority=1))
                        end_semi = source_code.find(";", (then_branch.extent.end.offset - offset_shift) - 1)
                        if end_semi != -1:
                            edits.append(SourceEdit(end_semi + 1, "\n}\n", priority=-1))
                    ret_counter = self._instrument_stmt(then_branch, source_code, edits, ret_counter, offset_shift, line_shift)

            if len(children) >= 3:
                else_branch = children[2]
                if else_branch.kind == CursorKind.COMPOUND_STMT:
                    ret_counter = self._instrument_block(else_branch, source_code, edits, ret_counter, offset_shift, line_shift)
                elif else_branch.kind == CursorKind.IF_STMT:
                    ret_counter = self._instrument_stmt(else_branch, source_code, edits, ret_counter, offset_shift, line_shift)
                else:
                    if else_branch.kind != CursorKind.RETURN_STMT:
                        edits.append(SourceEdit(else_branch.extent.start.offset - offset_shift, "{\n", priority=1))
                        end_semi = source_code.find(";", (else_branch.extent.end.offset - offset_shift) - 1)
                        if end_semi != -1:
                            edits.append(SourceEdit(end_semi + 1, "\n}\n", priority=-1))
                    ret_counter = self._instrument_stmt(else_branch, source_code, edits, ret_counter, offset_shift, line_shift)

        # 7. Loops: For & While
        elif k in (CursorKind.FOR_STMT, CursorKind.WHILE_STMT):
            edits.append(SourceEdit(stmt_start, f"\n    AL_STEP_LINE({line});\n    ", priority=0))
            children = list(stmt.get_children())
            if children:
                body = children[-1]
                if body.kind == CursorKind.COMPOUND_STMT:
                    body_start = (body.extent.start.offset - offset_shift) + 1
                    edits.append(SourceEdit(body_start, f"\n        AL_STEP_LINE({line});", priority=1))
                    ret_counter = self._instrument_block(body, source_code, edits, ret_counter, offset_shift, line_shift)
                else:
                    edits.append(SourceEdit(body.extent.start.offset - offset_shift, "{\n        AL_STEP_LINE(" + str(line) + ");\n", priority=1))
                    end_semi = source_code.find(";", (body.extent.end.offset - offset_shift) - 1)
                    if end_semi != -1:
                        edits.append(SourceEdit(end_semi + 1, "\n    }\n", priority=-1))
                    ret_counter = self._instrument_stmt(body, source_code, edits, ret_counter, offset_shift, line_shift)

        # 8. Nested Compound Statement / Scope: { ... }
        elif k == CursorKind.COMPOUND_STMT:
            scope_start = stmt_start + 1
            scope_end = stmt_end - 1
            edits.append(SourceEdit(scope_start, f"\n    AL_SCOPE_ENTER(\"block\", {line});", priority=1))
            edits.append(SourceEdit(scope_end, f"\n    AL_SCOPE_EXIT({stmt.extent.end.line - line_shift});\n", priority=-1))
            ret_counter = self._instrument_block(stmt, source_code, edits, ret_counter, offset_shift, line_shift)

        return ret_counter
