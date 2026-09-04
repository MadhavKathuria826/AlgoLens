"""
AlgoLens Event Observer
Hooks into execution without altering execution logic to emit AlgoLens Event Protocol v2.1 events.
Maps host/interpreter memory addresses to synthetic universal object IDs (obj_N).
"""

import copy
from typing import Dict, Any, List, Optional
from event_models import (
    AlgoLensEvent, UniversalValue, PrimitiveValue, ObjectRef, NullRef, Uninitialized,
    make_object_id, make_frame_id, make_scope_id, make_binding_id
)

def dump_val(v: Any) -> Any:
    if hasattr(v, "model_dump"):
        return v.model_dump()
    elif hasattr(v, "dict"):
        return v.dict()
    return v


class EventObserver:
    """
    Collects execution events from runtime interpreters and adapters.
    Maintains synthetic identity mappings to isolate host pointers.
    """

    def __init__(self):
        self.events: List[AlgoLensEvent] = []
        self.seq_counter = 0

        # Synthetic ID counters
        self.obj_counter = 0
        self.frame_counter = 0
        self.scope_counter = 0
        self.binding_counter = 0

        # Address mapping: native_addr (e.g. "0x1000") -> synthetic obj_id ("obj_1")
        self.addr_to_obj_id: Dict[str, str] = {}
        self.var_to_binding_id: Dict[str, str] = {}

        # History tracking for event reversibility
        self.binding_values: Dict[str, Any] = {}
        self.object_fields: Dict[str, Dict[str, Any]] = {}
        self.container_history: Dict[str, Any] = {}

        # Current frame and scope tracking
        self.frame_stack: List[str] = []
        self.scope_stack: List[str] = []
        self.current_line = 0
        self.last_emitted_line = 0

    @property
    def current_frame_id(self) -> str:
        return self.frame_stack[-1] if self.frame_stack else "frame_0"

    @property
    def current_scope_id(self) -> str:
        return self.scope_stack[-1] if self.scope_stack else "scope_0"

    def get_or_create_obj_id(self, addr: str) -> str:
        if addr in ("0x0000", "nullptr", "NULL", None):
            return "null"
        if addr.startswith("obj_"):
            return addr
        if addr not in self.addr_to_obj_id:
            self.obj_counter += 1
            self.addr_to_obj_id[addr] = make_object_id(self.obj_counter)
        return self.addr_to_obj_id[addr]

    def to_universal_value(self, val: Any, type_str: str = "") -> UniversalValue:
        if val is None:
            return NullRef()
        if isinstance(val, bool):
            return PrimitiveValue(type_name="bool", value=val)
        if isinstance(val, int):
            return PrimitiveValue(type_name="int", value=val)
        if isinstance(val, float):
            return PrimitiveValue(type_name="float", value=val)
        if isinstance(val, str):
            if val in ("0x0000", "nullptr", "NULL"):
                return NullRef()
            if val.startswith("0x"):
                obj_id = self.get_or_create_obj_id(val)
                return ObjectRef(object_id=obj_id)
            if val.startswith("obj_"):
                return ObjectRef(object_id=val)
            return PrimitiveValue(type_name="string", value=val)
        return PrimitiveValue(type_name=type_str or "unknown", value=str(val))

    def emit(self, event_type: str, payload: Dict[str, Any], debug_meta: Optional[Dict[str, Any]] = None):
        prev_l = self.last_emitted_line
        ev = AlgoLensEvent(
            seq=self.seq_counter,
            line=self.current_line,
            prev_line=prev_l,
            event_type=event_type,
            frame_id=self.current_frame_id,
            scope_id=self.current_scope_id,
            payload=payload,
            debug_meta=debug_meta
        )
        self.events.append(ev)
        self.seq_counter += 1
        self.last_emitted_line = self.current_line

    # --- Lifecycle Hooks ---

    def on_prog_start(self, entry_func: str, args: List[Any] = None):
        self.frame_counter += 1
        self.scope_counter += 1
        frame_id = make_frame_id(self.frame_counter)
        scope_id = make_scope_id(self.scope_counter)
        self.frame_stack.append(frame_id)
        self.scope_stack.append(scope_id)

        parsed_args = {}
        if args:
            for idx, arg_val in enumerate(args):
                parsed_args[f"arg_{idx}"] = dump_val(self.to_universal_value(arg_val))

        self.emit("PROG_START", {
            "entry_function": entry_func,
            "args": parsed_args
        })

    def on_frame_push(self, func_name: str, args: Dict[str, Any] = None):
        self.frame_counter += 1
        self.scope_counter += 1
        frame_id = make_frame_id(self.frame_counter)
        scope_id = make_scope_id(self.scope_counter)
        parent_id = self.frame_stack[-1] if self.frame_stack else None

        self.frame_stack.append(frame_id)
        self.scope_stack.append(scope_id)

        parsed_args = {}
        if args:
            for k, v in args.items():
                parsed_args[k] = dump_val(self.to_universal_value(v))

        self.emit("FRAME_PUSH", {
            "frame_id": frame_id,
            "func_name": func_name,
            "parent_frame_id": parent_id,
            "args": parsed_args
        })

    def on_frame_pop(self, return_val: Any = None):
        u_ret = dump_val(self.to_universal_value(return_val)) if return_val is not None else None
        self.emit("FRAME_POP", {
            "return_value": u_ret
        })
        if self.frame_stack:
            self.frame_stack.pop()
        if self.scope_stack:
            self.scope_stack.pop()

    def on_scope_enter(self, kind: str = "block"):
        self.scope_counter += 1
        scope_id = make_scope_id(self.scope_counter)
        self.scope_stack.append(scope_id)
        self.emit("SCOPE_ENTER", {"kind": kind})

    def on_scope_exit(self):
        self.emit("SCOPE_EXIT", {})
        if len(self.scope_stack) > 1:
            self.scope_stack.pop()

    def on_var_declare(self, name: str, val: Any, type_str: str = ""):
        self.binding_counter += 1
        b_id = make_binding_id(self.binding_counter)
        self.var_to_binding_id[name] = b_id
        self.binding_values[name] = val

        self.emit("VAR_DECLARE", {
            "binding_id": b_id,
            "name": name,
            "type_decl": type_str,
            "value": dump_val(self.to_universal_value(val, type_str))
        })

    def on_var_write(self, name: str, val: Any, type_str: str = ""):
        b_id = self.var_to_binding_id.get(name) or make_binding_id(self.binding_counter)
        old_val = self.binding_values.get(name)
        self.binding_values[name] = val
        old_val_dump = dump_val(self.to_universal_value(old_val, type_str)) if old_val is not None else {"kind": "uninitialized"}

        self.emit("VAR_WRITE", {
            "binding_id": b_id,
            "name": name,
            "old_value": old_val_dump,
            "new_value": dump_val(self.to_universal_value(val, type_str))
        })

    def on_object_allocate(self, native_addr: str, type_name: str, fields: Dict[str, Any] = None):
        obj_id = self.get_or_create_obj_id(native_addr)
        self.object_fields[obj_id] = copy.deepcopy(fields) if fields else {}
        parsed_fields = {}
        if fields:
            for k, v in fields.items():
                parsed_fields[k] = dump_val(self.to_universal_value(v))

        self.emit("OBJECT_ALLOCATE", {
            "object_id": obj_id,
            "type_name": type_name,
            "fields": parsed_fields
        }, debug_meta={"native_addr": native_addr})

    def on_object_mutate(self, native_addr: str, field: str, new_val: Any):
        obj_id = self.get_or_create_obj_id(native_addr)
        old_val = self.object_fields.get(obj_id, {}).get(field)
        self.object_fields.setdefault(obj_id, {})[field] = new_val
        old_val_dump = dump_val(self.to_universal_value(old_val)) if old_val is not None else {"kind": "uninitialized"}

        self.emit("OBJECT_MUTATE", {
            "object_id": obj_id,
            "field": field,
            "old_value": old_val_dump,
            "new_value": dump_val(self.to_universal_value(new_val))
        }, debug_meta={"native_addr": native_addr})

    def on_container_op(self, c_id: str, kind: str, op: str, indices: List[int] = None, values: List[Any] = None, meta: Dict[str, Any] = None):
        old_history = self.container_history.get(c_id)
        if values is not None:
            self.container_history[c_id] = copy.deepcopy(values)
        elif meta is not None:
            self.container_history[c_id] = copy.deepcopy(meta)

        parsed_vals = [dump_val(self.to_universal_value(v)) for v in values] if values is not None else None
        old_parsed_vals = [dump_val(self.to_universal_value(v)) for v in old_history] if isinstance(old_history, list) else None
        old_meta = copy.deepcopy(old_history) if isinstance(old_history, dict) else None

        self.emit("CONTAINER_OP", {
            "container_id": c_id,
            "kind": kind,
            "op": op,
            "indices": indices,
            "values": parsed_vals,
            "old_values": old_parsed_vals,
            "meta": meta,
            "old_meta": old_meta
        })

    def on_step_line(self, line_number: int):
        self.current_line = line_number
        self.emit("STEP_LINE", {
            "line": line_number
        })
