import copy
from typing import List
from models import Step, VisualizationData
from tracer import Tracer

def run_avl_tracer(code: str) -> List[Step]:
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
        for obj_id, obj in heap.items():
            if isinstance(obj, dict) and obj.get('type') == 'TreeNode' and 'fields' in obj:
                nodes[obj_id] = obj['fields']
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
        
        heights = {}
        balance_factors = {}
        cycle_found = False
        
        path_visited = set()
        def get_height(node_id):
            nonlocal cycle_found
            if not node_id or node_id == 'None' or node_id not in nodes:
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
            
        # Traverse any unvisited nodes to ensure balance factors are computed for cyclic subtrees
        for obj_id in nodes:
            if obj_id not in heights:
                get_height(obj_id)
            
        cycle_found = cycle_found or (len(heights) < len(nodes))
        return roots, nodes, heights, balance_factors, cycle_found

    # 3. Post-process steps to identify insertions, traversals, and rotations
    # Track the set of node obj_ids known so far to detect when a new one is added
    known_nodes = set()
    new_node_id = None
    insertion_path = []
    
    # Track active rotation when a cycle is present
    active_rotation = "none"
    active_unbalanced = None
    active_rotation_nodes = []
    
    # Track composite double rotations (LR/RL)
    composite_rotation = "none"
    composite_unbalanced = None
    first_rotation_completed = False
    
    # We will identify directed edge configurations to detect rotations
    def get_edges(nodes):
        edges = {}
        for parent, fields in nodes.items():
            left = fields.get('left')
            right = fields.get('right')
            if left and left != 'None':
                edges[(parent, left)] = 'left'
            if right and right != 'None':
                edges[(parent, right)] = 'right'
        return edges

    for i, step in enumerate(steps):
        should_complete_first_rotation = False
        # Analyze current tree state
        roots, nodes, heights, balance_factors, cycle_found = analyze_tree(step.heap)
        
        # Enrich the heap fields with height and balance_factor
        for obj_id in list(step.heap.keys()):
            if obj_id in nodes:
                step.heap[obj_id]['fields']['height'] = heights.get(obj_id, 1)
                step.heap[obj_id]['fields']['balance_factor'] = balance_factors.get(obj_id, 0)
                if obj_id == new_node_id:
                    step.heap[obj_id]['fields']['is_new'] = True
                else:
                    step.heap[obj_id]['fields']['is_new'] = False

        # Detect new node insertion
        current_node_ids = set(nodes.keys())
        newly_added = current_node_ids - known_nodes
        if newly_added:
            # We found a newly inserted node!
            new_node_id = list(newly_added)[0]
            known_nodes.update(newly_added)
            if new_node_id in step.heap:
                step.heap[new_node_id]['fields']['is_new'] = True

        # Determine insertion / comparison path
        # Find which node is currently pointed to by local pointer variables (like 'node', 'curr', 'x')
        curr_ptr_node = None
        if not ('y' in step.locals and 'T2' in step.locals):
            for var_name in ('node', 'curr', 'x', 'p', 'root'):
                val = step.locals.get(var_name)
                if isinstance(val, str) and val.startswith('obj_') and val in nodes:
                    curr_ptr_node = val
                    break
        
        if curr_ptr_node:
            # Find the path from root to this node
            # BFS or DFS to find path
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

        # Detect if a rotation is about to happen or has happened
        # We can look at the balance factors of step i
        unbalanced_node = None
        rotation_type = "none"
        rotation_nodes = []
        status_message = ""
        
        # Check if any node is unbalanced in this step
        for obj_id, bf in balance_factors.items():
            if abs(bf) >= 2:
                unbalanced_node = obj_id
                # Determine rotation type based on balance factors
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

        # Override and track composite rotations (LR/RL)
        if rotation_type in ("LR", "RL"):
            composite_rotation = rotation_type
            composite_unbalanced = unbalanced_node
            first_rotation_completed = False
        elif composite_rotation == "LR" and rotation_type == "LL":
            # Second step of LR rotation
            rotation_type = "LR"
            unbalanced_node = composite_unbalanced
            # Update rotation nodes for the second step (right rotate on root)
            left_child = nodes[unbalanced_node].get('left') if unbalanced_node in nodes else None
            if left_child:
                rotation_nodes = [unbalanced_node, left_child, nodes[left_child].get('left')]
        elif composite_rotation == "RL" and rotation_type == "RR":
            # Second step of RL rotation
            rotation_type = "RL"
            unbalanced_node = composite_unbalanced
            # Update rotation nodes for the second step (left rotate on root)
            right_child = nodes[unbalanced_node].get('right') if unbalanced_node in nodes else None
            if right_child:
                rotation_nodes = [unbalanced_node, right_child, nodes[right_child].get('right')]

         # Handle cycle state during rotation
        if rotation_type != "none":
            active_rotation = rotation_type
            active_unbalanced = unbalanced_node
            active_rotation_nodes = rotation_nodes
        elif active_rotation != "none":
            if cycle_found:
                rotation_type = active_rotation
                unbalanced_node = active_unbalanced
                rotation_nodes = active_rotation_nodes

        # Filter out None elements from rotation nodes
        rotation_nodes = [r for r in rotation_nodes if r and r != 'None' and r in nodes]

        # Generate status messages
        if curr_ptr_node:
            curr_val = nodes[curr_ptr_node].get('val')
            status_message = f"Visiting node {curr_val} during insertion traversal."
        elif new_node_id and new_node_id in nodes:
            new_val = nodes[new_node_id].get('val')
            status_message = f"Inserted new node {new_val}."
        
        if unbalanced_node and rotation_type != "none":
            unbalanced_val = nodes[unbalanced_node].get('val')
            # Check if this is a double rotation second step
            if rotation_type == "LR" and composite_rotation == "LR" and first_rotation_completed:
                status_message = f"Node {unbalanced_val} is unbalanced (BF = {balance_factors[unbalanced_node]}). Triggering LR rotation (second step: right rotate)."
            elif rotation_type == "RL" and composite_rotation == "RL" and first_rotation_completed:
                status_message = f"Node {unbalanced_val} is unbalanced (BF = {balance_factors[unbalanced_node]}). Triggering RL rotation (second step: left rotate)."
            else:
                status_message = f"Node {unbalanced_val} is unbalanced (BF = {balance_factors[unbalanced_node]}). Triggering {rotation_type} rotation."

        # Detect if rotation completed in this step
        # (if previous step had rotation_type != "none" and current step is balanced)
        if i > 0:
            prev_vis = next((v for v in steps[i-1].visualizations if v.type == "AVL_METADATA"), None)
            if prev_vis and prev_vis.details.get("rotation_type") != "none":
                # Check if the node is now balanced or has been rotated
                prev_unbalanced = prev_vis.details.get("unbalanced_node")
                prev_rot_type = prev_vis.details.get("rotation_type")
                if prev_unbalanced not in balance_factors or abs(balance_factors.get(prev_unbalanced, 0)) < 2:
                    if prev_rot_type in ("LR", "RL") and not first_rotation_completed:
                        # First step of double rotation complete
                        should_complete_first_rotation = True
                        status_message = f"{prev_rot_type} rotation: first rotation complete (child rotated)."
                    else:
                        # Standalone rotation or second step of double rotation complete
                        status_message = f"{prev_rot_type} rotation complete. Tree is now balanced."

        # Reset active rotation once cycle is broken and rotation is complete
        if rotation_type == "none" and active_rotation != "none" and not cycle_found:
            if first_rotation_completed:
                # This was the completion of the second rotation!
                composite_rotation = "none"
                composite_unbalanced = None
                first_rotation_completed = False
            elif should_complete_first_rotation:
                # First rotation complete, set flag for second stage
                first_rotation_completed = True

            active_rotation = "none"
            active_unbalanced = None
            active_rotation_nodes = []

        # Add AVL Metadata visualization
        avl_vis = VisualizationData(
            type="AVL_METADATA",
            details={
                "rotation_type": rotation_type,
                "unbalanced_node": unbalanced_node,
                "rotation_nodes": rotation_nodes,
                "insertion_path": copy.deepcopy(insertion_path),
                "new_node_id": new_node_id,
                "status_message": status_message
            }
        )
        step.visualizations.append(avl_vis)

    return steps
