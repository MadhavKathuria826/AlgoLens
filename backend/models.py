from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class CodeExecutionRequest(BaseModel):
    code: str

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
