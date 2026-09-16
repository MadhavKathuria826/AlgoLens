"""
AlgoLens Universal State & Event Reducer
Implements the deterministic state reduction: State_{n+1} = reduce(State_n, Event_n)
Maintains the formal hierarchy: FRAME -> SCOPE -> BINDING -> VALUE -> OBJECT
"""

import copy
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from event_models import (
    AlgoLensEvent, UniversalValue, PrimitiveValue, ObjectRef, NullRef, DanglingRef, Uninitialized, ReferenceRef
)


def _parse_uval(raw_val: Any, fallback_type: str = "unknown") -> UniversalValue:
    """Helper to deterministically convert raw payload values into UniversalValue."""
    if isinstance(raw_val, dict):
        k = raw_val.get("kind")
        if k == "primitive":
            return PrimitiveValue(**raw_val)
        elif k == "object_ref":
            return ObjectRef(**raw_val)
        elif k == "null_ref":
            return NullRef()
        elif k == "dangling_ref":
            return DanglingRef(**raw_val)
        elif k == "reference":
            return ReferenceRef(**raw_val)
        elif k == "uninitialized":
            return Uninitialized()
        else:
            return PrimitiveValue(type_name=fallback_type, value=raw_val.get("value", str(raw_val)))
    elif isinstance(raw_val, UniversalValue):
        return raw_val
    elif isinstance(raw_val, str):
        if raw_val in ("0x0000", "nullptr", "NULL"):
            return NullRef()
        elif raw_val.startswith("obj_"):
            return ObjectRef(object_id=raw_val)
        else:
            return PrimitiveValue(type_name=fallback_type, value=raw_val)
    elif raw_val is None:
        return NullRef()
    return PrimitiveValue(type_name=fallback_type, value=raw_val)


class UniversalBinding(BaseModel):
    binding_id: str
    name: str
    type_decl: str = ""
    value: UniversalValue = Field(default_factory=Uninitialized)
    scope_id: str = ""


class UniversalScope(BaseModel):
    scope_id: str
    frame_id: str
    parent_scope_id: Optional[str] = None
    kind: str = "block"  # "function", "block", "loop", "branch"
    binding_map: Dict[str, str] = Field(default_factory=dict)  # var_name -> binding_id


class UniversalFrame(BaseModel):
    frame_id: str
    func_name: str
    parent_frame_id: Optional[str] = None
    active_scope_id: str = ""
    args: Dict[str, UniversalValue] = Field(default_factory=dict)
    return_value: Optional[UniversalValue] = None


class UniversalHeapObject(BaseModel):
    object_id: str
    type_name: str
    fields: Dict[str, UniversalValue] = Field(default_factory=dict)
    elements: List[UniversalValue] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
    is_alive: bool = True


class UniversalRuntimeState(BaseModel):
    current_line: int = 0
    step_sequence: int = 0
    active_frame_id: Optional[str] = None
    call_stack: List[str] = Field(default_factory=list)  # List of frame_ids
    frames: Dict[str, UniversalFrame] = Field(default_factory=dict)
    scopes: Dict[str, UniversalScope] = Field(default_factory=dict)
    bindings: Dict[str, UniversalBinding] = Field(default_factory=dict)
    heap: Dict[str, UniversalHeapObject] = Field(default_factory=dict)
    containers: Dict[str, Any] = Field(default_factory=dict)  # container_id -> state

    def get_current_frame(self) -> Optional[UniversalFrame]:
        if self.call_stack:
            return self.frames.get(self.call_stack[-1])
        return None

    def get_current_scope(self) -> Optional[UniversalScope]:
        frame = self.get_current_frame()
        if frame and frame.active_scope_id:
            return self.scopes.get(frame.active_scope_id)
        return None

    def get_visible_bindings(self) -> Dict[str, UniversalBinding]:
        """Traverses up the lexical scope hierarchy in the active frame to find visible bindings."""
        visible: Dict[str, UniversalBinding] = {}
        curr_scope = self.get_current_scope()
        while curr_scope:
            for name, b_id in curr_scope.binding_map.items():
                if name not in visible and b_id in self.bindings:
                    visible[name] = self.bindings[b_id]
            if curr_scope.parent_scope_id:
                curr_scope = self.scopes.get(curr_scope.parent_scope_id)
            else:
                break
        return visible


