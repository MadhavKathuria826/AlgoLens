import copy
from typing import List
from models import Step, VisualizationData
from tracer import Tracer

def run_rbt_tracer(code: str) -> List[Step]:
    # 1. Run the standard tracer to get all execution steps
    standard_tracer = Tracer()
    steps = standard_tracer.run_code(code)
    
    # If standard tracing failed, return the error step
    if steps and any(v.type == 'Error' for s in steps for v in s.visualizations):
        return steps

    # 2. Helper to analyze tree state
    def analyze_tree(heap):
        nodes = {}
        in_degree = {}
        
        # Identify any nodes with left/right fields (representing tree topology)
        for obj_id, obj in heap.items():
            if isinstance(obj, dict) and 'fields' in obj:
                fields = obj['fields']
                if 'left' in fields or 'right' in fields:
                    nodes[obj_id] = fields
                    in_degree[obj_id] = 0

        # Calculate in-degree to find roots
        for obj_id, fields in nodes.items():
            left = fields.get('left')
            right = fields.get('right')
            if left and left in nodes:
                in_degree[left] += 1
            if right and right in nodes:
                in_degree[right] += 1

        roots = [obj_id for obj_id, deg in in_degree.items() if deg == 0]
        
        # Color extraction helper
        def get_color(fields):
            # Check color attribute
            col_val = fields.get('color')
            if col_val is not None:
                s = str(col_val).strip().upper()
                if s in ('RED', 'R', 'TRUE', '0'):
                    return 'RED'
                if s in ('BLACK', 'B', 'FALSE', '1'):
                    return 'BLACK'
            
            # Check red/is_red fields
            for r_field in ('red', 'is_red'):
                r_val = fields.get(r_field)
                if r_val is not None:
                    s = str(r_val).strip().upper()
                    if s in ('TRUE', '1', 'RED', 'R'):
                        return 'RED'
                    if s in ('FALSE', '0', 'BLACK', 'B'):
                        return 'BLACK'
            
            return 'BLACK'  # Default color is black

        colors = {}
        for obj_id, fields in nodes.items():
            colors[obj_id] = get_color(fields)

        return roots, nodes, colors

    # 3. Post-process steps to enrich with RBT metadata
    known_nodes = set()
    new_node_id = None
    insertion_path = []
    prev_colors = {}
    
    import ast
    try:
        parsed_tree = ast.parse(code)
    except Exception:
        parsed_tree = None

    def get_function_name(line_no):
        if not parsed_tree:
            return None
        for node in ast.walk(parsed_tree):
            if isinstance(node, ast.FunctionDef):
                if hasattr(node, "end_lineno"):
                    if node.lineno <= line_no <= node.end_lineno:
                        return node.name
        return None

    for i, step in enumerate(steps):
        # Analyze current tree state
        roots, nodes, colors = analyze_tree(step.heap)
        
        # Enrich the heap fields with normalized color
        for obj_id in list(step.heap.keys()):
            if obj_id in colors:
                step.heap[obj_id]['fields']['color'] = colors[obj_id]
                step.heap[obj_id]['fields']['is_removed'] = False
                step.heap[obj_id]['fields']['is_swapped'] = False
                if obj_id == new_node_id:
                    step.heap[obj_id]['fields']['is_new'] = True
                else:
                    step.heap[obj_id]['fields']['is_new'] = False

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
                if not curr or curr == 'None':
                    return False
                path.append(curr)
                if curr == target:
                    return True
                left = nodes[curr].get('left')
                right = nodes[curr].get('right')
                if find_path_to(left, target, path) or find_path_to(right, target, path):
                    return True
                path.pop()
                return False

            for r in roots:
                path = []
                if find_path_to(r, curr_ptr_node, path):
                    insertion_path = path
                    break

        # Check for color changes (recoloring)
        recolored_nodes = []
        for node_id, col in colors.items():
            if node_id in prev_colors and prev_colors[node_id] != col:
                recolored_nodes.append(node_id)
        prev_colors = copy.deepcopy(colors)

        # Build parent mapping
        parents = {}
        for parent_id, fields in nodes.items():
            left = fields.get('left')
            right = fields.get('right')
            if left and left in nodes:
                parents[left] = parent_id
            if right and right in nodes:
                parents[right] = parent_id

        # Check for double-red violations (educational highlight)
        double_red_node = None
        double_red_parent = None
        for node_id, col in colors.items():
            if col == 'RED' and node_id in parents:
                p_id = parents[node_id]
                if colors.get(p_id) == 'RED':
                    double_red_node = node_id
                    double_red_parent = p_id
                    break

        # Check rotation activity based on function context
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

        # Generate status messages
        status_message = ""
        is_deletion = current_func in ("delete", "_delete", "delete_fixup", "delete_node")
        
        if is_deletion:
            if curr_ptr_node:
                curr_val = nodes[curr_ptr_node].get('val')
                status_message = f"Traversing node {curr_val} during deletion."
            else:
                status_message = "Rebalancing/fixing up tree colors and properties after deletion."
        else:
            if rotation_type != "none":
                status_message = f"Performing {rotation_type.capitalize()} Rotation to restore balance."
            elif double_red_node:
                dr_val = nodes[double_red_node].get('val')
                dr_p_val = nodes[double_red_parent].get('val')
                status_message = f"Double-red violation detected: Node {dr_val} and parent {dr_p_val} are both RED."
            elif recolored_nodes:
                recolored_desc = []
                for rn in recolored_nodes:
                    if rn in nodes:
                        recolored_desc.append(f"Node {nodes[rn].get('val')} recolored to {colors[rn]}")
                status_message = ", ".join(recolored_desc) + "."
            elif curr_ptr_node:
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

    return steps
