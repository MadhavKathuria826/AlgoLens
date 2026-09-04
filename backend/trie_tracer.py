import copy
import ast
from typing import List
from models import Step, VisualizationData
from tracer import Tracer

def parse_dict_field(val):
    if isinstance(val, dict):
        return val
    if isinstance(val, str) and val.startswith('{') and val.endswith('}'):
        try:
            parsed = ast.literal_eval(val)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}

def run_trie_tracer(code: str) -> List[Step]:
    """
    Tracer engine for Trie (Prefix Tree) execution.
    Inspects runtime heaps, reconstructs prefix tree hierarchies,
    and enriches steps with active node highlighting and word termination states.
    """
    standard_tracer = Tracer()
    steps = standard_tracer.run_code(code)

    if steps and any(v.type == 'Error' for s in steps for v in s.visualizations):
        return steps

    def extract_trie_nodes(heap):
        nodes = {}
        trie_roots = []

        for obj_id, obj in heap.items():
            if not isinstance(obj, dict):
                continue
            
            obj_type = obj.get('type', '')
            fields = obj.get('fields', {})

            if any(k in fields for k in ('children', 'child', 'nodes', 'is_end_of_word', 'is_word', 'isEnd', 'end')) or 'Trie' in obj_type:
                nodes[obj_id] = {
                    "id": obj_id,
                    "type": obj_type,
                    "fields": fields
                }
                if obj_type in ('Trie', 'PrefixTree') and 'root' in fields:
                    root_val = fields['root']
                    if isinstance(root_val, str) and root_val.startswith('obj_'):
                        trie_roots.append(root_val)

        if not trie_roots:
            referenced_children = set()
            for obj_id, node_info in nodes.items():
                children_raw = node_info['fields'].get('children') or node_info['fields'].get('child')
                children_dict = parse_dict_field(children_raw)
                for char, child_id in children_dict.items():
                    if isinstance(child_id, str) and child_id.startswith('obj_'):
                        referenced_children.add(child_id)
            
            for obj_id in nodes:
                if obj_id not in referenced_children and nodes[obj_id]['type'] != 'Trie':
                    trie_roots.append(obj_id)

        return trie_roots, nodes

    for step in steps:
        trie_roots, nodes = extract_trie_nodes(step.heap)

        # Identify active pointer variable
        active_node_id = None
        for var_name in ('curr', 'node', 'p', 'root', 'curr_node'):
            val = step.locals.get(var_name)
            if isinstance(val, str) and val.startswith('obj_') and val in nodes:
                active_node_id = val
                break

        # Reconstruct tree representation
        def build_trie_tree(node_id, char_val="ROOT", visited=None):
            if visited is None:
                visited = set()
            if not node_id or node_id not in nodes or node_id in visited:
                return None
            visited.add(node_id)

            node_fields = nodes[node_id]['fields']
            is_end_val = node_fields.get('is_end_of_word') or node_fields.get('is_word') or node_fields.get('isEnd') or node_fields.get('end')
            is_end = is_end_val in (True, 'True', 'true', 1)

            children_raw = node_fields.get('children') or node_fields.get('child')
            children_dict = parse_dict_field(children_raw)
            children_tree = []

            for char, child_id in children_dict.items():
                if isinstance(child_id, str) and child_id.startswith('obj_'):
                    child_tree = build_trie_tree(child_id, char_val=str(char), visited=visited.copy())
                    if child_tree:
                        children_tree.append(child_tree)

            return {
                "id": node_id,
                "char": char_val,
                "is_end_of_word": is_end,
                "is_active": node_id == active_node_id,
                "children": children_tree
            }

        trie_trees = []
        for root_id in trie_roots:
            tree_struct = build_trie_tree(root_id)
            if tree_struct:
                trie_trees.append(tree_struct)

        status_msg = ""
        word_var = step.locals.get('word') or step.locals.get('prefix')
        if active_node_id:
            status_msg = f"Traversing Trie node for variable '{word_var or ''}'."
        else:
            status_msg = "Executing Trie operation."

        step.visualizations.append(VisualizationData(
            type="TRIE_METADATA",
            details={
                "trie_roots": trie_roots,
                "trie_trees": trie_trees,
                "active_node_id": active_node_id,
                "status_message": status_msg
            }
        ))

    return steps
