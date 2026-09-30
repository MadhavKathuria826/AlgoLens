"""
AlgoLens Universal Structural Adapter (Milestone 9)
Enriches Universal Event Protocol steps with domain-specific metadata
for AVL Trees, Red-Black Trees, Tries, and Dynamic Programming (Tabulation & Memoization).

Ensures 100% visualization parity with legacy tracers while preserving the
underlying Universal AlgoLens Event stream, bidirectional reversibility, and PlaybackEngine compatibility.
"""

import ast
import copy
from typing import List, Dict, Any, Optional, Set, Tuple
from models import Step, VisualizationData


# ==============================================================================
# 1. AVL Tree Structural Adapter
# ==============================================================================

def enrich_avl_steps(steps: List[Step], code: str) -> List[Step]:
    """
    Enriches steps with AVL Tree balance factors, heights, rotation detections (LL/RR/LR/RL),
    traversal paths, and deletion successor information.
    """
    if not steps:
        return steps

    def analyze_tree(heap):
        nodes = {}
        in_degree = {}
        for obj_id, obj in heap.items():
            if isinstance(obj, dict) and 'fields' in obj:
                fields = obj['fields']
                if 'left' in fields or 'right' in fields or obj.get('type') in ('TreeNode', 'LocalTreeNode', 'Node'):
                    nodes[obj_id] = fields
                    in_degree[obj_id] = 0

        for obj_id, fields in nodes.items():
            left = fields.get('left')
            right = fields.get('right')
            if left and left in nodes:
                in_degree[left] = in_degree.get(left, 0) + 1
            if right and right in nodes:
                in_degree[right] = in_degree.get(right, 0) + 1

        roots = [obj_id for obj_id, deg in in_degree.items() if deg == 0]

        heights = {}
        balance_factors = {}
        cycle_found = False
        path_visited = set()

        def get_height(node_id):
            nonlocal cycle_found
            if not node_id or node_id in ('None', '0x0000', 'nullptr', 'NULL') or node_id not in nodes:
                return 0
            if node_id in path_visited:
                cycle_found = True
                return 0
            path_visited.add(node_id)
            if node_id in heights:
                path_visited.remove(node_id)
                return heights[node_id]

            left = nodes[node_id].get('left')
            right = nodes[node_id].get('right')

            h_left = get_height(left)
            h_right = get_height(right)

            h = 1 + max(h_left, h_right)
            heights[node_id] = h
            balance_factors[node_id] = h_left - h_right
            path_visited.remove(node_id)
            return h

        for r in roots:
            get_height(r)

        for obj_id in nodes:
            if obj_id not in heights:
                get_height(obj_id)

        cycle_found = cycle_found or (len(heights) < len(nodes))
        return roots, nodes, heights, balance_factors, cycle_found

    try:
        parsed_tree = ast.parse(code)
    except Exception:
        parsed_tree = None

    def get_function_name(line_no):
        if not parsed_tree:
            return None
        for node in ast.walk(parsed_tree):
            if isinstance(node, ast.FunctionDef) and hasattr(node, "end_lineno"):
                if node.lineno <= line_no <= node.end_lineno:
                    return node.name
        return None

    known_nodes = set()
    new_node_id = None
    insertion_path = []
    active_rotation = "none"
    active_unbalanced = None
    active_rotation_nodes = []
    composite_rotation = "none"
    composite_unbalanced = None
    first_rotation_completed = False

    for i, step in enumerate(steps):
        should_complete_first_rotation = False
        roots, nodes, heights, balance_factors, cycle_found = analyze_tree(step.heap)

        # Enrich heap fields with height and balance factor
        for obj_id in list(step.heap.keys()):
            if obj_id in nodes:
                step.heap[obj_id]['fields']['height'] = heights.get(obj_id, 1)
                step.heap[obj_id]['fields']['balance_factor'] = balance_factors.get(obj_id, 0)
                step.heap[obj_id]['fields']['is_removed'] = False
                step.heap[obj_id]['fields']['is_swapped'] = False
                step.heap[obj_id]['fields']['is_new'] = (obj_id == new_node_id)

        # Detect new node insertion
        current_node_ids = set(nodes.keys())
        newly_added = current_node_ids - known_nodes
        if newly_added:
            new_node_id = list(newly_added)[0]
            known_nodes.update(newly_added)
            if new_node_id in step.heap:
                step.heap[new_node_id]['fields']['is_new'] = True

        # Determine insertion / comparison path
        curr_ptr_node = None
        if not ('y' in step.locals and 'T2' in step.locals):
            for var_name in ('node', 'curr', 'x', 'p', 'root'):
                val = step.locals.get(var_name)
                if isinstance(val, str) and val.startswith('obj_') and val in nodes:
                    curr_ptr_node = val
                    break

        if curr_ptr_node:
            def find_path_to(curr, target, path):
                if not curr or curr in ('None', '0x0000', 'nullptr', 'NULL'):
                    return False
                path.append(curr)
                if curr == target:
                    return True
                left = nodes[curr].get('left') if curr in nodes else None
                right = nodes[curr].get('right') if curr in nodes else None
                if find_path_to(left, target, path) or find_path_to(right, target, path):
                    return True
                path.pop()
                return False

            for r in roots:
                path = []
                if find_path_to(r, curr_ptr_node, path):
                    insertion_path = path
                    break

        # Detect rotations based on balance factors
        unbalanced_node = None
        rotation_type = "none"
        rotation_nodes = []
        status_message = ""

        for obj_id, bf in balance_factors.items():
            if abs(bf) >= 2:
                unbalanced_node = obj_id
                if bf >= 2:
                    left_child = nodes[obj_id].get('left')
                    if left_child and left_child in balance_factors:
                        left_bf = balance_factors[left_child]
                        if left_bf >= 0:
                            rotation_type = "LL"
                            rotation_nodes = [obj_id, left_child, nodes[left_child].get('left')]
                        else:
                            rotation_type = "LR"
                            rotation_nodes = [obj_id, left_child, nodes[left_child].get('right')]
                elif bf <= -2:
                    right_child = nodes[obj_id].get('right')
                    if right_child and right_child in balance_factors:
                        right_bf = balance_factors[right_child]
                        if right_bf <= 0:
                            rotation_type = "RR"
                            rotation_nodes = [obj_id, right_child, nodes[right_child].get('right')]
                        else:
                            rotation_type = "RL"
                            rotation_nodes = [obj_id, right_child, nodes[right_child].get('left')]
                break

        # Handle composite double rotations (LR/RL)
        if rotation_type in ("LR", "RL"):
            composite_rotation = rotation_type
            composite_unbalanced = unbalanced_node
            first_rotation_completed = False
        elif composite_rotation == "LR" and rotation_type == "LL":
            rotation_type = "LR"
            unbalanced_node = composite_unbalanced
            left_child = nodes[unbalanced_node].get('left') if unbalanced_node in nodes else None
            if left_child and left_child in nodes:
                rotation_nodes = [unbalanced_node, left_child, nodes[left_child].get('left')]
        elif composite_rotation == "RL" and rotation_type == "RR":
            rotation_type = "RL"
            unbalanced_node = composite_unbalanced
            right_child = nodes[unbalanced_node].get('right') if unbalanced_node in nodes else None
            if right_child and right_child in nodes:
                rotation_nodes = [unbalanced_node, right_child, nodes[right_child].get('right')]

        if rotation_type != "none":
            active_rotation = rotation_type
            active_unbalanced = unbalanced_node
            active_rotation_nodes = rotation_nodes
        elif active_rotation != "none":
            if cycle_found:
                rotation_type = active_rotation
                unbalanced_node = active_unbalanced
                rotation_nodes = active_rotation_nodes

        rotation_nodes = [r for r in rotation_nodes if r and r not in ('None', '0x0000', 'nullptr', 'NULL') and r in nodes]

        current_func = get_function_name(step.line_number)
        is_deletion = current_func in ("delete", "_delete", "_get_min_value_node")

        removed_node = None
        successor_swap_node = None

        if is_deletion:
            node_id = step.locals.get('node')
            key = step.locals.get('key')
            temp_id = step.locals.get('temp')

            if node_id and node_id in nodes:
                node_val = nodes[node_id].get('val')
                if key == node_val:
                    left_child = nodes[node_id].get('left')
                    right_child = nodes[node_id].get('right')
                    is_leaf = (not left_child or left_child in ('None', '0x0000')) and (not right_child or right_child in ('None', '0x0000'))
                    is_one_child = not is_leaf and (not left_child or left_child in ('None', '0x0000') or not right_child or right_child in ('None', '0x0000'))

                    if is_leaf:
                        removed_node = node_id
                        status_message = f"Leaf deletion: removing node {node_val} (no children)."
                    elif is_one_child:
                        removed_node = node_id
                        child_id = left_child if left_child and left_child not in ('None', '0x0000') else right_child
                        child_val = nodes[child_id].get('val') if child_id in nodes else 'None'
                        status_message = f"One-child deletion: replacing node {node_val} with child {child_val}."
                    else:
                        successor_swap_node = node_id
                        if temp_id and temp_id in nodes:
                            removed_node = temp_id
                            successor_val = nodes[temp_id].get('val')
                            status_message = f"Two-child deletion: copying successor {successor_val}'s value into node {node_val}."
                        else:
                            status_message = f"Two-child deletion: finding in-order successor for node {node_val}."

            if not status_message:
                if curr_ptr_node and curr_ptr_node in nodes:
                    curr_val = nodes[curr_ptr_node].get('val')
                    status_message = f"Visiting node {curr_val} during deletion traversal."
                elif node_id and node_id in nodes:
                    node_val = nodes[node_id].get('val')
                    status_message = f"Rebalancing node {node_val} after deletion."
                else:
                    status_message = "Returning from delete recursion."
        else:
            if curr_ptr_node and curr_ptr_node in nodes:
                curr_val = nodes[curr_ptr_node].get('val')
                status_message = f"Visiting node {curr_val} during insertion traversal."
            elif new_node_id and new_node_id in nodes:
                new_val = nodes[new_node_id].get('val')
                status_message = f"Inserted new node {new_val}."

        if removed_node and removed_node in step.heap:
            step.heap[removed_node]['fields']['is_removed'] = True
        if successor_swap_node and successor_swap_node in step.heap:
            step.heap[successor_swap_node]['fields']['is_swapped'] = True

        if unbalanced_node and rotation_type != "none" and unbalanced_node in nodes:
            unbalanced_val = nodes[unbalanced_node].get('val')
            if rotation_type == "LR" and composite_rotation == "LR" and first_rotation_completed:
                status_message = f"Node {unbalanced_val} is unbalanced (BF = {balance_factors[unbalanced_node]}). Triggering LR rotation (second step: right rotate)."
            elif rotation_type == "RL" and composite_rotation == "RL" and first_rotation_completed:
                status_message = f"Node {unbalanced_val} is unbalanced (BF = {balance_factors[unbalanced_node]}). Triggering RL rotation (second step: left rotate)."
            else:
                status_message = f"Node {unbalanced_val} is unbalanced (BF = {balance_factors[unbalanced_node]}). Triggering {rotation_type} rotation."

        if i > 0:
            prev_vis = next((v for v in steps[i-1].visualizations if v.type == "AVL_METADATA"), None)
            if prev_vis and prev_vis.details.get("rotation_type") != "none":
                prev_unbalanced = prev_vis.details.get("unbalanced_node")
                prev_rot_type = prev_vis.details.get("rotation_type")
                if prev_unbalanced not in balance_factors or abs(balance_factors.get(prev_unbalanced, 0)) < 2:
                    if prev_rot_type in ("LR", "RL") and not first_rotation_completed:
                        should_complete_first_rotation = True
                        status_message = f"{prev_rot_type} rotation: first rotation complete (child rotated)."
                    else:
                        status_message = f"{prev_rot_type} rotation complete. Tree is now balanced."

        if rotation_type == "none" and active_rotation != "none" and not cycle_found:
            if first_rotation_completed:
                composite_rotation = "none"
                composite_unbalanced = None
                first_rotation_completed = False
            elif should_complete_first_rotation:
                first_rotation_completed = True
            active_rotation = "none"
            active_unbalanced = None
            active_rotation_nodes = []

        avl_vis = VisualizationData(
            type="AVL_METADATA",
            details={
                "rotation_type": rotation_type,
                "unbalanced_node": unbalanced_node,
                "rotation_nodes": rotation_nodes,
                "insertion_path": copy.deepcopy(insertion_path),
                "new_node_id": new_node_id,
                "removed_node": removed_node,
                "successor_swap_node": successor_swap_node,
                "status_message": status_message
            }
        )
        step.visualizations.append(avl_vis)
        step.isTreeAlgorithm = True

    return steps


