"""
AlgoLens Universal Language Runtime Contract (v1.0)
Defines the universal execution interface and result envelope for all language producers.
Ensures strict decoupling between language-specific producers and the Universal Event Protocol.
"""

import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from event_models import AlgoLensEvent


class ExecutionResult(BaseModel):
    """
    Universal language-independent execution result envelope.
    All language producers (C++, Python, etc.) return an instance of ExecutionResult
    (or a language-specific subclass extending it with compiler/runtime telemetry).
    """
    success: bool
    events: List[AlgoLensEvent] = Field(default_factory=list)
    user_stdout: str = ""
    runtime_stderr: str = ""
    exit_code: int = 0
    execution_time_ms: float = 0.0
    total_time_ms: float = 0.0
    error_message: Optional[str] = None
    diagnostics: str = ""


class LanguageRuntimeProducer(ABC):
    """
    Abstract interface for language-specific runtime producers.
    Every language producer must:
      - Produce valid AlgoLensEvent objects conforming to the Universal Event Protocol
      - Maintain deterministic event ordering
      - Mint fresh runtime identity (sequence numbers, frame IDs, object IDs) for every execution
      - Enforce bounded event production (max_events)
      - Enforce execution timeouts without hanging
      - Strictly separate user program stdout from AlgoLens events
      - Report runtime and syntax errors without corrupting the event protocol
      - Leak zero language-specific state into the UniversalStateReducer
    """

    @abstractmethod
    def execute_program(
        self,
        source_code: str,
        entry_func: str = "main",
        args: Optional[List[Any]] = None,
        timeout_sec: float = 12.0,
        max_events: int = 50000
    ) -> ExecutionResult:
        pass
