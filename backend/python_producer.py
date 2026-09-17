"""
AlgoLens Python Runtime Producer (Milestone 7)
Implements LanguageRuntimeProducer and Universal Event Protocol for Python.
Provides:
1. Real Python execution via sys.settrace hooks
2. Deterministic synthetic object identity & aliasing isolation (ObjectRegistry)
3. Universal Value Model (int, float, bool, None, str, list, tuple, dict, set)
4. Comprehensive mutation tracking (append, pop, clear, insert, update, erase)
5. Clean stdout / event stream demultiplexing
6. Strict timeout and max_events enforcement
7. Zero Python-specific state leakage into UniversalStateReducer
"""

import os
import sys
import ast
import time
import copy
import inspect
import io
import contextlib
import traceback
from typing import Dict, Any, List, Optional, Tuple, Set

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from event_models import (
    AlgoLensEvent,
    UniversalValue,
    PrimitiveValue,
    ObjectRef,
    NullRef,
    Uninitialized,
    ReferenceRef,
    TraceTruncatedPayload
)
from runtime_contract import ExecutionResult, LanguageRuntimeProducer


class TraceLimitReached(Exception):
    """Internal exception raised when max_events ceiling is encountered."""
    pass


class PythonObjectRegistry:
    """
    Manages synthetic object IDs (obj_0, obj_1, ...) and state tracking for Python reference objects.
    Preserves object identity, aliasing, and container mutation detection.
    Guarantees no raw Python memory addresses (id()) leak into universal events.
    """

    def __init__(self, tracer: "_PythonTracer"):
        self.tracer = tracer
        self._id_to_obj_id: Dict[int, str] = {}
        self._tracked_objects: Dict[str, Any] = {}
        self._snapshots: Dict[str, Any] = {}
        self._object_seq = 0

    def reset(self):
        self._id_to_obj_id.clear()
        self._tracked_objects.clear()
        self._snapshots.clear()
        self._object_seq = 0

    def _mint_object_id(self) -> str:
        obj_id = f"obj_{self._object_seq}"
        self._object_seq += 1
        return obj_id

    def to_universal_value(self, val: Any) -> UniversalValue:
        """Maps a Python runtime value into the universal state model."""
        if val is None:
            return NullRef()
        if isinstance(val, bool):
            return PrimitiveValue(type_name="bool", value=val)
        if isinstance(val, int):
            return PrimitiveValue(type_name="int", value=val)
        if isinstance(val, float):
            return PrimitiveValue(type_name="float", value=val)
        if isinstance(val, str):
            return PrimitiveValue(type_name="string", value=val)

        # Reference / Container Types
        if isinstance(val, (list, dict, set, tuple)):
            py_id = id(val)
            if py_id in self._id_to_obj_id:
                return ObjectRef(object_id=self._id_to_obj_id[py_id])

            # New allocation
            obj_id = self._mint_object_id()
            self._id_to_obj_id[py_id] = obj_id
            self._tracked_objects[obj_id] = val

            fields: Dict[str, UniversalValue] = {}
            if isinstance(val, list):
                type_name = "list"
                self._snapshots[obj_id] = [copy.deepcopy(x) if not isinstance(x, (list, dict, set, tuple)) else x for x in val]
                for i, elem in enumerate(val):
                    fields[str(i)] = self.to_universal_value(elem)
                fields["length"] = PrimitiveValue(type_name="int", value=len(val))
            elif isinstance(val, tuple):
                type_name = "tuple"
                self._snapshots[obj_id] = tuple(val)
                for i, elem in enumerate(val):
                    fields[str(i)] = self.to_universal_value(elem)
                fields["length"] = PrimitiveValue(type_name="int", value=len(val))
            elif isinstance(val, dict):
                type_name = "dict"
                self._snapshots[obj_id] = {k: copy.deepcopy(v) if not isinstance(v, (list, dict, set, tuple)) else v for k, v in val.items()}
                for k, v in val.items():
                    fields[str(k)] = self.to_universal_value(v)
                fields["size"] = PrimitiveValue(type_name="int", value=len(val))
            elif isinstance(val, set):
                type_name = "set"
                self._snapshots[obj_id] = set(val)
                for elem in sorted(val, key=lambda x: str(x)):
                    fields[str(elem)] = self.to_universal_value(elem)
                fields["size"] = PrimitiveValue(type_name="int", value=len(val))
            else:
                type_name = type(val).__name__
                self._snapshots[obj_id] = str(val)

            # Emit OBJECT_ALLOCATE event
            self.tracer.emit_event(
                event_type="OBJECT_ALLOCATE",
                payload={
                    "object_id": obj_id,
                    "type_name": type_name,
                    "fields": {k: (v.model_dump() if hasattr(v, "model_dump") else v.dict()) for k, v in fields.items()}
                }
            )
            return ObjectRef(object_id=obj_id)

        # Fallback for other objects
        py_id = id(val)
        if py_id in self._id_to_obj_id:
            return ObjectRef(object_id=self._id_to_obj_id[py_id])
        obj_id = self._mint_object_id()
        self._id_to_obj_id[py_id] = obj_id
        self._tracked_objects[obj_id] = val
        self._snapshots[obj_id] = str(val)
        self.tracer.emit_event(
            event_type="OBJECT_ALLOCATE",
            payload={
                "object_id": obj_id,
                "type_name": type(val).__name__,
                "fields": {"value": PrimitiveValue(type_name="string", value=str(val)).model_dump()}
            }
        )
        return ObjectRef(object_id=obj_id)

    def detect_mutations(self):
        """Scans tracked objects and emits OBJECT_MUTATE events for any modified state."""
        for obj_id, live_obj in list(self._tracked_objects.items()):
            if isinstance(live_obj, list):
                old_snap = self._snapshots[obj_id]
                new_elems = list(live_obj)
                if new_elems != old_snap:
                    old_len = len(old_snap)
                    new_len = len(new_elems)
                    min_len = min(old_len, new_len)
                    for i in range(min_len):
                        if old_snap[i] != new_elems[i]:
                            old_u = self.to_universal_value(old_snap[i])
                            new_u = self.to_universal_value(new_elems[i])
                            self.tracer.emit_event(
                                event_type="OBJECT_MUTATE",
                                payload={
                                    "object_id": obj_id,
                                    "field": str(i),
                                    "old_value": old_u.model_dump() if hasattr(old_u, "model_dump") else old_u.dict(),
                                    "new_value": new_u.model_dump() if hasattr(new_u, "model_dump") else new_u.dict()
                                }
                            )
                    if new_len > old_len:
                        for i in range(old_len, new_len):
                            new_u = self.to_universal_value(new_elems[i])
                            self.tracer.emit_event(
                                event_type="OBJECT_MUTATE",
                                payload={
                                    "object_id": obj_id,
                                    "field": str(i),
                                    "old_value": Uninitialized().model_dump(),
                                    "new_value": new_u.model_dump() if hasattr(new_u, "model_dump") else new_u.dict()
                                }
                            )
                    elif new_len < old_len:
                        for i in range(new_len, old_len):
                            old_u = self.to_universal_value(old_snap[i])
                            self.tracer.emit_event(
                                event_type="OBJECT_MUTATE",
                                payload={
                                    "object_id": obj_id,
                                    "field": str(i),
                                    "old_value": old_u.model_dump() if hasattr(old_u, "model_dump") else old_u.dict(),
                                    "new_value": Uninitialized().model_dump()
                                }
                            )
                    if new_len != old_len:
                        self.tracer.emit_event(
                            event_type="OBJECT_MUTATE",
                            payload={
                                "object_id": obj_id,
                                "field": "length",
                                "old_value": PrimitiveValue(type_name="int", value=old_len).model_dump(),
                                "new_value": PrimitiveValue(type_name="int", value=new_len).model_dump()
                            }
                        )
                    self._snapshots[obj_id] = [copy.deepcopy(x) if not isinstance(x, (list, dict, set, tuple)) else x for x in new_elems]

            elif isinstance(live_obj, dict):
                old_snap = self._snapshots[obj_id]
                new_dict = dict(live_obj)
                if new_dict != old_snap:
                    for k, v in new_dict.items():
                        if k not in old_snap:
                            new_u = self.to_universal_value(v)
                            self.tracer.emit_event(
                                event_type="OBJECT_MUTATE",
                                payload={
                                    "object_id": obj_id,
                                    "field": str(k),
                                    "old_value": Uninitialized().model_dump(),
                                    "new_value": new_u.model_dump() if hasattr(new_u, "model_dump") else new_u.dict()
                                }
                            )
                        elif old_snap[k] != v:
                            old_u = self.to_universal_value(old_snap[k])
                            new_u = self.to_universal_value(v)
                            self.tracer.emit_event(
                                event_type="OBJECT_MUTATE",
                                payload={
                                    "object_id": obj_id,
                                    "field": str(k),
                                    "old_value": old_u.model_dump() if hasattr(old_u, "model_dump") else old_u.dict(),
                                    "new_value": new_u.model_dump() if hasattr(new_u, "model_dump") else new_u.dict()
                                }
                            )
                    for k, v in old_snap.items():
                        if k not in new_dict:
                            old_u = self.to_universal_value(v)
                            self.tracer.emit_event(
                                event_type="OBJECT_MUTATE",
                                payload={
                                    "object_id": obj_id,
                                    "field": str(k),
                                    "old_value": old_u.model_dump() if hasattr(old_u, "model_dump") else old_u.dict(),
                                    "new_value": Uninitialized().model_dump()
                                }
                            )
                    if len(new_dict) != len(old_snap):
                        self.tracer.emit_event(
                            event_type="OBJECT_MUTATE",
                            payload={
                                "object_id": obj_id,
                                "field": "size",
                                "old_value": PrimitiveValue(type_name="int", value=len(old_snap)).model_dump(),
                                "new_value": PrimitiveValue(type_name="int", value=len(new_dict)).model_dump()
                            }
                        )
                    self._snapshots[obj_id] = {k: copy.deepcopy(v) if not isinstance(v, (list, dict, set, tuple)) else v for k, v in new_dict.items()}

            elif isinstance(live_obj, set):
                old_snap = self._snapshots[obj_id]
                new_set = set(live_obj)
                if new_set != old_snap:
                    for elem in (new_set - old_snap):
                        new_u = self.to_universal_value(elem)
                        self.tracer.emit_event(
                            event_type="OBJECT_MUTATE",
                            payload={
                                "object_id": obj_id,
                                "field": str(elem),
                                "old_value": Uninitialized().model_dump(),
                                "new_value": new_u.model_dump() if hasattr(new_u, "model_dump") else new_u.dict()
                            }
                        )
                    for elem in (old_snap - new_set):
                        old_u = self.to_universal_value(elem)
                        self.tracer.emit_event(
                            event_type="OBJECT_MUTATE",
                            payload={
                                "object_id": obj_id,
                                "field": str(elem),
                                "old_value": old_u.model_dump() if hasattr(old_u, "model_dump") else old_u.dict(),
                                "new_value": Uninitialized().model_dump()
                            }
                        )
                    if len(new_set) != len(old_snap):
                        self.tracer.emit_event(
                            event_type="OBJECT_MUTATE",
                            payload={
                                "object_id": obj_id,
                                "field": "size",
                                "old_value": PrimitiveValue(type_name="int", value=len(old_snap)).model_dump(),
                                "new_value": PrimitiveValue(type_name="int", value=len(new_set)).model_dump()
                            }
                        )
                    self._snapshots[obj_id] = set(new_set)


