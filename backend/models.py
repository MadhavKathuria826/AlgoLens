from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class CodeExecutionRequest(BaseModel):
    code: str
    language: Optional[str] = "python"
    max_recursion_depth: Optional[int] = 1000
    test_case: Optional[str] = None
    selected_method: Optional[str] = None

class VisualizationData(BaseModel):
    type: str # 'Array', 'Recursion', 'Loop', 'Condition', 'Function', 'Variable'
    details: Dict[str, Any]

class Step(BaseModel):
    step_number: int
    line_number: int
    visualizations: List[VisualizationData]
    event_type: str # 'call', 'line', 'return'
    locals: Optional[Dict[str, Any]] = None
    heap: Optional[Dict[str, Any]] = None

class CodeExecutionResponse(BaseModel):
    steps: List[Step]
    error: Optional[str] = None
    needs_test_case: bool = False
    needs_disambiguation: bool = False
    candidates: Optional[List[str]] = None
    params: Optional[List[str]] = None
    recurrence_relations: Optional[List[str]] = None
