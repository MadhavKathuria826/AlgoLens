import sys
import ast
import copy
from typing import List
from models import Step, VisualizationData

class Tracer:
    def __init__(self):
        self.steps: List[Step] = []
        self.step_counter = 0
        self.original_frame_count = 0
        self.dropped_frames = 0
        self.ast_map = {}
        self.call_stack = []
        self.recursive_funcs = set()
        
        self.call_id_counter = 0
        self.tree_nodes = [] # Tracks all nodes in the current execution tree
        self.active_tree = False

    def parse_ast_mapping(self, code: str):
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if hasattr(node, 'lineno'):
                self.ast_map[node.lineno] = node
            if isinstance(node, ast.FunctionDef):
                for child in ast.walk(node):
                    if isinstance(child, ast.Call) and getattr(child.func, 'id', None) == node.name:
                        self.recursive_funcs.add(node.name)

    def trace_calls(self, frame, event, arg):
        if event in ('call', 'line', 'return'):
            filename = frame.f_code.co_filename
            if filename != "<string>":
                return self.trace_calls
            
            func_name = frame.f_code.co_name
            lineno = frame.f_lineno

            # Phase 1: Constructor and Class Blackboxing
            if event == 'call':
                if func_name.startswith('__') and func_name.endswith('__'):
                    return None
                node = self.ast_map.get(lineno)
                if isinstance(node, ast.ClassDef):
                    return None

            # Update call stack
            if event == 'call':
                args = {}
                import inspect
                for k, v in frame.f_locals.items():
                    if not k.startswith('__') and not (inspect.isclass(v) or inspect.ismodule(v) or inspect.isroutine(v)):
                        try:
                            args[k] = str(v)
                        except:
                            pass
                
                call_id = str(self.call_id_counter)
                self.call_id_counter += 1
                parent_id = self.call_stack[-1]['id'] if self.call_stack else None
                
                self.call_stack.append({
                    'func': func_name, 
                    'args': args, 
                    'return_val': None,
                    'id': call_id
                })

                if func_name in self.recursive_funcs or self.active_tree:
                    self.active_tree = True
                    self.tree_nodes.append({
                        'id': call_id,
                        'parent_id': parent_id,
                        'func': func_name,
                        'args': args,
                        'return_val': None,
                        'is_active': True,
                        'is_returning': False
                    })

            elif event == 'return' and len(self.call_stack) > 0:
                current_id = self.call_stack[-1]['id']
                self.call_stack[-1]['return_val'] = str(arg)
                
                if self.active_tree:
                    for node in self.tree_nodes:
                        if node['id'] == current_id:
                            node['return_val'] = str(arg)
                            node['is_active'] = False
                            node['is_returning'] = True
                            break

            self.original_frame_count += 1
            node = self.ast_map.get(lineno)
            
            visualizations = []

            # 1. Determine Recursion or Normal Function
            if self.active_tree:
                rec_func = self.tree_nodes[0]['func'] if self.tree_nodes else func_name
                # Deep copy to freeze the state for this step
                visualizations.append(VisualizationData(
                    type='RecursionTree',
                    details={'func': rec_func, 'nodes': copy.deepcopy(self.tree_nodes)}
                ))

            # 2. Arrays & Fallbacks
            current_locals = {}
            current_heap = {}
            visited_objs = set()
            
            def serialize(val):
                if val is None: return "None"
                if isinstance(val, (int, float, bool, str)): return str(val) if isinstance(val, bool) else val
                if (hasattr(val, '__dict__') or hasattr(type(val), '__slots__')) and getattr(type(val), '__module__', '') == '__main__':
                    obj_id = f"obj_{id(val)}"
                    if obj_id not in visited_objs:
                        visited_objs.add(obj_id)
                        fields = {}
                        current_heap[obj_id] = {'type': type(val).__name__, 'fields': fields}
                        import inspect
                        attrs = {}
                        if hasattr(val, '__dict__'):
                            attrs.update(val.__dict__)
                        if hasattr(type(val), '__slots__'):
                            slots = type(val).__slots__
                            if isinstance(slots, str): slots = [slots]
                            for slot in slots:
                                if hasattr(val, slot):
                                    attrs[slot] = getattr(val, slot)
                        for k, v in attrs.items():
                            if not k.startswith('__') and not (inspect.isclass(v) or inspect.ismodule(v) or inspect.isroutine(v)):
                                fields[k] = serialize(v)
                    return obj_id
                return str(val)

            import inspect
            for name, value in frame.f_locals.items():
                if not name.startswith('__') and name not in ('self', 'cls'):
                    if inspect.isclass(value) or inspect.ismodule(value) or inspect.isroutine(value):
                        continue
                    if isinstance(value, list) and not self.active_tree:
                        visualizations.append(VisualizationData(
                            type='Array',
                            details={'name': name, 'value': list(value), 'obj_id': f"list_{id(value)}"}
                        ))
                    else:
                        current_locals[name] = serialize(value)

            # Traverse all parent frames to capture the global heap topology.
            # This ensures that structural roots (e.g. tree roots) are preserved
            # in the heap even when the current recursive frame only references a subtree.
            f = frame.f_back
            while f:
                for name, value in f.f_locals.items():
                    if not name.startswith('__'):
                        if not (inspect.isclass(value) or inspect.ismodule(value) or inspect.isroutine(value)):
                            serialize(value)
                f = f.f_back

            if not self.active_tree:
                # 3. Line-specific actions
                if event == 'line' and node:
                    if isinstance(node, ast.If):
                        visualizations.append(VisualizationData(
                            type='Condition',
                            details={'line': lineno}
                        ))
                    elif isinstance(node, (ast.For, ast.While)):
                        visualizations.append(VisualizationData(
                            type='Loop',
                            details={'line': lineno, 'locals': current_locals}
                        ))
                
                # 4. Fallback Variables
                if not visualizations and current_locals:
                    visualizations.append(VisualizationData(
                        type='Variable',
                        details=current_locals
                    ))

            # Phase 2: Function Frame Cleanup & Aggressive Deduplication
            should_append = self.active_tree or event not in ('call', 'return') or (event == 'return' and frame.f_code.co_name == '<module>')
            
            is_tree = any(isinstance(obj, dict) and 'fields' in obj and ('left' in obj['fields'] or 'right' in obj['fields']) for obj in current_heap.values())
            is_ll = any(isinstance(obj, dict) and 'fields' in obj and 'next' in obj['fields'] for obj in current_heap.values())
            has_primary_struct = is_tree or is_ll
            
            if should_append and self.steps:
                prev_step = self.steps[-1]
                
                is_identical = (prev_step.locals == current_locals and 
                                prev_step.heap == current_heap and 
                                prev_step.visualizations == visualizations)

                if is_identical:
                    should_append = False
                    self.dropped_frames += 1
                elif has_primary_struct:
                    def get_struct_state(locals_dict, heap_dict):
                        pointers = {k: v for k, v in locals_dict.items() if isinstance(v, str) and v.startswith('obj_')}
                        struct_heap = {k: v['fields'] for k, v in heap_dict.items() if isinstance(v, dict) and 'fields' in v}
                        return pointers, struct_heap

                    prev_pointers, prev_struct = get_struct_state(prev_step.locals, prev_step.heap)
                    curr_pointers, curr_struct = get_struct_state(current_locals, current_heap)
                    
                    if prev_pointers == curr_pointers and prev_struct == curr_struct:
                        should_append = False
                        self.dropped_frames += 1

            if should_append:
                self.step_counter += 1
                step = Step(
                    step_number=self.step_counter,
                    line_number=lineno,
                    visualizations=visualizations,
                    event_type=event,
                    locals=current_locals,
                    heap=current_heap
                )
                self.steps.append(step)

            if event == 'return' and len(self.call_stack) > 0:
                popped = self.call_stack.pop()
                if self.active_tree:
                    # turn off is_returning flag immediately after the return step is processed
                    for node in self.tree_nodes:
                        if node['id'] == popped['id']:
                            node['is_returning'] = False
                if len(self.call_stack) == 0:
                    self.active_tree = False
                    self.tree_nodes = []
            
        return self.trace_calls

    def run_code(self, code: str) -> List[Step]:
        self.steps = []
        self.step_counter = 0
        self.original_frame_count = 0
        self.dropped_frames = 0
        self.ast_map = {}
        self.call_stack = []
        self.recursive_funcs = set()
        self.call_id_counter = 0
        self.tree_nodes = []
        self.active_tree = False
        
        try:
            self.parse_ast_mapping(code)
        except Exception:
            pass
            
        heapq_polyfill_code = """
class _heapq_poly:
    @staticmethod
    def _siftdown(heap, startpos, pos):
        # Bubble UP (CPython names this _siftdown)
        while pos > startpos:
            parentpos = (pos - 1) >> 1
            if heap[pos] < heap[parentpos]:
                heap[pos], heap[parentpos] = heap[parentpos], heap[pos]
                pos = parentpos
            else:
                break

    @staticmethod
    def _siftup(heap, pos):
        # Bubble DOWN (CPython names this _siftup)
        endpos = len(heap)
        while True:
            childpos = 2 * pos + 1
            if childpos >= endpos:
                break
            rightpos = childpos + 1
            if rightpos < endpos and not heap[childpos] < heap[rightpos]:
                childpos = rightpos
            
            if heap[childpos] < heap[pos]:
                heap[pos], heap[childpos] = heap[childpos], heap[pos]
                pos = childpos
            else:
                break

    @staticmethod
    def heappush(heap, item):
        heap.append(item)
        _heapq_poly._siftdown(heap, 0, len(heap)-1)

    @staticmethod
    def heappop(heap):
        lastelt = heap.pop()
        if heap:
            returnitem = heap[0]
            heap[0] = lastelt
            _heapq_poly._siftup(heap, 0)
            return returnitem
        return lastelt

    @staticmethod
    def heapify(x):
        n = len(x)
        for i in reversed(range(n//2)):
            _heapq_poly._siftup(x, i)
"""
        
        heapq_globals = {}
        exec(heapq_polyfill_code, heapq_globals, heapq_globals)
        
        def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "heapq":
                return heapq_globals["_heapq_poly"]
            return __builtins__["__import__"](name, globals, locals, fromlist, level)

        safe_builtins = {
            "__build_class__": __builtins__["__build_class__"],
            "__import__": safe_import,
            "print": print, "range": range, "len": len, "int": int, "str": str,
            "float": float, "bool": bool, "list": list, "abs": abs, "max": max,
            "min": min, "sum": sum, "True": True, "False": False, "None": None
        }
        safe_globals = {"__builtins__": safe_builtins, "__name__": "__main__"}
        
        old_trace = sys.gettrace()
        sys.settrace(self.trace_calls)
        try:
            exec(code, safe_globals, safe_globals)
        except Exception as e:
            self.step_counter += 1
            self.steps.append(Step(
                step_number=self.step_counter,
                line_number=0,
                visualizations=[VisualizationData(type='Error', details={'msg': str(e)})],
                event_type='error'
            ))
        finally:
            sys.settrace(old_trace)
            print(f"TRACER METRICS - Original: {self.original_frame_count}, Compressed: {len(self.steps)}, Dropped: {self.dropped_frames}")
            
        return self.steps
