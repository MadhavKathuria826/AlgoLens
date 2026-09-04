"""
AlgoLens Checkpoint Manager
Provides configurable and adaptive checkpoint policies for efficient playback and random access.
Ensures complete state mutation isolation between stored checkpoints and active runtime execution.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
from event_models import AlgoLensEvent
from state_reducer import UniversalRuntimeState


class CheckpointPolicy(ABC):
    """Abstract interface for deciding when to record a state checkpoint."""

    @abstractmethod
    def should_checkpoint(
        self,
        event: AlgoLensEvent,
        state: UniversalRuntimeState,
        events_since_last: int
    ) -> bool:
        pass


class FixedIntervalPolicy(CheckpointPolicy):
    """Records a checkpoint every N events."""

    def __init__(self, interval: int = 50):
        self.interval = max(1, interval)

    def should_checkpoint(
        self,
        event: AlgoLensEvent,
        state: UniversalRuntimeState,
        events_since_last: int
    ) -> bool:
        return events_since_last >= self.interval


class AdaptivePolicy(CheckpointPolicy):
    """
    Adaptive checkpointing policy balancing memory footprint against seek/replay latency.
    - More frequent checkpoints when state is lightweight.
    - Sparser checkpoints when state memory pressure is high.
    """

    def __init__(
        self,
        min_interval: int = 20,
        max_interval: int = 100,
        state_size_threshold: int = 50,
        max_checkpoints: int = 100
    ):
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.state_size_threshold = state_size_threshold
        self.max_checkpoints = max_checkpoints

    def estimate_state_complexity(self, state: UniversalRuntimeState) -> int:
        container_elements = sum(
            len(c["elements"]) if isinstance(c.get("elements"), (list, dict)) else 0
            for c in state.containers.values()
        )
        return len(state.bindings) + len(state.heap) + container_elements

    def should_checkpoint(
        self,
        event: AlgoLensEvent,
        state: UniversalRuntimeState,
        events_since_last: int
    ) -> bool:
        # Never checkpoint before minimum interval
        if events_since_last < self.min_interval:
            return False

        # Always checkpoint when hard ceiling reached
        if events_since_last >= self.max_interval:
            return True

        # Check state complexity
        complexity = self.estimate_state_complexity(state)

        # Lightweight state: record earlier to reduce seek replay time
        if complexity < self.state_size_threshold and events_since_last >= (self.min_interval + self.max_interval) // 3:
            return True

        return False


class CheckpointManager:
    """
    Manages checkpoints during execution or playback.
    Guarantees state isolation via deep cloning.
    """

    def __init__(self, policy: Optional[CheckpointPolicy] = None):
        self.policy = policy or FixedIntervalPolicy(interval=50)
        self.checkpoints: Dict[int, UniversalRuntimeState] = {}
        self.events_since_last = 0

    def clone_state(self, state: UniversalRuntimeState) -> UniversalRuntimeState:
        """Deep clones a UniversalRuntimeState to guarantee mutation isolation."""
        return state.model_copy(deep=True)

    def record_checkpoint(self, event_seq: int, state: UniversalRuntimeState):
        """Saves an isolated clone of the state at event_seq."""
        self.checkpoints[event_seq] = self.clone_state(state)
        self.events_since_last = 0

    def maybe_checkpoint(self, event: AlgoLensEvent, state: UniversalRuntimeState, event_index: Optional[int] = None) -> bool:
        """Evaluates policy and saves checkpoint if recommended."""
        self.events_since_last += 1
        seq_key = event_index if event_index is not None else event.seq
        if self.policy.should_checkpoint(event, state, self.events_since_last):
            self.record_checkpoint(seq_key, state)
            return True
        return False

    def get_nearest_checkpoint(self, target_seq: int) -> Tuple[int, Optional[UniversalRuntimeState]]:
        """
        Finds the closest checkpoint sequence index k <= target_seq.
        Returns (checkpoint_seq, cloned_state). If no checkpoint <= target_seq, returns (0, None).
        """
        candidate_keys = [k for k in self.checkpoints.keys() if k <= target_seq]
        if not candidate_keys:
            return (0, None)
        nearest_seq = max(candidate_keys)
        return (nearest_seq, self.clone_state(self.checkpoints[nearest_seq]))