# ==============================================================================
# 2. Red-Black Tree (RBT) Structural Adapter
# ==============================================================================

def enrich_rbt_steps(steps: List[Step], code: str) -> List[Step]:
    """
    Enriches steps with Red-Black Tree colors, double-red violation detection,
    recoloring tracking, and rotation metadata.
    """
    if not steps:
        return steps

    def analyze_tree(heap):
        nodes = {}
        in_degree = {}
        for obj_id, obj in heap.items():
            if isinstance(obj, dict) and 'fields' in obj:
                fields = obj['fields']
                if 'left' in fields or 'right' in fields or obj.get('type') in ('TreeNode', 'LocalTreeNode', 'Node'):
                    nodes[obj_id] = fields
                    in_degree[obj_id] = 0

        for obj_id, fields in nodes.items():
            left = fields.get('left')
            right = fields.get('right')
            if left and left in nodes:
                in_degree[left] = in_degree.get(left, 0) + 1
            if right and right in nodes:
                in_degree[right] = in_degree.get(right, 0) + 1

        roots = [obj_id for obj_id, deg in in_degree.items() if deg == 0]

        def get_color(fields):
            col_val = fields.get('color')
            if col_val is not None:
                s = str(col_val).strip().upper()
                if s in ('RED', 'R', 'TRUE', '0'):
                    return 'RED'
                if s in ('BLACK', 'B', 'FALSE', '1'):
                    return 'BLACK'
            for r_field in ('red', 'is_red'):
                r_val = fields.get(r_field)
                if r_val is not None:
                    s = str(r_val).strip().upper()
                    if s in ('TRUE', '1', 'RED', 'R'):
                        return 'RED'
                    if s in ('FALSE', '0', 'BLACK', 'B'):
                        return 'BLACK'
            return 'BLACK'

        colors = {obj_id: get_color(fields) for obj_id, fields in nodes.items()}
        return roots, nodes, colors

    try:
        parsed_tree = ast.parse(code)
    except Exception:
        parsed_tree = None

    def get_function_name(line_no):
        if not parsed_tree:
            return None
        for node in ast.walk(parsed_tree):
            if isinstance(node, ast.FunctionDef) and hasattr(node, "end_lineno"):
                if node.lineno <= line_no <= node.end_lineno:
                    return node.name
        return None

    known_nodes = set()
    new_node_id = None
    insertion_path = []
    prev_colors = {}

    for step in steps:
        roots, nodes, colors = analyze_tree(step.heap)

        # Enrich heap fields with normalized color
        for obj_id in list(step.heap.keys()):
            if obj_id in colors:
                step.heap[obj_id]['fields']['color'] = colors[obj_id]
                step.heap[obj_id]['fields']['is_removed'] = False
                step.heap[obj_id]['fields']['is_swapped'] = False
                step.heap[obj_id]['fields']['is_new'] = (obj_id == new_node_id)

        # Detect new node insertion
        current_node_ids = set(nodes.keys())
        newly_added = current_node_ids - known_nodes
        if newly_added:
            new_node_id = list(newly_added)[0]
            known_nodes.update(newly_added)
            if new_node_id in step.heap:
                step.heap[new_node_id]['fields']['is_new'] = True

        # Track active traversal pointers
        curr_ptr_node = None
        for var_name in ('node', 'curr', 'x', 'p', 'root', 'z'):
            val = step.locals.get(var_name)
            if isinstance(val, str) and val.startswith('obj_') and val in nodes:
                curr_ptr_node = val
                break

        if curr_ptr_node:
            def find_path_to(curr, target, path):
                if not curr or curr in ('None', '0x0000', 'nullptr', 'NULL'):
                    return False
                path.append(curr)
                if curr == target:
                    return True
                left = nodes[curr].get('left') if curr in nodes else None
                right = nodes[curr].get('right') if curr in nodes else None
                if find_path_to(left, target, path) or find_path_to(right, target, path):
                    return True
                path.pop()
                return False

            for r in roots:
                path = []
                if find_path_to(r, curr_ptr_node, path):
                    insertion_path = path
                    break

        recolored_nodes = [node_id for node_id, col in colors.items() if node_id in prev_colors and prev_colors[node_id] != col]
        prev_colors = copy.deepcopy(colors)

        parents = {}
        for parent_id, fields in nodes.items():
            left = fields.get('left')
            right = fields.get('right')
            if left and left in nodes:
                parents[left] = parent_id
            if right and right in nodes:
                parents[right] = parent_id

        double_red_node = None
        double_red_parent = None
        for node_id, col in colors.items():
            if col == 'RED' and node_id in parents:
                p_id = parents[node_id]
                if colors.get(p_id) == 'RED':
                    double_red_node = node_id
                    double_red_parent = p_id
                    break

        current_func = get_function_name(step.line_number)
        rotation_type = "none"
        rotation_nodes = []
        if current_func in ("left_rotate", "right_rotate", "rotate_left", "rotate_right"):
            rotation_type = "left" if "left" in current_func else "right"
            rot_candidates = []
            for var in ('x', 'y', 'node', 'parent', 'pivot'):
                val = step.locals.get(var)
                if isinstance(val, str) and val.startswith('obj_') and val in nodes:
                    rot_candidates.append(val)
            rotation_nodes = list(set(rot_candidates))

        status_message = ""
        is_deletion = current_func in ("delete", "_delete", "delete_fixup", "delete_node")

        if is_deletion:
            if curr_ptr_node and curr_ptr_node in nodes:
                curr_val = nodes[curr_ptr_node].get('val')
                status_message = f"Traversing node {curr_val} during deletion."
            else:
                status_message = "Rebalancing/fixing up tree colors and properties after deletion."
        else:
            if rotation_type != "none":
                status_message = f"Performing {rotation_type.capitalize()} Rotation to restore balance."
            elif double_red_node and double_red_parent:
                dr_val = nodes[double_red_node].get('val') if double_red_node in nodes else double_red_node
                dr_p_val = nodes[double_red_parent].get('val') if double_red_parent in nodes else double_red_parent
                status_message = f"Double-red violation detected: Node {dr_val} and parent {dr_p_val} are both RED."
            elif recolored_nodes:
                recolored_desc = [f"Node {nodes[rn].get('val', rn)} recolored to {colors[rn]}" for rn in recolored_nodes if rn in nodes]
                status_message = ", ".join(recolored_desc) + "."
            elif curr_ptr_node and curr_ptr_node in nodes:
                curr_val = nodes[curr_ptr_node].get('val')
                status_message = f"Traversing node {curr_val} during insertion."
            elif new_node_id and new_node_id in nodes:
                new_val = nodes[new_node_id].get('val')
                status_message = f"Inserted new node {new_val} (colored RED)."

        if not status_message:
            status_message = f"Step {step.step_number}: Executing line {step.line_number}."

        rbt_vis = VisualizationData(
            type="RBT_METADATA",
            details={
                "rotation_type": rotation_type,
                "rotation_nodes": rotation_nodes,
                "insertion_path": copy.deepcopy(insertion_path),
                "new_node_id": new_node_id,
                "recolored_nodes": recolored_nodes,
                "double_red_node": double_red_node,
                "double_red_parent": double_red_parent,
                "status_message": status_message
            }
        )
        step.visualizations.append(rbt_vis)
        step.isTreeAlgorithm = True

    return steps