class UniversalStateReducer:
    """
    Deterministic state reducer. Applies events sequentially to build or update UniversalRuntimeState.
    """

    @staticmethod
    def reduce(state: UniversalRuntimeState, event: AlgoLensEvent) -> UniversalRuntimeState:
        ev_type = event.event_type
        payload = event.payload
        state.current_line = event.line
        state.step_sequence = event.seq

        # 1. Execution & Frame Lifecycle
        if ev_type == "PROG_START":
            entry_func = payload.get("entry_function", "main")
            frame_id = event.frame_id or "frame_0"
            scope_id = event.scope_id or "scope_0"

            frame = UniversalFrame(
                frame_id=frame_id,
                func_name=entry_func,
                active_scope_id=scope_id,
                args=payload.get("args", {})
            )
            scope = UniversalScope(
                scope_id=scope_id,
                frame_id=frame_id,
                kind="function"
            )
            state.frames[frame_id] = frame
            state.scopes[scope_id] = scope
            state.call_stack.append(frame_id)
            state.active_frame_id = frame_id

        elif ev_type == "FRAME_PUSH":
            frame_id = payload.get("frame_id") or event.frame_id
            func_name = payload.get("func_name", "anonymous")
            parent_id = state.call_stack[-1] if state.call_stack else None
            scope_id = event.scope_id or f"scope_{len(state.scopes)}"

            frame = UniversalFrame(
                frame_id=frame_id,
                func_name=func_name,
                parent_frame_id=parent_id,
                active_scope_id=scope_id,
                args=payload.get("args", {})
            )
            scope = UniversalScope(
                scope_id=scope_id,
                frame_id=frame_id,
                kind="function"
            )
            state.frames[frame_id] = frame
            state.scopes[scope_id] = scope
            state.call_stack.append(frame_id)
            state.active_frame_id = frame_id

        elif ev_type == "FRAME_POP":
            if state.call_stack:
                popped_id = state.call_stack.pop()
                if popped_id in state.frames and "return_value" in payload:
                    raw_ret = payload["return_value"]
                    if raw_ret is None:
                        ret_u = None
                    elif isinstance(raw_ret, dict) and "kind" in raw_ret:
                        k = raw_ret["kind"]
                        if k == "primitive":
                            ret_u = PrimitiveValue(**raw_ret)
                        elif k == "object_ref":
                            ret_u = ObjectRef(**raw_ret)
                        elif k == "null_ref":
                            ret_u = NullRef()
                        elif k == "dangling_ref":
                            ret_u = DanglingRef(**raw_ret)
                        else:
                            ret_u = Uninitialized()
                    elif isinstance(raw_ret, UniversalValue):
                        ret_u = raw_ret
                    else:
                        ret_u = PrimitiveValue(type_name="unknown", value=raw_ret)
                    state.frames[popped_id].return_value = ret_u
                state.active_frame_id = state.call_stack[-1] if state.call_stack else None

        elif ev_type == "SCOPE_ENTER":
            scope_id = event.scope_id
            frame = state.get_current_frame()
            if frame:
                parent_scope_id = frame.active_scope_id
                new_scope = UniversalScope(
                    scope_id=scope_id,
                    frame_id=frame.frame_id,
                    parent_scope_id=parent_scope_id,
                    kind=payload.get("kind", "block")
                )
                state.scopes[scope_id] = new_scope
                frame.active_scope_id = scope_id

        elif ev_type == "SCOPE_EXIT":
            frame = state.get_current_frame()
            if frame and frame.active_scope_id in state.scopes:
                curr_s = state.scopes[frame.active_scope_id]
                if curr_s.parent_scope_id:
                    frame.active_scope_id = curr_s.parent_scope_id

        # 2. Variable Bindings
        elif ev_type == "VAR_DECLARE":
            b_id = payload.get("binding_id") or f"binding_{len(state.bindings)}"
            name = payload["name"]
            type_decl = payload.get("type_decl", "")
            raw_val = payload.get("value")
            u_val = _parse_uval(raw_val, type_decl or "unknown")

            binding = UniversalBinding(
                binding_id=b_id,
                name=name,
                type_decl=type_decl,
                value=u_val,
                scope_id=event.scope_id
            )
            state.bindings[b_id] = binding

            scope = state.scopes.get(event.scope_id) or state.get_current_scope()
            if scope:
                scope.binding_map[name] = b_id

        elif ev_type == "VAR_WRITE":
            b_id = payload.get("binding_id")
            name = payload.get("name")
            raw_val = payload.get("new_value")
            u_val = _parse_uval(raw_val)

            target_binding = None
            if b_id and b_id in state.bindings:
                target_binding = state.bindings[b_id]
            elif name:
                visible = state.get_visible_bindings()
                if name in visible:
                    target_binding = visible[name]

            if target_binding:
                if isinstance(target_binding.value, ReferenceRef):
                    # Write through reference to referent
                    ref = target_binding.value
                    if ref.target_binding_id and ref.target_binding_id in state.bindings:
                        state.bindings[ref.target_binding_id].value = u_val
                    elif ref.target_name:
                        vis = state.get_visible_bindings()
                        if ref.target_name in vis:
                            vis[ref.target_name].value = u_val
                    elif ref.target_object_id and ref.target_object_id in state.heap:
                        f_name = ref.target_field or "value"
                        state.heap[ref.target_object_id].fields[f_name] = u_val
                else:
                    target_binding.value = u_val

        # 3. Heap Objects
        elif ev_type == "OBJECT_ALLOCATE":
            obj_id = payload["object_id"]
            type_name = payload.get("type_name", "Object")
            raw_fields = payload.get("fields", {})
            parsed_fields: Dict[str, UniversalValue] = {}

            for f_name, f_val in raw_fields.items():
                parsed_fields[f_name] = _parse_uval(f_val)

            heap_obj = UniversalHeapObject(
                object_id=obj_id,
                type_name=type_name,
                fields=parsed_fields,
                meta=payload.get("debug_meta", {})
            )
            state.heap[obj_id] = heap_obj

        elif ev_type == "OBJECT_MUTATE":
            obj_id = payload["object_id"]
            field = payload["field"]
            raw_val = payload.get("new_value")
            u_val = _parse_uval(raw_val)

            if obj_id not in state.heap:
                state.heap[obj_id] = UniversalHeapObject(
                    object_id=obj_id,
                    type_name=payload.get("type_name", "Object"),
                    fields={},
                    meta=payload.get("debug_meta", {})
                )

            parts = field.split(".")
            if len(parts) == 1:
                state.heap[obj_id].fields[field] = u_val
            else:
                curr = state.heap[obj_id].fields
                for p in parts[:-1]:
                    if p not in curr or not isinstance(curr[p], dict):
                        curr[p] = {}
                    curr = curr[p]
                curr[parts[-1]] = u_val

        elif ev_type in ("OBJECT_DEALLOCATE", "OBJECT_FREE"):
            obj_id = payload["object_id"]
            if obj_id in state.heap:
                state.heap[obj_id].is_alive = False

        # 4. Containers
        elif ev_type == "CONTAINER_OP":
            c_id = payload["container_id"]
            op = payload["op"]
            kind = payload["kind"]
            if c_id not in state.containers:
                state.containers[c_id] = {"kind": kind, "elements": [] if kind in ("ARRAY", "STACK", "QUEUE", "HEAP") else {}}

            c_state = state.containers[c_id]
            if op == "PUSH":
                for v in (payload.get("values") or []):
                    val_repr = v.get("value") if isinstance(v, dict) and "value" in v else v
                    c_state["elements"].append(val_repr)
            elif op == "POP":
                if c_state["elements"]:
                    c_state["elements"].pop()
            elif op == "SET_INDEX":
                indices = payload.get("indices")
                vals = payload.get("values")
                if indices and vals and len(indices) == len(vals):
                    for idx, v in zip(indices, vals):
                        val_repr = v.get("value") if isinstance(v, dict) and "value" in v else v
                        if isinstance(c_state["elements"], list):
                            while len(c_state["elements"]) <= idx:
                                c_state["elements"].append(None)
                            c_state["elements"][idx] = val_repr
                        elif isinstance(c_state["elements"], dict):
                            c_state["elements"][str(idx)] = val_repr
                elif vals is not None:
                    c_state["elements"] = []
                    for v in vals:
                        val_repr = v.get("value") if isinstance(v, dict) and "value" in v else v
                        c_state["elements"].append(val_repr)
            elif op == "INSERT":
                meta = payload.get("meta")
                if meta is not None and isinstance(meta, dict):
                    if not isinstance(c_state["elements"], dict):
                        c_state["elements"] = {}
                    for mk, mv in meta.items():
                        mval = mv.get("value") if isinstance(mv, dict) and "value" in mv else mv
                        c_state["elements"][mk] = mval
            elif op == "ERASE":
                meta = payload.get("meta")
                indices = payload.get("indices")
                if meta and isinstance(meta, dict) and isinstance(c_state["elements"], dict):
                    for mk in meta:
                        c_state["elements"].pop(mk, None)
                if indices and isinstance(c_state["elements"], dict):
                    for idx in indices:
                        c_state["elements"].pop(str(idx), None)
            elif op == "CLEAR":
                if isinstance(c_state["elements"], list):
                    c_state["elements"] = []
                else:
                    c_state["elements"] = {}

        return state

    @staticmethod
    def reduce_inverse(state: UniversalRuntimeState, event: AlgoLensEvent) -> UniversalRuntimeState:
        ev_type = event.event_type
        payload = event.payload
        state.step_sequence = max(0, event.seq - 1)
        if event.prev_line is not None:
            state.current_line = event.prev_line

        # 1. Variable Binding Inversion
        if ev_type == "VAR_WRITE":
            b_id = payload.get("binding_id")
            name = payload.get("name")
            old_raw = payload.get("old_value")
            old_u = _parse_uval(old_raw)

            target_binding = None
            if b_id and b_id in state.bindings:
                target_binding = state.bindings[b_id]
            elif name:
                vis = state.get_visible_bindings()
                if name in vis:
                    target_binding = vis[name]

            if target_binding:
                if isinstance(target_binding.value, ReferenceRef):
                    ref = target_binding.value
                    if ref.target_binding_id and ref.target_binding_id in state.bindings:
                        state.bindings[ref.target_binding_id].value = old_u
                    elif ref.target_name:
                        vis = state.get_visible_bindings()
                        if ref.target_name in vis:
                            vis[ref.target_name].value = old_u
                    elif ref.target_object_id and ref.target_object_id in state.heap:
                        f_name = ref.target_field or "value"
                        state.heap[ref.target_object_id].fields[f_name] = old_u
                else:
                    target_binding.value = old_u

        elif ev_type == "VAR_DECLARE":
            b_id = payload.get("binding_id")
            name = payload.get("name")
            if b_id and b_id in state.bindings:
                b = state.bindings.pop(b_id)
                scope = state.scopes.get(b.scope_id)
                if scope and name in scope.binding_map:
                    scope.binding_map.pop(name, None)
            elif name:
                scope = state.get_current_scope()
                if scope and name in scope.binding_map:
                    b_id = scope.binding_map.pop(name)
                    state.bindings.pop(b_id, None)

            if name and name in state.containers:
                state.containers.pop(name, None)

        # 2. Object Mutation Inversion
        elif ev_type == "OBJECT_MUTATE":
            obj_id = payload["object_id"]
            field = payload["field"]
            old_raw = payload.get("old_value")
            old_u = _parse_uval(old_raw)

            if obj_id in state.heap:
                parts = field.split(".")
                if len(parts) == 1:
                    if isinstance(old_u, Uninitialized):
                        state.heap[obj_id].fields.pop(field, None)
                    else:
                        state.heap[obj_id].fields[field] = old_u
                else:
                    curr = state.heap[obj_id].fields
                    for p in parts[:-1]:
                        if p not in curr or not isinstance(curr[p], dict):
                            curr[p] = {}
                        curr = curr[p]
                    if isinstance(old_u, Uninitialized):
                        curr.pop(parts[-1], None)
                    else:
                        curr[parts[-1]] = old_u

        elif ev_type in ("OBJECT_DEALLOCATE", "OBJECT_FREE"):
            obj_id = payload["object_id"]
            if obj_id in state.heap:
                state.heap[obj_id].is_alive = True
                if "old_fields" in payload and payload["old_fields"]:
                    old_f = {}
                    for fk, fv in (payload.get("old_fields") or {}).items():
                        old_f[fk] = _parse_uval(fv)
                    state.heap[obj_id].fields = old_f
            elif "old_fields" in payload:
                old_f = {}
                for fk, fv in (payload.get("old_fields") or {}).items():
                    old_f[fk] = _parse_uval(fv)
                state.heap[obj_id] = UniversalHeapObject(
                    object_id=obj_id,
                    type_name=payload.get("type_name", "Object"),
                    fields=old_f,
                    is_alive=True
                )

        elif ev_type == "OBJECT_ALLOCATE":
            obj_id = payload["object_id"]
            state.heap.pop(obj_id, None)

        # 3. Container Operation Inversion
        elif ev_type == "CONTAINER_OP":
            c_id = payload["container_id"]
            op = payload["op"]
            if c_id in state.containers:
                c_state = state.containers[c_id]
                old_vals = payload.get("old_values")
                old_meta = payload.get("old_meta")
                if op == "POP":
                    if old_vals is not None:
                        for v in old_vals:
                            val_repr = v.get("value") if isinstance(v, dict) and "value" in v else v
                            c_state["elements"].append(val_repr)
                elif op == "PUSH":
                    count = len(payload.get("values") or [1])
                    for _ in range(count):
                        if c_state["elements"]:
                            c_state["elements"].pop()
                elif op == "INSERT":
                    if old_meta is not None and isinstance(old_meta, dict):
                        c_state["elements"].update(old_meta)
                    else:
                        meta = payload.get("meta")
                        if meta and isinstance(meta, dict) and isinstance(c_state["elements"], dict):
                            for k in meta:
                                c_state["elements"].pop(k, None)
                elif op == "ERASE":
                    if old_meta is not None and isinstance(old_meta, dict):
                        c_state["elements"].update(old_meta)
                    elif old_vals is not None:
                        for v in old_vals:
                            val_repr = v.get("value") if isinstance(v, dict) and "value" in v else v
                            c_state["elements"].append(val_repr)
                elif op == "CLEAR":
                    if old_meta is not None and isinstance(old_meta, dict):
                        c_state["elements"] = copy.deepcopy(old_meta)
                    elif old_vals is not None:
                        c_state["elements"] = []
                        for v in old_vals:
                            val_repr = v.get("value") if isinstance(v, dict) and "value" in v else v
                            c_state["elements"].append(val_repr)
                elif old_vals is not None:
                    c_state["elements"] = []
                    for v in old_vals:
                        val_repr = v.get("value") if isinstance(v, dict) and "value" in v else v
                        c_state["elements"].append(val_repr)
                elif old_meta is not None and isinstance(old_meta, dict):
                    c_state["elements"] = copy.deepcopy(old_meta)
                else:
                    state.containers.pop(c_id, None)

        # 4. Scope and Frame Inversion
        elif ev_type == "SCOPE_ENTER":
            frame = state.get_current_frame()
            if frame and frame.active_scope_id in state.scopes:
                curr_s = state.scopes[frame.active_scope_id]
                if curr_s.parent_scope_id:
                    frame.active_scope_id = curr_s.parent_scope_id
                state.scopes.pop(event.scope_id, None)

        elif ev_type == "SCOPE_EXIT":
            frame = state.get_current_frame()
            if frame and event.scope_id in state.scopes:
                frame.active_scope_id = event.scope_id

        elif ev_type == "FRAME_PUSH":
            frame_id = payload.get("frame_id") or event.frame_id
            if state.call_stack and state.call_stack[-1] == frame_id:
                state.call_stack.pop()
            state.frames.pop(frame_id, None)
            state.active_frame_id = state.call_stack[-1] if state.call_stack else None

        elif ev_type == "FRAME_POP":
            frame_id = event.frame_id
            if frame_id in state.frames:
                state.call_stack.append(frame_id)
                state.active_frame_id = frame_id
                state.frames[frame_id].return_value = None

        elif ev_type == "PROG_START":
            frame_id = event.frame_id or "frame_0"
            scope_id = event.scope_id or "scope_0"
            state.frames.pop(frame_id, None)
            state.scopes.pop(scope_id, None)
            if state.call_stack and state.call_stack[-1] == frame_id:
                state.call_stack.pop()
            state.active_frame_id = state.call_stack[-1] if state.call_stack else None

        return state
