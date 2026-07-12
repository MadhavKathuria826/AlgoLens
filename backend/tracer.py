import sys
import ast
import copy
from typing import List
from models import Step, VisualizationData

def is_dp_name(name: str) -> bool:
    name_lower = name.lower()
    allowed_terms = {'dp', 'memo', 'cache', 'table', 'dp_table', 'memo_table'}
    if name_lower in allowed_terms:
        return True
    for term in allowed_terms:
        if name_lower.startswith(term + '_') or name_lower.endswith('_' + term):
            return True
    return False

def is_dp_shape(node_val) -> bool:
    if node_val is None:
        return False
    if isinstance(node_val, ast.BinOp):
        if isinstance(node_val.op, ast.Mult):
            if isinstance(node_val.left, ast.List) or isinstance(node_val.right, ast.List):
                return True
    if isinstance(node_val, ast.ListComp):
        if node_val.generators and len(node_val.generators) == 1:
            gen = node_val.generators[0]
            if isinstance(gen.iter, ast.Call) and getattr(gen.iter.func, 'id', None) == 'range':
                return True
    if isinstance(node_val, ast.Dict):
        return True
    if isinstance(node_val, ast.Call) and getattr(node_val.func, 'id', None) == 'dict':
        return True
    return False

def dict_to_array(d):
    if not d:
        return []
    keys = list(d.keys())
    if all(isinstance(k, int) and k >= 0 for k in keys):
        max_k = max(keys)
        if max_k > 1000:
            return []
        arr = [None] * (max_k + 1)
        for k, v in d.items():
            arr[k] = v
        return arr
    elif all(isinstance(k, tuple) and len(k) == 2 and isinstance(k[0], int) and k[0] >= 0 and isinstance(k[1], int) and k[1] >= 0 for k in keys):
        max_r = max(k[0] for k in keys)
        max_c = max(k[1] for k in keys)
        if max_r > 100 or max_c > 100:
            return []
        arr = [[None] * (max_c + 1) for _ in range(max_r + 1)]
        for (r, c), v in d.items():
            arr[r][c] = v
        return arr
    return []

def get_slice_node(subscript_node):
    sl = subscript_node.slice
    if isinstance(sl, ast.Index):
        return sl.value
    return sl

def eval_ast_node(node, globals_dict, locals_dict):
    try:
        expr = ast.Expression(body=node)
        code_obj = compile(expr, '<string>', 'eval')
        return eval(code_obj, globals_dict, locals_dict)
    except Exception:
        return None

