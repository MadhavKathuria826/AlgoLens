import copy
import math
from typing import Dict, Any, List, Optional, Tuple, Union
from clang.cindex import Index, CursorKind, TypeKind, Cursor
from cpp_classifier import parse_cpp_ast
from models import Step, VisualizationData

# --- Exceptions for Control Flow and Safety Caps ---

class ReturnException(Exception):
    def __init__(self, value: Any):
        self.value = value

class BreakException(Exception):
    pass

class ContinueException(Exception):
    pass

class InterpreterError(Exception):
    pass

class ExecutionLimitError(InterpreterError):
    pass

# --- Shared C++ Semantics Helpers ---

def cpp_int_div(a: int, b: int) -> int:
    """Integer division truncating toward zero (C++ semantics)."""
    if b == 0:
        raise ZeroDivisionError("division by zero in C++ interpreter")
    return int(float(a) / float(b))

def cpp_int_mod(a: int, b: int) -> int:
    """Modulo retaining dividend sign (C++ semantics)."""
    if b == 0:
        raise ZeroDivisionError("modulo by zero in C++ interpreter")
    div = cpp_int_div(a, b)
    return a - div * b

def wrap_int(val: Any, type_str: str = "int") -> Any:
    """Wraps fixed-width integers on overflow per C++ semantics (signed 2's complement & unsigned modulo)."""
    if not isinstance(val, int) or isinstance(val, bool):
        return val
    type_s = (type_str or "int").lower()
    if 'unsigned' in type_s:
        if 'short' in type_s:
            return val % 65536
        elif 'char' in type_s:
            return val % 256
        else: # unsigned int / unsigned long
            return val % 4294967296
    else:
        if 'short' in type_s:
            return (val + 32768) % 65536 - 32768
        elif 'char' in type_s:
            return (val + 128) % 256 - 128
        elif 'int' in type_s or 'long' in type_s:
            return (val + 2147483648) % 4294967296 - 2147483648
    return val

def is_pointer_type(type_str: str, val: Any = None) -> bool:
    """Checks if static type or runtime value represents a pointer address."""
    if type_str and ('*' in type_str or type_str.endswith('*')):
        return True
    if isinstance(val, str) and (val.startswith("0x") or val in ("nullptr", "NULL")):
        return True
    return False

# --- Environment & Heap Model ---

class Heap:
    """Simulated Heap mapping synthetic memory addresses (0x1000) to object dicts."""
    def __init__(self):
        self._address_counter = 0x1000
        self._memory: Dict[str, Dict[str, Any]] = {}

    def allocate(self, initial_fields: Dict[str, Any] = None) -> str:
        addr = f"0x{self._address_counter:04x}"
        self._address_counter += 4
        self._memory[addr] = copy.deepcopy(initial_fields) if initial_fields is not None else {}
        return addr

    def get(self, addr: str) -> Optional[Dict[str, Any]]:
        return self._memory.get(addr)

    def set_field(self, addr: str, field: str, value: Any):
        if addr in self._memory:
            self._memory[addr][field] = value
        else:
            raise KeyError(f"Null or invalid pointer dereference at address '{addr}'")

    def get_field(self, addr: str, field: str) -> Any:
        if addr in self._memory:
            if field in self._memory[addr]:
                return self._memory[addr][field]
            raise AttributeError(f"Object at '{addr}' has no field '{field}'")
        raise KeyError(f"Null or invalid pointer dereference at address '{addr}'")

    def to_dict(self) -> Dict[str, Any]:
        return copy.deepcopy(self._memory)