# ==============================================================================
# 3. Trie (Prefix Tree) Structural Adapter
# ==============================================================================

def enrich_trie_steps(steps: List[Step]) -> List[Step]:
    """
    Enriches steps with Trie multi-child hierarchical tree structures,
    active traversal pointers, and word completion markers.
    """
    if not steps:
        return steps

    def parse_dict_field(val, heap):
        if isinstance(val, dict):
            return val
        if isinstance(val, str) and val.startswith('obj_') and val in heap:
            # The dictionary is stored as a heap object
            d_obj = heap[val]
            if isinstance(d_obj, dict) and 'fields' in d_obj:
                return {k: v for k, v in d_obj['fields'].items() if k not in ('size', 'length')}
        return {}

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
                children_dict = parse_dict_field(children_raw, heap)
                for char, child_id in children_dict.items():
                    if isinstance(child_id, str) and child_id.startswith('obj_'):
                        referenced_children.add(child_id)

            for obj_id in nodes:
                if obj_id not in referenced_children and nodes[obj_id]['type'] != 'Trie':
                    trie_roots.append(obj_id)

        return trie_roots, nodes

    for step in steps:
        trie_roots, nodes = extract_trie_nodes(step.heap)

        active_node_id = None
        for var_name in ('curr', 'node', 'p', 'root', 'curr_node'):
            val = step.locals.get(var_name)
            if isinstance(val, str) and val.startswith('obj_') and val in nodes:
                active_node_id = val
                break

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
            children_dict = parse_dict_field(children_raw, step.heap)
            children_tree = []

            for char, child_id in sorted(children_dict.items(), key=lambda x: str(x[0])):
                if isinstance(child_id, str) and child_id.startswith('obj_'):
                    child_tree = build_trie_tree(child_id, char_val=str(char), visited=visited.copy())
                    if child_tree:
                        children_tree.append(child_tree)

            return {
                "id": node_id,
                "char": char_val,
                "is_end_of_word": is_end,
                "is_active": (node_id == active_node_id),
                "children": children_tree
            }

        trie_trees = []
        for root_id in trie_roots:
            tree_struct = build_trie_tree(root_id)
            if tree_struct:
                trie_trees.append(tree_struct)

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