class FrameState:
    """Tracks lexical state and visible bindings within a call frame."""
    def __init__(self, frame_id: str, scope_id: str, func_name: str, parent_frame_id: Optional[str] = None):
        self.frame_id = frame_id
        self.scope_id = scope_id
        self.func_name = func_name
        self.parent_frame_id = parent_frame_id
        self.bindings: Dict[str, Tuple[str, UniversalValue]] = {}  # var_name -> (binding_id, UniversalValue)
        self.active_scope_id = scope_id


class _PythonTracer:
    """
    Execution tracing engine using sys.settrace.
    Generates strict AlgoLensEvent sequences according to the Universal Event Protocol.
    """

    def __init__(
        self,
        source_code: str,
        user_filename: str,
        entry_func: str = "main",
        timeout_sec: float = 12.0,
        max_events: int = 50000,
        loop_ranges: Optional[List[Tuple[int, int]]] = None
    ):
        self.source_code = source_code
        self.source_lines = source_code.splitlines()
        self.user_filename = user_filename
        self.entry_func = entry_func
        self.timeout_sec = timeout_sec
        self.max_events = max_events
        self.loop_ranges = loop_ranges or []

        # Deterministic sequence generators (strictly 0-indexed per execution)
        self.seq = 0
        self.frame_seq = 0
        self.scope_seq = 0
        self.binding_seq = 0

        self.events: List[AlgoLensEvent] = []
        self.call_stack: List[str] = []
        self.frame_states: Dict[str, FrameState] = {}
        self.frame_id_by_code: Dict[int, str] = {}  # id(frame) -> frame_id

        self.active_frame_id = "frame_0"
        self.active_scope_id = "scope_0"
        self.current_line = 0
        self.prev_line_executed = 0
        self.start_time = time.perf_counter()

        self.registry = PythonObjectRegistry(self)
        self.active_loop_scopes: List[Dict[str, Any]] = []

    def get_source_line(self, line_num: int) -> Optional[str]:
        if 1 <= line_num <= len(self.source_lines):
            return self.source_lines[line_num - 1].strip()
        return None

    def emit_event(self, event_type: str, payload: Dict[str, Any], line: Optional[int] = None) -> AlgoLensEvent:
        if len(self.events) >= self.max_events - 1:
            trun_ev = AlgoLensEvent(
                seq=self.seq,
                line=line if line is not None else self.current_line,
                event_type="TRACE_TRUNCATED",
                frame_id=self.active_frame_id,
                scope_id=self.active_scope_id,
                prev_line=self.prev_line_executed,
                payload={"reason": "max_events limit reached", "max_limit": self.max_events}
            )
            self.events.append(trun_ev)
            self.seq += 1
            raise TraceLimitReached("max_events limit reached")

        ev = AlgoLensEvent(
            seq=self.seq,
            line=line if line is not None else self.current_line,
            event_type=event_type,
            frame_id=self.active_frame_id,
            scope_id=self.active_scope_id,
            prev_line=self.prev_line_executed,
            payload=payload
        )
        self.events.append(ev)
        self.seq += 1
        return ev

    def _flush_frame_variables(self, frame, event_line: int):
        """Detects newly declared, updated, or deleted variables in the active frame."""
        frame_id = self.frame_id_by_code.get(id(frame))
        if not frame_id or frame_id not in self.frame_states:
            return
        frame_state = self.frame_states[frame_id]

        # Scan local variables
        for name, val in list(frame.f_locals.items()):
            # Filter internal symbols and functions/classes
            if name.startswith("__") or inspect.isfunction(val) or inspect.isclass(val) or inspect.ismodule(val):
                continue

            u_val = self.registry.to_universal_value(val)
            u_dict = u_val.model_dump() if hasattr(u_val, "model_dump") else u_val.dict()

            if name not in frame_state.bindings:
                # VAR_DECLARE
                b_id = f"binding_{self.binding_seq}"
                self.binding_seq += 1
                frame_state.bindings[name] = (b_id, u_val)
                type_name = type(val).__name__
                self.emit_event(
                    event_type="VAR_DECLARE",
                    payload={
                        "binding_id": b_id,
                        "name": name,
                        "type_decl": type_name,
                        "value": u_dict
                    },
                    line=event_line
                )
            else:
                b_id, old_u = frame_state.bindings[name]
                if old_u != u_val:
                    old_dict = old_u.model_dump() if hasattr(old_u, "model_dump") else old_u.dict()
                    frame_state.bindings[name] = (b_id, u_val)
                    self.emit_event(
                        event_type="VAR_WRITE",
                        payload={
                            "binding_id": b_id,
                            "name": name,
                            "old_value": old_dict,
                            "new_value": u_dict
                        },
                        line=event_line
                    )

        # Detect deleted variables
        for name in list(frame_state.bindings.keys()):
            if name not in frame.f_locals:
                b_id, _ = frame_state.bindings.pop(name)
                self.emit_event(
                    event_type="VAR_DELETE",
                    payload={"binding_id": b_id, "name": name},
                    line=event_line
                )

        # Scan heap object mutations
        self.registry.detect_mutations()

    def trace(self, frame, event: str, arg: Any):
        # Enforce timeout
        if (time.perf_counter() - self.start_time) > self.timeout_sec:
            raise TimeoutError(f"Execution timed out after {self.timeout_sec}s")

        # Ignore foreign files (builtins, standard library)
        if frame.f_code.co_filename != self.user_filename:
            return None

        lineno = frame.f_lineno

        if event == "call":
            func_name = frame.f_code.co_name
            if func_name == "<module>":
                # Initial module entry
                self.active_frame_id = "frame_0"
                self.active_scope_id = "scope_0"
                self.call_stack = ["frame_0"]
                frame_state = FrameState("frame_0", "scope_0", "<module>")
                self.frame_states["frame_0"] = frame_state
                self.frame_id_by_code[id(frame)] = "frame_0"
                self.frame_seq = 1
                self.scope_seq = 1

                self.emit_event(
                    event_type="PROG_START",
                    payload={"entry_function": self.entry_func, "args": {}},
                    line=0
                )
            else:
                # Function call
                new_frame_id = f"frame_{self.frame_seq}"
                self.frame_seq += 1
                new_scope_id = f"scope_{self.scope_seq}"
                self.scope_seq += 1

                parent_id = self.call_stack[-1] if self.call_stack else None
                self.call_stack.append(new_frame_id)
                self.active_frame_id = new_frame_id
                self.active_scope_id = new_scope_id

                frame_state = FrameState(new_frame_id, new_scope_id, func_name, parent_id)
                self.frame_states[new_frame_id] = frame_state
                self.frame_id_by_code[id(frame)] = new_frame_id

                # Extract arguments
                args_dict = {}
                param_names = frame.f_code.co_varnames[:frame.f_code.co_argcount]
                for p in param_names:
                    if p in frame.f_locals:
                        pval = frame.f_locals[p]
                        pu = self.registry.to_universal_value(pval)
                        args_dict[p] = pu.model_dump() if hasattr(pu, "model_dump") else pu.dict()

                self.emit_event(
                    event_type="FRAME_PUSH",
                    payload={
                        "frame_id": new_frame_id,
                        "func_name": func_name,
                        "parent_frame_id": parent_id,
                        "args": args_dict
                    },
                    line=lineno
                )

                # Declare function parameters as bindings
                for p in param_names:
                    if p in frame.f_locals:
                        pval = frame.f_locals[p]
                        pu = self.registry.to_universal_value(pval)
                        b_id = f"binding_{self.binding_seq}"
                        self.binding_seq += 1
                        frame_state.bindings[p] = (b_id, pu)
                        self.emit_event(
                            event_type="VAR_DECLARE",
                            payload={
                                "binding_id": b_id,
                                "name": p,
                                "type_decl": type(pval).__name__,
                                "value": pu.model_dump() if hasattr(pu, "model_dump") else pu.dict()
                            },
                            line=lineno
                        )
            return self.trace

        elif event == "line":
            # 1. Flush any mutations that occurred on the preceding line
            if self.prev_line_executed > 0:
                self._flush_frame_variables(frame, event_line=self.prev_line_executed)

            # 2. Scope transitions for loop blocks
            # Check if any active loop scope has been exited
            while self.active_loop_scopes and not (self.active_loop_scopes[-1]["start"] <= lineno <= self.active_loop_scopes[-1]["end"]):
                self.active_loop_scopes.pop()
                self.emit_event(
                    event_type="SCOPE_EXIT",
                    payload={},
                    line=lineno
                )
                self.active_scope_id = self.active_loop_scopes[-1]["scope_id"] if self.active_loop_scopes else self.frame_states[self.active_frame_id].scope_id

            # Check if a new loop scope is entered
            for start, end in self.loop_ranges:
                if lineno == start:
                    if not any(s["start"] == start for s in self.active_loop_scopes):
                        loop_scope_id = f"scope_{self.scope_seq}"
                        self.scope_seq += 1
                        self.active_loop_scopes.append({"start": start, "end": end, "scope_id": loop_scope_id})
                        self.active_scope_id = loop_scope_id
                        self.emit_event(
                            event_type="SCOPE_ENTER",
                            payload={"kind": "loop"},
                            line=lineno
                        )

            # 3. Emit STEP_LINE for current line
            snippet = self.get_source_line(lineno)
            self.emit_event(
                event_type="STEP_LINE",
                payload={"line": lineno, "code_snippet": snippet},
                line=lineno
            )
            self.current_line = lineno
            self.prev_line_executed = lineno
            return self.trace

        elif event == "return":
            # Flush final line changes
            if self.prev_line_executed > 0:
                self._flush_frame_variables(frame, event_line=self.prev_line_executed)

            # Pop any open loop scopes in this frame
            while self.active_loop_scopes:
                self.active_loop_scopes.pop()
                self.emit_event(
                    event_type="SCOPE_EXIT",
                    payload={},
                    line=lineno
                )

            func_name = frame.f_code.co_name
            if func_name == "<module>":
                # Final step line on completion so that post-execution variables are captured
                if self.events and self.events[-1].event_type != "STEP_LINE":
                    self.emit_event("STEP_LINE", payload={"line": lineno, "code_snippet": self.get_source_line(lineno)}, line=lineno)
                ret_u = self.registry.to_universal_value(arg) if arg is not None else None
                ret_payload = {"return_value": ret_u.model_dump() if (ret_u and hasattr(ret_u, "model_dump")) else (ret_u.dict() if ret_u else None)}
                self.emit_event("PROG_END", ret_payload, line=lineno)
            else:
                # Function return
                ret_u = self.registry.to_universal_value(arg) if arg is not None else None
                ret_dict = ret_u.model_dump() if (ret_u and hasattr(ret_u, "model_dump")) else (ret_u.dict() if ret_u else None)
                self.emit_event(
                    event_type="FRAME_POP",
                    payload={"return_value": ret_dict},
                    line=lineno
                )
                if self.call_stack:
                    self.call_stack.pop()
                self.active_frame_id = self.call_stack[-1] if self.call_stack else "frame_0"
                if self.active_frame_id in self.frame_states:
                    self.active_scope_id = self.frame_states[self.active_frame_id].scope_id

            return self.trace

        return self.trace


