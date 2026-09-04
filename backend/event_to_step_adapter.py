"""
AlgoLens EventToStepAdapter
Translates reconstructed UniversalRuntimeState into legacy Step models expected by the frontend.
"""

import copy
import json
from typing import Dict, Any, List, Optional
from models import Step, VisualizationData
from event_models import AlgoLensEvent, UniversalValue, PrimitiveValue, ObjectRef, NullRef, Uninitialized
from state_reducer import UniversalRuntimeState, UniversalStateReducer


class EventToStepAdapter:
    """
    Consumes a stream of AlgoLensEvent objects, reduces them through UniversalStateReducer,
    and emits a list of legacy Step objects compatible with the existing frontend.
    """

    def __init__(self):
        self.state = UniversalRuntimeState()
        self.steps: List[Step] = []
        self.step_counter = 0

    def serialize_value(self, val: Any) -> Any:
        if isinstance(val, PrimitiveValue):
            return val.value
        elif isinstance(val, ObjectRef):
            return val.object_id
        elif isinstance(val, NullRef):
            return "0x0000"
        elif isinstance(val, Uninitialized):
            return None
        elif isinstance(val, dict):
            return {k: self.serialize_value(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [self.serialize_value(v) for v in val]
        return val

    def state_to_step(self, event_type: str = "line", container_types: Dict[str, str] = None) -> Step:
        if container_types is None:
            container_types = {}

        # 1. Reconstruct Locals
        locals_snapshot: Dict[str, Any] = {}
        visible_bindings = self.state.get_visible_bindings()

        for name, binding in visible_bindings.items():
            # Check if this variable is represented in state.containers
            if name in self.state.containers:
                c_data = self.state.containers[name]
                locals_snapshot[name] = copy.deepcopy(c_data["elements"])
            else:
                locals_snapshot[name] = self.serialize_value(binding.value)

        # Also populate any containers not directly in bindings
        for c_id, c_data in self.state.containers.items():
            if c_id not in locals_snapshot:
                locals_snapshot[c_id] = copy.deepcopy(c_data["elements"])

        # 2. Reconstruct Heap
        heap_snapshot: Dict[str, Any] = {}
        is_tree = False
        is_linked_list = False

        for obj_id, heap_obj in self.state.heap.items():
            fields_dict = {}
            for f_name, f_val in heap_obj.fields.items():
                fields_dict[f_name] = self.serialize_value(f_val)
                if f_name in ("left", "right"):
                    is_tree = True
                if f_name == "next":
                    is_linked_list = True

            heap_snapshot[obj_id] = {
                "type": heap_obj.type_name,
                "fields": fields_dict
            }

        # 3. Format Visualizations
        visualizations: List[VisualizationData] = []
        for k, v in locals_snapshot.items():
            c_type = container_types.get(k)
            if isinstance(v, list):
                if c_type == 'stack':
                    visualizations.append(VisualizationData(
                        type='Stack',
                        details={'name': k, 'value': list(v), 'obj_id': f"cpp_stack_{k}"}
                    ))
                elif c_type in ('priority_queue', 'priority_queue_min'):
                    formatted_heap = []
                    for item in v:
                        if isinstance(item, dict) and "first" in item and "second" in item:
                            formatted_heap.append(f"({item['first']}, {item['second']})")
                        else:
                            formatted_heap.append(item)
                    visualizations.append(VisualizationData(
                        type='Heap',
                        details={'name': k, 'value': formatted_heap, 'obj_id': f"cpp_heap_{k}"}
                    ))
                else:
                    visualizations.append(VisualizationData(
                        type='Array',
                        details={'name': k, 'value': list(v), 'obj_id': f"cpp_list_{k}"}
                    ))
            elif isinstance(v, dict):
                dict_str = "{" + ", ".join(f"{json.dumps(str(dk))}: {json.dumps(dv)}" for dk, dv in v.items()) + "}"
                visualizations.append(VisualizationData(
                    type='Variable',
                    details={k: dict_str}
                ))

        scalar_locals = {k: v for k, v in locals_snapshot.items() if not isinstance(v, (list, dict))}
        if scalar_locals:
            visualizations.append(VisualizationData(
                type='Variable',
                details=scalar_locals
            ))

        step = Step(
            step_number=self.step_counter,
            line_number=self.state.current_line,
            event_type=event_type,
            locals=locals_snapshot,
            heap=heap_snapshot,
            visualizations=visualizations,
            isTreeAlgorithm=is_tree,
            isLinkedListAlgorithm=is_linked_list
        )
        self.step_counter += 1
        return step

    def process_event_stream(
        self,
        events: List[AlgoLensEvent],
        container_types: Dict[str, str] = None
    ) -> List[Step]:
        """
        Reduces a full event stream and produces the corresponding legacy Step list.
        Emits a Step for each STEP_LINE event.
        """
        self.state = UniversalRuntimeState()
        self.steps = []
        self.step_counter = 0

        for event in events:
            self.state = UniversalStateReducer.reduce(self.state, event)

            if event.event_type == "STEP_LINE":
                step = self.state_to_step(event_type="line", container_types=container_types)
                self.steps.append(step)

        return self.steps
