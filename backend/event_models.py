"""
AlgoLens Event Protocol Models (v2.1)
Defines universal identities, typed values, and event envelope schemas.
"""

from typing import Dict, Any, List, Optional, Union, Literal
from pydantic import BaseModel, Field


# --- Universal Identity Helpers ---

def make_object_id(seq: int) -> str:
    return f"obj_{seq}"

def make_frame_id(seq: int) -> str:
    return f"frame_{seq}"

def make_scope_id(seq: int) -> str:
    return f"scope_{seq}"

def make_binding_id(seq: int) -> str:
    return f"binding_{seq}"


# --- Universal Value Models ---

class PrimitiveValue(BaseModel):
    kind: Literal["primitive"] = "primitive"
    type_name: str  # "int", "float", "bool", "string"
    value: Union[int, float, bool, str]

class ObjectRef(BaseModel):
    kind: Literal["object_ref"] = "object_ref"
    object_id: str  # e.g., "obj_17"

class NullRef(BaseModel):
    kind: Literal["null_ref"] = "null_ref"

class DanglingRef(BaseModel):
    kind: Literal["dangling_ref"] = "dangling_ref"
    last_known_object_id: str

class Uninitialized(BaseModel):
    kind: Literal["uninitialized"] = "uninitialized"

class ReferenceRef(BaseModel):
    kind: Literal["reference"] = "reference"
    target_binding_id: Optional[str] = None
    target_name: Optional[str] = None
    target_object_id: Optional[str] = None
    target_field: Optional[str] = None

UniversalValue = Union[PrimitiveValue, ObjectRef, NullRef, DanglingRef, Uninitialized, ReferenceRef]


# --- Helper Value Factories ---

def value_from_python(val: Any, type_str: str = "") -> UniversalValue:
    """Converts a Python runtime value/pointer address into a UniversalValue."""
    if val is None:
        return NullRef()
    if isinstance(val, dict):
        k = val.get("kind")
        if k == "reference":
            return ReferenceRef(**val)
        elif k == "object_ref":
            return ObjectRef(**val)
        elif k == "null_ref":
            return NullRef()
        elif k == "dangling_ref":
            return DanglingRef(**val)
        elif k == "primitive":
            return PrimitiveValue(**val)
        elif k == "uninitialized":
            return Uninitialized()
    if isinstance(val, bool):
        return PrimitiveValue(type_name="bool", value=val)
    if isinstance(val, int):
        return PrimitiveValue(type_name="int", value=val)
    if isinstance(val, float):
        return PrimitiveValue(type_name="float", value=val)
    if isinstance(val, str):
        if val in ("0x0000", "nullptr", "NULL"):
            return NullRef()
        if val.startswith("obj_"):
            return ObjectRef(object_id=val)
        if val.startswith("0x"):
            # Raw addresses are NOT universal object IDs; treat as debug address primitive
            return PrimitiveValue(type_name="address", value=val)
        return PrimitiveValue(type_name="string", value=val)
    return PrimitiveValue(type_name=type_str or "unknown", value=str(val))


# --- Event Payload Schemas ---

class ProgramStartPayload(BaseModel):
    entry_function: str
    args: Dict[str, UniversalValue] = Field(default_factory=dict)

class ProgramEndPayload(BaseModel):
    return_value: Optional[UniversalValue] = None

class StepLinePayload(BaseModel):
    line: int
    code_snippet: Optional[str] = None

class FramePushPayload(BaseModel):
    func_name: str
    parent_frame_id: Optional[str] = None
    args: Dict[str, UniversalValue] = Field(default_factory=dict)

class FramePopPayload(BaseModel):
    return_value: Optional[UniversalValue] = None

class ScopeEnterPayload(BaseModel):
    kind: str = "block"  # "block", "loop", "branch"

class ScopeExitPayload(BaseModel):
    pass

class VarDeclarePayload(BaseModel):
    binding_id: str
    name: str
    type_decl: str
    value: UniversalValue

class VarWritePayload(BaseModel):
    binding_id: str
    name: str
    old_value: UniversalValue
    new_value: UniversalValue

class VarDeletePayload(BaseModel):
    binding_id: str
    name: str

class ObjectAllocatePayload(BaseModel):
    object_id: str
    type_name: str
    fields: Dict[str, UniversalValue] = Field(default_factory=dict)
    debug_meta: Optional[Dict[str, Any]] = None

class ObjectMutatePayload(BaseModel):
    object_id: str
    field: str
    old_value: UniversalValue
    new_value: UniversalValue

class ObjectDeallocatePayload(BaseModel):
    object_id: str
    type_name: Optional[str] = None
    old_fields: Optional[Dict[str, UniversalValue]] = None
    debug_meta: Optional[Dict[str, Any]] = None

class ObjectFreePayload(BaseModel):
    object_id: str

class ContainerOpPayload(BaseModel):
    container_id: str  # binding_id or object_id
    kind: str  # "ARRAY", "STACK", "QUEUE", "DEQUE", "HEAP", "MAP", "SET", "TRIE"
    op: str    # "PUSH", "POP", "SET_INDEX", "SWAP", "INSERT", "ERASE", "CLEAR"
    indices: Optional[List[int]] = None
    values: Optional[List[UniversalValue]] = None
    old_values: Optional[List[UniversalValue]] = None
    meta: Optional[Dict[str, Any]] = None
    old_meta: Optional[Dict[str, Any]] = None

class TraceTruncatedPayload(BaseModel):
    reason: str
    max_limit: int


# --- Event Envelope ---

class AlgoLensEvent(BaseModel):
    seq: int
    line: int
    event_type: str
    frame_id: str
    scope_id: str
    payload: Dict[str, Any]
    debug_meta: Optional[Dict[str, Any]] = None
    ts: Optional[float] = None
    prev_line: Optional[int] = None