class PythonRuntimeProducer(LanguageRuntimeProducer):
    """
    Second-language producer for AlgoLens.
    Executes Python source programs and emits the Universal Event Protocol.
    Integrates directly with UniversalStateReducer, EventToStepAdapter, and PlaybackEngine.
    """

    def __init__(self):
        pass

    def _find_loop_ranges(self, tree: ast.AST) -> List[Tuple[int, int]]:
        """Collects (start_line, end_line) of loop blocks (for / while) for scope tracking."""
        loop_ranges = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.For, ast.While)):
                start = node.lineno
                end = getattr(node, "end_lineno", node.lineno)
                loop_ranges.append((start, end))
        return loop_ranges

    def execute_program(
        self,
        source_code: str,
        entry_func: str = "main",
        args: Optional[List[Any]] = None,
        timeout_sec: float = 12.0,
        max_events: int = 50000
    ) -> ExecutionResult:
        """
        Executes Python source code according to the Universal Runtime Contract.
        Produces deterministic AlgoLensEvent stream, separated stdout, and error isolation.
        """
        t_start = time.perf_counter()

        # Step 1: Parse AST & Validate Syntax
        try:
            tree = ast.parse(source_code)
        except SyntaxError as se:
            t_total = (time.perf_counter() - t_start) * 1000.0
            return ExecutionResult(
                success=False,
                events=[],
                user_stdout="",
                runtime_stderr=traceback.format_exc(),
                exit_code=1,
                execution_time_ms=0.0,
                total_time_ms=t_total,
                error_message=f"SyntaxError: {se.msg} on line {se.lineno}"
            )

        loop_ranges = self._find_loop_ranges(tree)

        # Step 2: Compile Bytecode
        user_filename = "<user_program.py>"
        try:
            code_obj = compile(source_code, user_filename, "exec")
        except Exception as ce:
            t_total = (time.perf_counter() - t_start) * 1000.0
            return ExecutionResult(
                success=False,
                events=[],
                user_stdout="",
                runtime_stderr=traceback.format_exc(),
                exit_code=1,
                execution_time_ms=0.0,
                total_time_ms=t_total,
                error_message=f"Compilation error: {ce}"
            )

        # Step 3: Initialize Tracer
        tracer = _PythonTracer(
            source_code=source_code,
            user_filename=user_filename,
            entry_func=entry_func,
            timeout_sec=timeout_sec,
            max_events=max_events,
            loop_ranges=loop_ranges
        )

        stdout_capture = io.StringIO()
        exec_env: Dict[str, Any] = {"__name__": "__main__"}

        t_exec_start = time.perf_counter()
        truncated = False
        timeout_err = None
        runtime_err = None
        stderr_msg = ""
        exit_code = 0

        # Step 4: Traced Execution
        old_trace = sys.gettrace()
        try:
            with contextlib.redirect_stdout(stdout_capture):
                sys.settrace(tracer.trace)
                try:
                    exec(code_obj, exec_env)

                    # If entry_func is a function and not yet invoked, invoke it
                    if entry_func in exec_env and inspect.isfunction(exec_env[entry_func]):
                        # Check if it was explicitly called in script by checking if frames pushed
                        has_function_run = any(
                            ev.event_type == "FRAME_PUSH" and ev.payload.get("func_name") == entry_func
                            for ev in tracer.events
                        )
                        if not has_function_run:
                            func = exec_env[entry_func]
                            arg_list = args or []
                            func_ret = func(*arg_list)
                            # Update PROG_END return value if present
                            if tracer.events and tracer.events[-1].event_type == "PROG_END":
                                u_ret = tracer.registry.to_universal_value(func_ret)
                                ret_dict = u_ret.model_dump() if hasattr(u_ret, "model_dump") else u_ret.dict()
                                tracer.events[-1].payload["return_value"] = ret_dict

                finally:
                    sys.settrace(old_trace)
        except TraceLimitReached:
            truncated = True
        except TimeoutError as te:
            timeout_err = str(te)
            exit_code = -1
        except Exception as e:
            runtime_err = f"{type(e).__name__}: {e}"
            stderr_msg = traceback.format_exc()
            exit_code = 1
        finally:
            sys.settrace(old_trace)

        t_exec_end = time.perf_counter()
        exec_ms = (t_exec_end - t_exec_start) * 1000.0
        total_ms = (t_exec_end - t_start) * 1000.0

        user_stdout = stdout_capture.getvalue()
        is_success = (exit_code == 0) and (timeout_err is None)

        diag = "Trace truncated: max_events reached" if truncated else ""

        return ExecutionResult(
            success=is_success,
            events=tracer.events,
            user_stdout=user_stdout,
            runtime_stderr=stderr_msg,
            exit_code=exit_code,
            execution_time_ms=exec_ms,
            total_time_ms=total_ms,
            error_message=timeout_err or runtime_err,
            diagnostics=diag
        )
