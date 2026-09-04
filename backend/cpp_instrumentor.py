"""
AlgoLens Native C++ Source-Level Instrumentor (Milestone 3 Prototype)
Uses libclang AST inspection to perform syntax-preserving instrumentation:
- Function entry & exit wrapping (FRAME_PUSH / FRAME_POP) with zero side-effect duplication
- Variable declaration tracking (VAR_DECLARE)
- Assignment & mutation tracking (VAR_WRITE)
- Array element updates (CONTAINER_OP / SET_INDEX)
- Statement step locations (STEP_LINE) with original source line mapping
- Synthetic main() driver generation when entry function is non-main (e.g. test())
"""

import os
import sys
from typing import List, Tuple, Dict, Any, Optional, Set
from clang.cindex import Index, CursorKind, TypeKind, Cursor, TranslationUnit

import cpp_classifier  # Ensures libclang native library is configured


class UnsupportedConstructError(Exception):
    """Raised when user source contains C++ constructs not yet supported by the native prototype."""
    def __init__(self, construct: str, line: int = 0):
        super().__init__(f"Unsupported C++ construct for Native Milestone 3: '{construct}' at line {line}")
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

    def instrument(self, source_code: str, entry_func: str = "main", args: List[Any] = None) -> str:
        """
        Instruments C++ source code.
        Returns the transformed C++ source string with algolens_runtime.hpp included.
        """
        # Parse Translation Unit with mock preamble for std types
        mock_preamble = "namespace std { struct string { string(); string(const char*); }; }\n"
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
        found_functions: Set[str] = set()
        ret_counter = 0

        # Scan for unsupported constructs first (Milestone 3 boundaries)
        for cursor in tu.cursor.walk_preorder():
            if not cursor.location.file or cursor.location.file.name != "input.cpp" or cursor.location.line <= line_shift:
                continue
            k = cursor.kind
            # Reject dynamic allocation in Milestone 3 (scheduled for Milestone 4)
            if k in (CursorKind.CXX_NEW_EXPR, CursorKind.CXX_DELETE_EXPR):
                raise UnsupportedConstructError("dynamic allocation (new/delete)", cursor.location.line - line_shift)
            # Reject classes with inheritance in Milestone 3
            if k == CursorKind.CXX_BASE_SPECIFIER:
                raise UnsupportedConstructError("class inheritance", cursor.location.line - line_shift)

        # Process Function Declarations and their Compound Statements
        for cursor in tu.cursor.get_children():
            if not cursor.location.file or cursor.location.file.name != "input.cpp" or cursor.location.line <= line_shift:
                continue

            if cursor.kind == CursorKind.FUNCTION_DECL:
                fn_name = cursor.spelling
                found_functions.add(fn_name)
                fn_line = cursor.location.line - line_shift

                # Find compound statement body
                body_node = None
                for ch in cursor.get_children():
                    if ch.kind == CursorKind.COMPOUND_STMT:
                        body_node = ch
                        break

                if body_node:
                    # Insert FRAME_PUSH and parameter declarations at start of body (right after '{')
                    body_start = (body_node.extent.start.offset - offset_shift) + 1
                    push_code = f"\n    AL_FRAME_PUSH(\"{fn_name}\", {fn_line});"
                    if fn_name == entry_func and fn_name == "main":
                        push_code = f"\n    AL_PROG_START(\"main\", {fn_line});" + push_code
                    
                    for ch in cursor.get_children():
                        if ch.kind == CursorKind.PARM_DECL:
                            p_name = ch.spelling
                            p_type = ch.type.spelling
                            push_code += f"\n    AL_VAR_DECLARE(\"{p_name}\", \"{p_type}\", {p_name}, {fn_line});"

                    edits.append(SourceEdit(body_start, push_code, priority=1))

                    # Process statements inside body recursively
                    ret_counter = self._instrument_block(body_node, source_code, edits, ret_counter, offset_shift, line_shift)

                    # Insert final FRAME_POP before closing brace if non-main void or fallback
                    body_end = (body_node.extent.end.offset - offset_shift) - 1
                    if cursor.result_type.kind == TypeKind.VOID:
                        pop_code = f"\n    AL_FRAME_POP_VOID({body_node.extent.end.line - line_shift});\n"
                        edits.append(SourceEdit(body_end, pop_code, priority=-1))

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
        if "main" not in found_functions and entry_func in found_functions:
            driver = f"\n\nint main() {{\n    AL_PROG_START(\"{entry_func}\", 1);\n    {entry_func}();\n    return 0;\n}}\n"
            transformed += driver

        return transformed

    def _instrument_block(self, block_node: Cursor, source_code: str, edits: List[SourceEdit], ret_counter: int, offset_shift: int, line_shift: int) -> int:
        """Traverses statements inside a block and records necessary source edits."""
        for stmt in block_node.get_children():
            ret_counter = self._instrument_stmt(stmt, source_code, edits, ret_counter, offset_shift, line_shift)
        return ret_counter

    def _instrument_stmt(self, stmt: Cursor, source_code: str, edits: List[SourceEdit], ret_counter: int, offset_shift: int, line_shift: int) -> int:
        k = stmt.kind
        line = stmt.location.line - line_shift
        stmt_start = stmt.extent.start.offset - offset_shift
        stmt_end = stmt.extent.end.offset - offset_shift

        # 1. Variable Declaration: int x = 5;
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
                            decl_hook = f"\n    AL_VAR_DECLARE(\"{var_name}\", \"{type_str}\", {var_name}, {line});"
                            edits.append(SourceEdit(ins_pos, decl_hook, priority=2))

        # 2. Assignment / Binary Operator: x = 10; or arr[i] = val;
        elif k == CursorKind.BINARY_OPERATOR:
            edits.append(SourceEdit(stmt_start, f"\n    AL_STEP_LINE({line});\n    ", priority=0))

            children = list(stmt.get_children())
            if children:
                lhs = children[0]
                end_pos = source_code.find(";", stmt_end - 1)
                if end_pos != -1:
                    ins_pos = end_pos + 1
                    if lhs.kind == CursorKind.DECL_REF_EXPR:
                        var_name = lhs.spelling
                        write_hook = f"\n    AL_VAR_WRITE(\"{var_name}\", {var_name}, {line});"
                        edits.append(SourceEdit(ins_pos, write_hook, priority=2))
                    elif lhs.kind == CursorKind.ARRAY_SUBSCRIPT_EXPR:
                        arr_children = list(lhs.get_children())
                        if len(arr_children) >= 2:
                            arr_name = arr_children[0].spelling
                            idx_str = source_code[arr_children[1].extent.start.offset - offset_shift : arr_children[1].extent.end.offset - offset_shift]
                            arr_hook = f"\n    AL_ARRAY_WRITE(\"{arr_name}\", ({idx_str}), {arr_name}[({idx_str})], {line});"
                            edits.append(SourceEdit(ins_pos, arr_hook, priority=2))

        # 3. Return Statement: return expr;
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

        # 4. If Statement: if (cond) { ... } else { ... }
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

        # 5. Loops: For & While
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

        # 6. Nested Compound Statement / Scope: { ... }
        elif k == CursorKind.COMPOUND_STMT:
            scope_start = stmt_start + 1
            scope_end = stmt_end - 1
            edits.append(SourceEdit(scope_start, f"\n    AL_SCOPE_ENTER(\"block\", {line});", priority=1))
            edits.append(SourceEdit(scope_end, f"\n    AL_SCOPE_EXIT({stmt.extent.end.line - line_shift});\n", priority=-1))
            ret_counter = self._instrument_block(stmt, source_code, edits, ret_counter, offset_shift, line_shift)

        return ret_counter