def resolve_subscript(node, globals_dict, locals_dict):
    if not isinstance(node, ast.Subscript):
        return None
    
    # 1D: base is Name
    if isinstance(node.value, ast.Name):
        idx = eval_ast_node(get_slice_node(node), globals_dict, locals_dict)
        if isinstance(idx, int) and idx >= 0:
            return node.value.id, idx
        return None
        
    # 2D: base is Subscript, and its base is Name
    if isinstance(node.value, ast.Subscript) and isinstance(node.value.value, ast.Name):
        idx2 = eval_ast_node(get_slice_node(node), globals_dict, locals_dict)
        idx1 = eval_ast_node(get_slice_node(node.value), globals_dict, locals_dict)
        if isinstance(idx1, int) and idx1 >= 0 and isinstance(idx2, int) and idx2 >= 0:
            return node.value.value.id, (idx1, idx2)
        return None
        
    return None

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
        self.dp_vars = set()
        self.non_dp_vars = set()

    def find_first_assignment_rhs(self, target_name: str):
        if not hasattr(self, 'ast_nodes_list'):
            return None
        for node in self.ast_nodes_list:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = []
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            targets.append(t.id)
                        elif isinstance(t, (ast.Tuple, ast.List)):
                            for elt in t.elts:
                                if isinstance(elt, ast.Name):
                                    targets.append(elt.id)
                else: # AnnAssign
                    if isinstance(node.target, ast.Name):
                        targets.append(node.target.id)
                
                if target_name in targets:
                    return node.value
        return None

    def parse_ast_mapping(self, code: str):
        tree = ast.parse(code)
        self.ast_nodes_list = list(ast.walk(tree))
        for node in self.ast_nodes_list:
            if isinstance(node, ast.stmt) and hasattr(node, 'lineno'):
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
                
                if len(self.call_stack) >= getattr(self, 'max_depth', 1000):
                    raise ValueError(f"Maximum recursion depth of {self.max_depth} exceeded. Please check your algorithm or increase the limit in Settings.")
                
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
                if (hasattr(val, '__dict__') or hasattr(type(val), '__slots__')) and (
                    getattr(type(val), '__module__', '') == '__main__' or
                    type(val).__name__ in ('TreeNode', 'ListNode', 'LocalTreeNode', 'LocalListNode')
                ):
                    obj_id = f"obj_{id(val)}"
                    if obj_id not in visited_objs:
                        visited_objs.add(obj_id)
                        fields = {}
                        type_name = type(val).__name__
                        if type_name == 'LocalTreeNode':
                            type_name = 'TreeNode'
                        elif type_name == 'LocalListNode':
                            type_name = 'ListNode'
                        current_heap[obj_id] = {'type': type_name, 'fields': fields}
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
                    
                    is_dp = name in self.dp_vars
                    if not is_dp and name not in self.non_dp_vars:
                        if is_dp_name(name):
                            rhs = self.find_first_assignment_rhs(name)
                            if rhs is not None and is_dp_shape(rhs):
                                self.dp_vars.add(name)
                                is_dp = True
                            else:
                                self.non_dp_vars.add(name)
                        else:
                            self.non_dp_vars.add(name)

                    if (isinstance(value, list) or (isinstance(value, dict) and is_dp)) and not self.active_tree:
                        vis_type = 'DP_TABLE' if is_dp else 'Array'
                        val_to_serialize = dict_to_array(value) if isinstance(value, dict) else list(value)
                        
                        details = {
                            'name': name,
                            'value': val_to_serialize,
                            'obj_id': f"{'dict' if isinstance(value, dict) else 'list'}_{id(value)}"
                        }
                        
                        if is_dp:
                            target_res = None
                            sources_res = []
                            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                                targets_lhs = []
                                if isinstance(node, ast.Assign):
                                    targets_lhs = node.targets
                                else:
                                    targets_lhs = [node.target]
                                    
                                for target_node in targets_lhs:
                                    res = resolve_subscript(target_node, frame.f_globals, frame.f_locals)
                                    if res is not None and res[0] == name:
                                        target_res = res[1]
                                        break
                                
                                if target_res is not None:
                                    skipped = set()
                                    for child in ast.walk(node.value):
                                        if child in skipped:
                                            continue
                                        res = resolve_subscript(child, frame.f_globals, frame.f_locals)
                                        if res is not None and res[0] == name:
                                            sources_res.append(res[1])
                                            if isinstance(child, ast.Subscript) and isinstance(child.value, ast.Subscript):
                                                skipped.add(child.value)
                                                
                            if target_res is not None:
                                details['target'] = target_res
                                if sources_res:
                                    details['sources'] = sources_res
                                    
                        visualizations.append(VisualizationData(
                            type=vis_type,
                            details=details
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

    def run_code(self, code: str, max_depth: int = 1000) -> List[Step]:
        self.max_depth = max_depth
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
            "min": min, "sum": sum, "True": True, "False": False, "None": None,
            "object": object, "Exception": Exception, "ValueError": ValueError,
            "TypeError": TypeError, "super": super, "isinstance": isinstance,
            "staticmethod": staticmethod, "classmethod": classmethod,
            "dict": dict, "tuple": tuple, "set": set, "frozenset": frozenset,
            "enumerate": enumerate, "zip": zip, "map": map, "filter": filter,
            "sorted": sorted, "reversed": reversed, "any": any, "all": all,
            "next": next, "iter": iter, "divmod": divmod, "pow": pow,
            "round": round, "chr": chr, "ord": ord, "hasattr": hasattr,
            "KeyError": KeyError, "IndexError": IndexError, "StopIteration": StopIteration,
            "ZeroDivisionError": ZeroDivisionError, "AttributeError": AttributeError,
            "RuntimeError": RuntimeError, "NotImplementedError": NotImplementedError
        }
        class LocalTreeNode:
            def __init__(self, val=0, left=None, right=None):
                self.val = val
                self.left = left
                self.right = right
            def __repr__(self):
                return f"TreeNode({self.val})"

        class LocalListNode:
            def __init__(self, val=0, next=None):
                self.val = val
                self.next = next
            def __repr__(self):
                return f"ListNode({self.val})"

        def deserialize_tree(arr):
            if not arr or not isinstance(arr, list):
                return None
            cls = safe_globals.get('TreeNode', LocalTreeNode)
            root = cls(arr[0])
            queue = [root]
            i = 1
            while queue and i < len(arr):
                curr = queue.pop(0)
                if curr is not None:
                    if i < len(arr):
                        val = arr[i]
                        i += 1
                        if val is not None:
                            curr.left = cls(val)
                            queue.append(curr.left)
                    if i < len(arr):
                        val = arr[i]
                        i += 1
                        if val is not None:
                            curr.right = cls(val)
                            queue.append(curr.right)
            return root

        def deserialize_list(arr):
            if not arr or not isinstance(arr, list):
                return None
            cls = safe_globals.get('ListNode', LocalListNode)
            head = cls(arr[0])
            curr = head
            for val in arr[1:]:
                curr.next = cls(val)
                curr = curr.next
            return head

        safe_globals = {
            "__builtins__": safe_builtins,
            "__name__": "__main__",
            "_deserialize_tree": deserialize_tree,
            "_deserialize_list": deserialize_list
        }

        has_treenode = False
        has_listnode = False
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    if node.name == 'TreeNode':
                        has_treenode = True
                    elif node.name == 'ListNode':
                        has_listnode = True
        except Exception:
            pass

        if not has_treenode:
            safe_globals["TreeNode"] = LocalTreeNode
        if not has_listnode:
            safe_globals["ListNode"] = LocalListNode
        
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