class Scope:
    """Dict-based variable scope with type tracking."""
    def __init__(self, parent: Optional['Scope'] = None, name: str = "local"):
        self.parent = parent
        self.name = name
        self.variables: Dict[str, Any] = {}
        self.types: Dict[str, str] = {}

    def declare(self, name: str, value: Any, type_str: str):
        self.variables[name] = value
        self.types[name] = type_str or ""

    def assign(self, name: str, value: Any) -> bool:
        if name in self.variables:
            self.variables[name] = value
            return True
        elif self.parent:
            return self.parent.assign(name, value)
        return False

    def lookup(self, name: str) -> Tuple[bool, Any]:
        if name in self.variables:
            return True, self.variables[name]
        elif self.parent:
            return self.parent.lookup(name)
        return False, None

    def lookup_type(self, name: str) -> Optional[str]:
        if name in self.types:
            return self.types[name]
        elif self.parent:
            return self.parent.lookup_type(name)
        return None

    def get_all_locals(self) -> Dict[str, Any]:
        merged = {}
        if self.parent and self.parent.parent is not None:
            merged.update(self.parent.get_all_locals())
        merged.update(self.variables)
        return merged

class Environment:
    """Execution environment managing call stack, heap, and struct definitions."""
    def __init__(self):
        self.heap = Heap()
        self.global_scope = Scope(name="global")
        self.call_stack: List[Scope] = [self.global_scope]
        self.struct_definitions: Dict[str, Dict[str, Any]] = {}
        self.function_cursors: Dict[str, Cursor] = {}

    @property
    def current_scope(self) -> Scope:
        return self.call_stack[-1]

    def push_scope(self, name: str = "block") -> Scope:
        new_scope = Scope(parent=self.current_scope, name=name)
        self.call_stack.append(new_scope)
        return new_scope

    def pop_scope(self):
        if len(self.call_stack) > 1:
            self.call_stack.pop()

    def push_function_frame(self, name: str = "function") -> Scope:
        frame_scope = Scope(parent=self.global_scope, name=name)
        self.call_stack.append(frame_scope)
        return frame_scope

# --- Centralized Copy-vs-Alias Assignment & Pass-by-Value Handlers ---

def assign_var(name: str, val: Any, type_str: str, scope: Scope, env: Environment) -> Any:
    """
    Centralized assignment logic:
    - Pointer types (TreeNode*, ListNode*, etc.): ALIAS (store address string directly).
    - Struct/Class/Vector value types: COPY (deep copy).
    - Primitives: scalar copy (wrapped by int overflow rule if fixed width int).
    """
    if is_pointer_type(type_str, val):
        processed_val = val if val is not None else "0x0000"
    elif isinstance(val, dict):
        processed_val = copy.deepcopy(val)
    elif isinstance(val, list):
        processed_val = copy.deepcopy(val)
    elif isinstance(val, int):
        processed_val = wrap_int(val, type_str)
    else:
        processed_val = copy.deepcopy(val)

    assigned = scope.assign(name, processed_val)
    if not assigned:
        scope.declare(name, processed_val, type_str)
    return processed_val

def pass_argument(param_name: str, val: Any, param_type_str: str, callee_scope: Scope, env: Environment):
    """
    Centralized function argument binding logic:
    - Pointer types (TreeNode*, ListNode*, etc.): ALIAS (store address string directly).
    - Struct/Class/Vector value types: COPY (deep copy).
    - Primitives: scalar copy (wrapped by int overflow rule).
    """
    if is_pointer_type(param_type_str, val):
        bound_val = val if val is not None else "0x0000"
    elif isinstance(val, dict):
        bound_val = copy.deepcopy(val)
    elif isinstance(val, list):
        bound_val = copy.deepcopy(val)
    elif isinstance(val, int):
        bound_val = wrap_int(val, param_type_str)
    else:
        bound_val = copy.deepcopy(val)

    callee_scope.declare(param_name, bound_val, param_type_str)

# --- Interpreter Class ---

