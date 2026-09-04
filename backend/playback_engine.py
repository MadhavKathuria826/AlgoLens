"""
AlgoLens Playback State Engine
Provides bidirectional playback (step_forward, step_reverse) and bounded-replay random access (seek)
powered by reversible event deltas and the CheckpointManager.
"""

from typing import List, Optional, Dict, Any, Tuple
from event_models import AlgoLensEvent
from state_reducer import UniversalRuntimeState, UniversalStateReducer
from checkpoint_manager import CheckpointManager, CheckpointPolicy, AdaptivePolicy
from event_to_step_adapter import EventToStepAdapter
from models import Step


class PlaybackEngine:
    """
    Stateful execution playback engine.
    - O(1) Forward Stepping: reduce(state, event)
    - O(1) Reverse Stepping: reduce_inverse(state, event)
    - Fast Random Seeking: nearest checkpoint restoration + bounded forward replay
    """

    def __init__(
        self,
        events: List[AlgoLensEvent],
        checkpoint_policy: Optional[CheckpointPolicy] = None,
        container_types: Optional[Dict[str, str]] = None
    ):
        self.events = events
        self.container_types = container_types or {}
        self.checkpoint_manager = CheckpointManager(policy=checkpoint_policy or AdaptivePolicy())
        self.current_state = UniversalRuntimeState()
        self.current_event_index = 0
        self.step_adapter = EventToStepAdapter()

        # Record initial baseline checkpoint at sequence 0
        self.checkpoint_manager.record_checkpoint(0, self.current_state)

    def build_checkpoints(self):
        """Pre-processes the event stream to establish all checkpoints."""
        temp_state = UniversalRuntimeState()
        self.checkpoint_manager.record_checkpoint(0, temp_state)

        for idx, event in enumerate(self.events):
            temp_state = UniversalStateReducer.reduce(temp_state, event)
            self.checkpoint_manager.maybe_checkpoint(event, temp_state, event_index=idx + 1)

    def step_forward(self) -> Optional[UniversalRuntimeState]:
        """Applies the next event in the stream."""
        if self.current_event_index >= len(self.events):
            return None

        event = self.events[self.current_event_index]
        self.current_state = UniversalStateReducer.reduce(self.current_state, event)
        self.current_event_index += 1
        self.checkpoint_manager.maybe_checkpoint(event, self.current_state, event_index=self.current_event_index)
        return self.current_state

    def step_reverse(self) -> Optional[UniversalRuntimeState]:
        """Reverses the most recently applied event in O(1) time."""
        if self.current_event_index <= 0:
            return None

        self.current_event_index -= 1
        event = self.events[self.current_event_index]
        self.current_state = UniversalStateReducer.reduce_inverse(self.current_state, event)
        return self.current_state

    def step_forward_line(self) -> Optional[UniversalRuntimeState]:
        """Steps forward until the next STEP_LINE event is encountered."""
        state = None
        while self.current_event_index < len(self.events):
            is_step_line = self.events[self.current_event_index].event_type == "STEP_LINE"
            state = self.step_forward()
            if is_step_line:
                break
        return state

    def step_reverse_line(self) -> Optional[UniversalRuntimeState]:
        """Steps backward until the previous STEP_LINE event is restored."""
        state = None
        while self.current_event_index > 0:
            state = self.step_reverse()
            if self.current_event_index > 0 and self.events[self.current_event_index - 1].event_type == "STEP_LINE":
                break
        return state

    def seek(self, target_event_index: int) -> UniversalRuntimeState:
        """
        Seeks to target_event_index with bounded replay overhead using nearest checkpoints and O(1) inverse deltas.
        """
        target = max(0, min(target_event_index, len(self.events)))

        if target == self.current_event_index:
            return self.current_state

        # Optimization 1: Small backward jump (<= 5 events) -> Apply O(1) reverse deltas directly
        if 0 < (self.current_event_index - target) <= 5:
            while self.current_event_index > target:
                self.step_reverse()
            return self.current_state

        # Optimization 2: Small forward jump (<= 15 events) -> Apply forward deltas directly
        if 0 < (target - self.current_event_index) <= 15:
            while self.current_event_index < target:
                self.step_forward()
            return self.current_state

        # General case: Restore nearest checkpoint <= target
        ckpt_idx, ckpt_state = self.checkpoint_manager.get_nearest_checkpoint(target)
        if ckpt_state is not None:
            self.current_state = ckpt_state
            self.current_event_index = ckpt_idx
        else:
            self.current_state = UniversalRuntimeState()
            self.current_event_index = 0

        # Replay forward from checkpoint to target index
        while self.current_event_index < target:
            self.step_forward()

        return self.current_state

    def get_current_step(self, event_type: str = "line") -> Step:
        """Translates current state into a legacy Step model."""
        self.step_adapter.state = self.current_state
        return self.step_adapter.state_to_step(event_type=event_type, container_types=self.container_types)