# ==============================================================================
# 4. Dynamic Programming (DP) Structural Adapter
# ==============================================================================

def enrich_dp_tabulation_steps(
    steps: List[Step],
    code: str,
    table_var_name: str,
    dimensions: int
) -> List[Step]:
    """
    Enriches steps with 1D/2D DP table visualizations, target cell writes,
    and source cell dependency highlighting.
    """
    if not steps:
        return steps

    from dp_tracer import post_process_tabulation
    return post_process_tabulation(steps, code, table_var_name, dimensions)


def enrich_dp_memoization_steps(
    steps: List[Step],
    code: str,
    memo_res: Dict[str, Any]
) -> List[Step]:
    """
    Enriches steps with recursive call frames, cache hits, and cache write events
    for memoized algorithms.
    """
    if not steps:
        return steps

    cache_var_name = memo_res.get("cache_var_name")
    func_name = memo_res.get("func_name")
    if not func_name:
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_name = node.name
                    break
        except Exception:
            pass

    known_cache_keys: Set[str] = set()
    call_depth = 0

    for step in steps:
        # Check call depth from locals or active frame
        # If cache_var_name is present in step.locals, monitor for writes
        memo_val = step.locals.get(cache_var_name) if cache_var_name else None
        new_writes = []
        if isinstance(memo_val, dict):
            current_keys = set(str(k) for k in memo_val.keys())
            new_keys = current_keys - known_cache_keys
            for k in sorted(new_keys):
                new_writes.append((k, memo_val.get(k)))
                known_cache_keys.add(k)

        # Detect memoization visualization
        if new_writes:
            for k, val in new_writes:
                step.visualizations.append(VisualizationData(
                    type="MEMOIZATION",
                    details={
                        "event": "cache_write",
                        "key": str(k),
                        "call_depth": max(1, call_depth),
                        "value": val
                    }
                ))
        elif any(v.type == 'Variable' for v in step.visualizations):
            # Check if this step is executing the target function
            param_names = [p for p in step.locals.keys() if p not in (cache_var_name, 'self', 'cls') and not p.startswith('__')]
            if param_names:
                args = [step.locals[p] for p in sorted(param_names)]
                key_str = str(args[0]) if len(args) == 1 else str(tuple(args))
                is_hit = False
                if isinstance(memo_val, dict) and (key_str in memo_val or (args[0] if len(args) == 1 else tuple(args)) in memo_val):
                    is_hit = True

                step.visualizations.append(VisualizationData(
                    type="MEMOIZATION",
                    details={
                        "event": "cache_hit" if is_hit else "call",
                        "key": key_str,
                        "call_depth": max(1, call_depth)
                    }
                ))

    return steps