class CPPInterpreter:
    def __init__(self, max_recursion_depth: int = 100, max_loop_iterations: int = 10000, max_total_steps: int = 2000):
        self.env = Environment()
        self.steps: List[Step] = []
        self.step_counter = 0
        self.header_lines_count = 0
        self.max_recursion_depth = max_recursion_depth
        self.max_loop_iterations = max_loop_iterations
        self.max_total_steps = max_total_steps

    def unwrap(self, cursor: Cursor) -> Cursor:
        """Strip implicit Clang wrapper nodes."""
        wrapper_kinds = {CursorKind.UNEXPOSED_EXPR, CursorKind.PAREN_EXPR}
        for name in ('IMPLICIT_CAST_EXPR', 'CXX_FUNCTIONAL_CAST_EXPR', 'CSTYLE_CAST_EXPR'):
            if hasattr(CursorKind, name):
                wrapper_kinds.add(getattr(CursorKind, name))
        curr = cursor
        while curr and curr.kind in wrapper_kinds:
            children = list(curr.get_children())
            if len(children) == 1:
                curr = children[0]
            else:
                break
        return curr

    def emit_step(self, line_number: int, event_type: str = "line"):
        if line_number <= 0:
            return
        if self.step_counter >= self.max_total_steps:
            raise ExecutionLimitError(f"Maximum step limit of {self.max_total_steps} exceeded")

        locals_snapshot = {}
        curr_locals = self.env.current_scope.get_all_locals()
        for k, v in curr_locals.items():
            if isinstance(v, (int, float, bool, str)):
                locals_snapshot[k] = v
            elif isinstance(v, (list, dict)):
                locals_snapshot[k] = copy.deepcopy(v)
            else:
                locals_snapshot[k] = str(v)

        heap_snapshot = self.env.heap.to_dict()

        visualizations = []
        for k, v in locals_snapshot.items():
            if isinstance(v, list):
                visualizations.append(VisualizationData(
                    type='Array',
                    details={
                        'name': k,
                        'value': list(v),
                        'obj_id': f"cpp_list_{k}"
                    }
                ))

        scalar_locals = {k: v for k, v in locals_snapshot.items() if not isinstance(v, (list, dict))}
        if scalar_locals:
            visualizations.append(VisualizationData(
                type='Variable',
                details=scalar_locals
            ))

        step = Step(
            step_number=self.step_counter,
            line_number=line_number,
            event_type=event_type,
            locals=locals_snapshot,
            heap=heap_snapshot,
            visualizations=visualizations
        )
        self.steps.append(step)
        self.step_counter += 1

    def parse_struct_definitions(self, root_cursor: Cursor):
        """Scans AST for struct/class declarations and records their fields."""
        def visit(c: Cursor):
            if c.kind in (CursorKind.STRUCT_DECL, CursorKind.CLASS_DECL):
                struct_name = c.spelling
                if struct_name:
                    fields = {}
                    for child in c.get_children():
                        if child.kind == CursorKind.FIELD_DECL:
                            f_name = child.spelling
                            f_type = child.type.spelling
                            clean_type = f_type.replace('struct ', '').replace('class ', '').strip()
                            if is_pointer_type(f_type):
                                fields[f_name] = "0x0000"
                            elif clean_type in self.env.struct_definitions:
                                fields[f_name] = copy.deepcopy(self.env.struct_definitions[clean_type])
                            elif 'int' in f_type or 'short' in f_type or 'char' in f_type:
                                fields[f_name] = 0
                            elif 'float' in f_type or 'double' in f_type:
                                fields[f_name] = 0.0
                            elif 'bool' in f_type:
                                fields[f_name] = False
                            else:
                                fields[f_name] = None
                    self.env.struct_definitions[struct_name] = fields
            elif c.kind in (CursorKind.FUNCTION_DECL, CursorKind.CXX_METHOD):
                func_name = c.spelling
                if func_name:
                    self.env.function_cursors[func_name] = c
            for child in c.get_children():
                visit(child)

        visit(root_cursor)

    # --- Expression Evaluation ---

    def eval_expr(self, cursor: Cursor) -> Any:
        curr = self.unwrap(cursor)
        kind = curr.kind

        if kind in (CursorKind.TYPE_REF, CursorKind.NAMESPACE_REF, CursorKind.TEMPLATE_REF):
            return None

        # Literals
        if kind == CursorKind.INTEGER_LITERAL:
            tokens = list(curr.get_tokens())
            if tokens:
                val_str = tokens[0].spelling
                return int(val_str, 0) if val_str.startswith(('0x', '0X')) else int(val_str)
            return 0

        elif kind == CursorKind.FLOATING_LITERAL:
            tokens = list(curr.get_tokens())
            return float(tokens[0].spelling) if tokens else 0.0

        elif kind == CursorKind.STRING_LITERAL:
            tokens = list(curr.get_tokens())
            return tokens[0].spelling.strip('"') if tokens else ""

        elif kind == CursorKind.CHARACTER_LITERAL:
            tokens = list(curr.get_tokens())
            if tokens:
                s = tokens[0].spelling.strip("'")
                return ord(s) if len(s) == 1 else 0
            return 0

        elif kind == CursorKind.CXX_BOOL_LITERAL_EXPR:
            tokens = list(curr.get_tokens())
            return (tokens[0].spelling == 'true') if tokens else False

        elif kind == CursorKind.CXX_NULL_PTR_LITERAL_EXPR:
            return "0x0000"

        # Variable reference
        elif kind == CursorKind.DECL_REF_EXPR:
            var_name = curr.spelling
            if var_name in ("nullptr", "NULL"):
                return "0x0000"
            found, val = self.env.current_scope.lookup(var_name)
            if found:
                return val
            raise InterpreterError(f"Undefined variable '{var_name}'")

        # Binary operators & assignments
        elif kind == CursorKind.BINARY_OPERATOR:
            children = list(curr.get_children())
            if len(children) < 2:
                raise InterpreterError("Invalid binary operator node")
            
            lhs_node = children[0]
            rhs_node = children[1]

            lhs_end = lhs_node.extent.end
            rhs_start = rhs_node.extent.start
            op = None
            valid_ops = ('=', '+=', '-=', '*=', '/=', '%=', '+', '-', '*', '/', '%', '==', '!=', '<', '<=', '>', '>=', '&&', '||')
            
            for t in curr.get_tokens():
                t_sp = t.spelling
                if t_sp in valid_ops:
                    if (t.extent.start.line > lhs_end.line or (t.extent.start.line == lhs_end.line and t.extent.start.column >= lhs_end.column)) and \
                       (t.extent.end.line < rhs_start.line or (t.extent.end.line == rhs_start.line and t.extent.end.column <= rhs_start.column)):
                        op = t_sp
                        break

            if not op:
                for t in curr.get_tokens():
                    if t.spelling in valid_ops:
                        op = t.spelling
                        break

            # Short-circuit logical
            if op == '&&':
                l_val = self.eval_expr(lhs_node)
                if not l_val:
                    return False
                return bool(self.eval_expr(rhs_node))
            elif op == '||':
                l_val = self.eval_expr(lhs_node)
                if l_val:
                    return True
                return bool(self.eval_expr(rhs_node))

            # Assignment operations
            if op in ('=', '+=', '-=', '*=', '/=', '%='):
                rhs_val = self.eval_expr(rhs_node)
                return self.exec_assignment(lhs_node, op, rhs_val)

            # Standard arithmetic / comparison
            lhs_val = self.eval_expr(lhs_node)
            rhs_val = self.eval_expr(rhs_node)

            if op == '+':
                if isinstance(lhs_val, str) or isinstance(rhs_val, str):
                    return str(lhs_val) + str(rhs_val)
                res = lhs_val + rhs_val
                return wrap_int(res, "int") if isinstance(res, int) else res
            elif op == '-':
                res = lhs_val - rhs_val
                return wrap_int(res, "int") if isinstance(res, int) else res
            elif op == '*':
                res = lhs_val * rhs_val
                return wrap_int(res, "int") if isinstance(res, int) else res
            elif op == '/':
                if isinstance(lhs_val, int) and isinstance(rhs_val, int):
                    return wrap_int(cpp_int_div(lhs_val, rhs_val), "int")
                return lhs_val / rhs_val
            elif op == '%':
                return wrap_int(cpp_int_mod(lhs_val, rhs_val), "int")
            elif op == '==':
                return lhs_val == rhs_val
            elif op == '!=':
                return lhs_val != rhs_val
            elif op == '<':
                return lhs_val < rhs_val
            elif op == '<=':
                return lhs_val <= rhs_val
            elif op == '>':
                return lhs_val > rhs_val
            elif op == '>=':
                return lhs_val >= rhs_val

        # Unary operators
        elif kind == CursorKind.UNARY_OPERATOR:
            children = list(curr.get_children())
            tokens = [t.spelling for t in curr.get_tokens()]
            op = tokens[0] if tokens else ""

            if op == '!':
                val = self.eval_expr(children[0])
                return not bool(val)
            elif op == '-':
                val = self.eval_expr(children[0])
                return wrap_int(-val, "int") if isinstance(val, int) else -val
            elif op == '+':
                return self.eval_expr(children[0])
            elif op in ('++', '--'):
                child = children[0]
                old_val = self.eval_expr(child)
                delta = 1 if op == '++' else -1
                new_val = wrap_int(old_val + delta, "int") if isinstance(old_val, int) else old_val + delta
                self.exec_assignment(child, '=', new_val)
                is_postfix = tokens[-1] in ('++', '--') if len(tokens) > 1 else False
                return old_val if is_postfix else new_val
            elif op == '*':
                addr = self.eval_expr(children[0])
                heap_obj = self.env.heap.get(addr)
                if heap_obj is not None:
                    return heap_obj
                raise InterpreterError(f"Null pointer dereference on '{addr}'")

        # Member access (. or ->)
        elif kind == CursorKind.MEMBER_REF_EXPR:
            children = list(curr.get_children())
            base_node = children[0]
            field_name = curr.spelling
            tokens = [t.spelling for t in curr.get_tokens()]
            is_arrow = '->' in tokens

            if is_arrow:
                addr = self.eval_expr(base_node)
                return self.env.heap.get_field(addr, field_name)
            else:
                base_obj = self.eval_expr(base_node)
                if isinstance(base_obj, dict) and field_name in base_obj:
                    return base_obj[field_name]
                elif isinstance(base_obj, list) and field_name == 'size':
                    return len(base_obj)
                raise InterpreterError(f"Invalid member access '{field_name}'")

        # Subscripting arr[i]
        elif kind == CursorKind.ARRAY_SUBSCRIPT_EXPR:
            children = list(curr.get_children())
            arr_val = self.eval_expr(children[0])
            idx_val = self.eval_expr(children[1])
            return arr_val[idx_val]

        # Allocation: new TreeNode(val) / new ListNode(val)
        elif kind == CursorKind.CXX_NEW_EXPR:
            type_str = curr.type.spelling.replace('*', '').strip()
            struct_fields = self.env.struct_definitions.get(type_str, {})
            initial_fields = copy.deepcopy(struct_fields)

            children = list(curr.get_children())
            args = [self.eval_expr(ch) for ch in children if ch.kind not in (CursorKind.TYPE_REF, CursorKind.NAMESPACE_REF, CursorKind.TEMPLATE_REF)]
            
            field_names = list(initial_fields.keys())
            for idx, arg_val in enumerate(args):
                if idx < len(field_names):
                    initial_fields[field_names[idx]] = arg_val

            addr = self.env.heap.allocate(initial_fields)
            return addr

        # Function / Method calls
        elif kind == CursorKind.CALL_EXPR:
            func_name = curr.spelling
            children = list(curr.get_children())
            tokens = [t.spelling for t in curr.get_tokens()]

            # Resolve function name from first child if empty
            if not func_name and children:
                first_child = self.unwrap(children[0])
                if first_child.kind == CursorKind.DECL_REF_EXPR:
                    func_name = first_child.spelling

            if func_name == 'operator[]' or (children and any(c.spelling == 'operator[]' for c in children)):
                arr_val = self.eval_expr(children[0])
                idx_val = self.eval_expr(children[2] if len(children) >= 3 else children[1])
                return arr_val[idx_val]

            # Vector / std member call
            if '.' in tokens or '->' in tokens or (children and children[0].kind == CursorKind.MEMBER_REF_EXPR):
                method_name = ""
                if children and children[0].kind == CursorKind.MEMBER_REF_EXPR:
                    first_child = children[0]
                    m_children = list(first_child.get_children())
                    method_name = first_child.spelling
                    base_val = self.eval_expr(m_children[0])
                    args = [self.eval_expr(c) for c in children[1:]]
                else:
                    base_val = self.eval_expr(children[0])
                    args = [self.eval_expr(c) for c in children[1:]]
                    for idx_t, tok in enumerate(tokens):
                        if tok in ('.', '->') and idx_t + 1 < len(tokens):
                            method_name = tokens[idx_t + 1]
                            break

                if isinstance(base_val, list):
                    if method_name == 'size':
                        return len(base_val)
                    elif method_name == 'push_back':
                        if args:
                            base_val.append(args[0])
                        return None
                    elif method_name == 'empty':
                        return len(base_val) == 0

            # vector constructor call
            if func_name == 'vector' or (curr.type and 'vector' in curr.type.spelling.lower()):
                return []

            # Struct constructor call: e.g. Point() or Node()
            if func_name in self.env.struct_definitions:
                struct_fields = copy.deepcopy(self.env.struct_definitions[func_name])
                args = [self.eval_expr(c) for c in children if c.kind not in (CursorKind.TYPE_REF, CursorKind.NAMESPACE_REF, CursorKind.TEMPLATE_REF, CursorKind.DECL_REF_EXPR)]
                field_names = list(struct_fields.keys())
                for idx, arg_val in enumerate(args):
                    if idx < len(field_names):
                        struct_fields[field_names[idx]] = arg_val
                return struct_fields

            # Std math functions
            if func_name in ('min', 'std::min'):
                args = [self.eval_expr(c) for c in children[1:]]
                return min(args)
            elif func_name in ('max', 'std::max'):
                args = [self.eval_expr(c) for c in children[1:]]
                return max(args)
            elif func_name in ('abs', 'std::abs'):
                arg = self.eval_expr(children[1])
                return abs(arg)

            # User-defined function call
            if func_name in self.env.function_cursors:
                func_cursor = self.env.function_cursors[func_name]
                arg_nodes = []
                for c in children:
                    if c.kind in (CursorKind.TYPE_REF, CursorKind.NAMESPACE_REF, CursorKind.TEMPLATE_REF):
                        continue
                    if c.spelling == func_name and c.kind in (CursorKind.DECL_REF_EXPR, CursorKind.UNEXPOSED_EXPR):
                        continue
                    arg_nodes.append(c)

                args = [self.eval_expr(c) for c in arg_nodes]
                return self.call_function(func_cursor, args)

        elif kind == CursorKind.INIT_LIST_EXPR:
            children = list(curr.get_children())
            return [self.eval_expr(c) for c in children]

        raise InterpreterError(f"Unsupported expression node kind: {kind} ({curr.spelling})")

    # --- Assignment Execution ---

    def exec_assignment(self, lhs_node: Cursor, op: str, rhs_val: Any) -> Any:
        lhs_curr = self.unwrap(lhs_node)

        # 1. Variable assignment: x = rhs
        if lhs_curr.kind == CursorKind.DECL_REF_EXPR:
            var_name = lhs_curr.spelling
            type_str = self.env.current_scope.lookup_type(var_name) or ""

            if op != '=':
                found, old_val = self.env.current_scope.lookup(var_name)
                if not found:
                    raise InterpreterError(f"Undefined variable '{var_name}' in compound assignment")
                if op == '+=': rhs_val = old_val + rhs_val
                elif op == '-=': rhs_val = old_val - rhs_val
                elif op == '*=': rhs_val = old_val * rhs_val
                elif op == '/=': rhs_val = cpp_int_div(old_val, rhs_val)
                elif op == '%=': rhs_val = cpp_int_mod(old_val, rhs_val)

            return assign_var(var_name, rhs_val, type_str, self.env.current_scope, self.env)

        # 2. Member assignment: ptr->field = rhs or obj.field = rhs
        elif lhs_curr.kind == CursorKind.MEMBER_REF_EXPR:
            children = list(lhs_curr.get_children())
            base_node = children[0]
            field_name = lhs_curr.spelling
            tokens = [t.spelling for t in lhs_curr.get_tokens()]
            is_arrow = '->' in tokens

            if is_arrow:
                addr = self.eval_expr(base_node)
                self.env.heap.set_field(addr, field_name, rhs_val)
                return rhs_val
            else:
                base_obj = self.eval_expr(base_node)
                if isinstance(base_obj, dict):
                    base_obj[field_name] = rhs_val
                    return rhs_val

        # 3. Array / Vector element assignment: arr[i] = rhs
        elif lhs_curr.kind in (CursorKind.ARRAY_SUBSCRIPT_EXPR, CursorKind.CALL_EXPR):
            children = list(lhs_curr.get_children())
            arr_val = self.eval_expr(children[0])
            idx_val = self.eval_expr(children[1] if lhs_curr.kind == CursorKind.ARRAY_SUBSCRIPT_EXPR else children[2])
            arr_val[idx_val] = rhs_val
            return rhs_val

        raise InterpreterError(f"Unsupported LHS assignment target: {lhs_curr.kind}")

    # --- Statement Execution ---

    def exec_stmt(self, cursor: Cursor):
        curr = self.unwrap(cursor)
        wrapper_kinds = {CursorKind.UNEXPOSED_EXPR, CursorKind.PAREN_EXPR}
        for name in ('IMPLICIT_CAST_EXPR', 'CXX_FUNCTIONAL_CAST_EXPR', 'CSTYLE_CAST_EXPR'):
            if hasattr(CursorKind, name):
                wrapper_kinds.add(getattr(CursorKind, name))
        kind = cursor.kind if cursor.kind not in wrapper_kinds else curr.kind
        line_no = curr.location.line - self.header_lines_count

        if kind == CursorKind.COMPOUND_STMT:
            for child in curr.get_children():
                self.exec_stmt(child)

        elif kind == CursorKind.DECL_STMT:
            self.emit_step(line_no)
            for child in curr.get_children():
                if child.kind == CursorKind.VAR_DECL:
                    var_name = child.spelling
                    type_str = child.type.spelling
                    children = [ch for ch in child.get_children() if ch.kind not in (CursorKind.TYPE_REF, CursorKind.NAMESPACE_REF, CursorKind.TEMPLATE_REF)]
                    
                    if children:
                        init_val = self.eval_expr(children[0])
                    else:
                        if is_pointer_type(type_str):
                            init_val = "0x0000"
                        elif 'vector' in type_str:
                            init_val = []
                        elif type_str in self.env.struct_definitions:
                            init_val = copy.deepcopy(self.env.struct_definitions[type_str])
                        else:
                            init_val = 0

                    assign_var(var_name, init_val, type_str, self.env.current_scope, self.env)

        elif kind == CursorKind.IF_STMT:
            self.emit_step(line_no)
            children = list(curr.get_children())
            cond_val = self.eval_expr(children[0])
            if cond_val:
                self.exec_stmt(children[1])
            elif len(children) > 2:
                self.exec_stmt(children[2])

        elif kind == CursorKind.FOR_STMT:
            children = list(curr.get_children())
            init_node = children[0] if len(children) > 0 else None
            cond_node = children[1] if len(children) > 1 else None
            inc_node = children[2] if len(children) > 2 else None
            body_node = children[3] if len(children) > 3 else None

            self.env.push_scope("for_loop")
            try:
                if init_node:
                    if init_node.kind == CursorKind.DECL_STMT:
                        self.exec_stmt(init_node)
                    else:
                        self.eval_expr(init_node)

                iterations = 0
                while True:
                    if iterations >= self.max_loop_iterations:
                        raise ExecutionLimitError(f"Maximum loop iterations ({self.max_loop_iterations}) exceeded")
                    iterations += 1

                    if cond_node:
                        self.emit_step(line_no)
                        if not self.eval_expr(cond_node):
                            break
                    
                    try:
                        if body_node:
                            self.exec_stmt(body_node)
                    except ContinueException:
                        pass
                    except BreakException:
                        break

                    if inc_node:
                        self.eval_expr(inc_node)
            finally:
                self.env.pop_scope()

        elif kind == CursorKind.WHILE_STMT:
            children = list(curr.get_children())
            cond_node = children[0]
            body_node = children[1] if len(children) > 1 else None

            iterations = 0
            while True:
                if iterations >= self.max_loop_iterations:
                    raise ExecutionLimitError(f"Maximum loop iterations ({self.max_loop_iterations}) exceeded")
                iterations += 1

                self.emit_step(line_no)
                if not self.eval_expr(cond_node):
                    break

                try:
                    if body_node:
                        self.exec_stmt(body_node)
                except ContinueException:
                    pass
                except BreakException:
                    break

        elif kind == CursorKind.DO_STMT:
            children = list(curr.get_children())
            body_node = children[0]
            cond_node = children[1] if len(children) > 1 else None

            iterations = 0
            while True:
                if iterations >= self.max_loop_iterations:
                    raise ExecutionLimitError(f"Maximum loop iterations ({self.max_loop_iterations}) exceeded")
                iterations += 1

                try:
                    if body_node:
                        self.exec_stmt(body_node)
                except ContinueException:
                    pass
                except BreakException:
                    break

                if cond_node:
                    self.emit_step(line_no)
                    if not self.eval_expr(cond_node):
                        break

        elif kind == CursorKind.RETURN_STMT:
            self.emit_step(line_no, event_type="return")
            children = list(curr.get_children())
            ret_val = self.eval_expr(children[0]) if children else None
            raise ReturnException(ret_val)

        elif kind == CursorKind.NULL_STMT:
            pass

        else:
            self.emit_step(line_no)
            self.eval_expr(curr)

    # --- Function Execution ---

    def call_function(self, func_cursor: Cursor, args: List[Any]) -> Any:
        if len(self.env.call_stack) > self.max_recursion_depth:
            raise ExecutionLimitError(f"Maximum recursion depth ({self.max_recursion_depth}) exceeded")

        func_name = func_cursor.spelling
        params = []
        body_node = None
        for child in func_cursor.get_children():
            if child.kind == CursorKind.PARM_DECL:
                params.append((child.spelling, child.type.spelling))
            elif child.kind == CursorKind.COMPOUND_STMT:
                body_node = child

        callee_scope = self.env.push_function_frame(func_name)
        try:
            for (p_name, p_type), arg_val in zip(params, args):
                pass_argument(p_name, arg_val, p_type, callee_scope, self.env)

            if body_node:
                line_no = body_node.location.line - self.header_lines_count
                self.emit_step(line_no, event_type="call")
                self.exec_stmt(body_node)
            return None
        except ReturnException as ret:
            return ret.value
        finally:
            self.env.pop_scope()

    # --- Public Entry Point ---

    def interpret(self, code: str, entry_function_name: str, args: List[Any]) -> Tuple[List[Step], Any]:
        """Interprets C++ code starting at entry_function_name with given test arguments."""
        tu, self.header_lines_count = parse_cpp_ast(code, use_header_mocks=True)
        self.parse_struct_definitions(tu.cursor)

        if entry_function_name not in self.env.function_cursors:
            raise InterpreterError(f"Entry point function '{entry_function_name}' not found in C++ source")

        entry_cursor = self.env.function_cursors[entry_function_name]
        return_val = self.call_function(entry_cursor, args)
        return self.steps, return_val
