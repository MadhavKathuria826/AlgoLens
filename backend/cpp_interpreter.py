import copy
from typing import Dict, Any, List, Optional, Tuple, Union
from clang.cindex import Index, CursorKind, TypeKind, Cursor
from cpp_classifier import parse_cpp_ast
from models import Step, VisualizationData

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
    """Wraps fixed-width integers on overflow per 2's complement C++ semantics."""
    if not isinstance(val, int) or isinstance(val, bool):
        return val
    type_s = (type_str or "int").lower()
    if 'short' in type_s:
        return (val + 32768) % 65536 - 32768
    elif 'char' in type_s and 'unsigned' not in type_s:
        return (val + 128) % 256 - 128
    elif 'int' in type_s or 'long' in type_s:
        return (val + 2147483648) % 4294967296 - 2147483648
    return val

def is_pointer_type(type_str: str, val: Any = None) -> bool:
    """Checks if static type or runtime value represents a pointer address."""
    if type_str and ('*' in type_str or type_str.endswith('*')):
        return True
    if isinstance(val, str) and (val.startswith("0x") or val in ("nullptr", "NULL", "0")):
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
        self._memory[addr] = initial_fields.copy() if initial_fields is not None else {}
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
        if self.parent and self.parent.parent is not None: # chain up to frame root
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
