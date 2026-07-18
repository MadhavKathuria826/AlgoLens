import json
import ast
import re

def parse_test_case(test_case_str: str) -> dict:
    test_case_str = test_case_str.strip()
    if not test_case_str:
        return {}
    
    # Try parsing as JSON first
    try:
        data = json.loads(test_case_str)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
        
    # Fallback: parse as Python assignment lines
    data = {}
    lines = test_case_str.splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('//'):
            continue
        try:
            tree = ast.parse(line)
            if tree.body and isinstance(tree.body[0], ast.Assign):
                stmt = tree.body[0]
                val = ast.literal_eval(stmt.value)
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        data[target.id] = val
        except Exception:
            pass
    return data

def to_cpp_init(param_name: str, param_type: str, value) -> str:
    t = param_type.strip()
    
    if t == 'int':
        val_str = str(int(value)) if value is not None else '0'
        return f"int {param_name} = {val_str};"
        
    elif t in ('double', 'float'):
        val_str = str(float(value)) if value is not None else '0.0'
        return f"double {param_name} = {val_str};"
        
    elif t == 'bool':
        val_str = 'true' if value else 'false'
        return f"bool {param_name} = {val_str};"
        
    elif t in ('std::string', 'string'):
        val_str = json.dumps(str(value)) if value is not None else '""'
        return f"std::string {param_name} = {val_str};"
        
    elif t in ('std::vector<int>', 'vector<int>'):
        if not isinstance(value, list):
            value = []
        items_str = ", ".join(str(int(x)) for x in value if x is not None)
        return f"std::vector<int> {param_name} = {{{items_str}}};"
        
    elif t in ('std::vector<std::string>', 'vector<string>'):
        if not isinstance(value, list):
            value = []
        items_str = ", ".join(json.dumps(str(x)) for x in value if x is not None)
        return f"std::vector<std::string> {param_name} = {{{items_str}}};"
        
    elif 'ListNode' in t:
        if not isinstance(value, list):
            value = []
        items_str = ", ".join(str(int(x)) for x in value if x is not None)
        return (
            f"std::vector<int> _temp_vals_{param_name} = {{{items_str}}};\n"
            f"    ListNode* {param_name} = deserialize_list(_temp_vals_{param_name});"
        )
        
    elif 'TreeNode' in t:
        if not isinstance(value, list):
            value = []
        tokens = []
        for x in value:
            if x is None or x == 'null' or x == 'None':
                tokens.append('"null"')
            else:
                tokens.append(json.dumps(str(x)))
        items_str = ", ".join(tokens)
        return (
            f"std::vector<std::string> _temp_vals_{param_name} = {{{items_str}}};\n"
            f"    TreeNode* {param_name} = deserialize_tree(_temp_vals_{param_name});"
        )
        
    # Default fallback
    return f"// Unsupported parameter type: {t} for {param_name}"

def build_driver_code(entry_info: dict, test_case_str: str) -> str:
    test_case_data = parse_test_case(test_case_str)
    
    # 1. Structural helpers
    driver_helpers = """
// --- STRUCTURAL DESERIALIZERS & SERIALIZERS ---
#ifndef ALGOLENS_HELPERS
#define ALGOLENS_HELPERS

TreeNode* deserialize_tree(const std::vector<std::string>& vals) {
    if (vals.empty() || vals[0] == "null" || vals[0] == "None") return nullptr;
    TreeNode* root = new TreeNode;
    root->val = std::stoi(vals[0]);
    root->left = nullptr;
    root->right = nullptr;
    
    std::queue<TreeNode*> q;
    q.push(root);
    
    size_t i = 1;
    while (!q.empty() && i < vals.size()) {
        TreeNode* curr = q.front();
        q.pop();
        
        if (i < vals.size() && vals[i] != "null" && vals[i] != "None") {
            TreeNode* leftNode = new TreeNode;
            leftNode->val = std::stoi(vals[i]);
            leftNode->left = nullptr;
            leftNode->right = nullptr;
            curr->left = leftNode;
            q.push(leftNode);
        }
        i++;
        
        if (i < vals.size() && vals[i] != "null" && vals[i] != "None") {
            TreeNode* rightNode = new TreeNode;
            rightNode->val = std::stoi(vals[i]);
            rightNode->left = nullptr;
            rightNode->right = nullptr;
            curr->right = rightNode;
            q.push(rightNode);
        }
        i++;
    }
    return root;
}

ListNode* deserialize_list(const std::vector<int>& vals) {
    if (vals.empty()) return nullptr;
    ListNode* head = new ListNode;
    head->val = vals[0];
    head->next = nullptr;
    ListNode* curr = head;
    for (size_t i = 1; i < vals.size(); ++i) {
        ListNode* node = new ListNode;
        node->val = vals[i];
        node->next = nullptr;
        curr->next = node;
        curr = node;
    }
    return head;
}

void serialize_output(int val) {
    std::cout << val << std::endl;
}
void serialize_output(double val) {
    std::cout << val << std::endl;
}
void serialize_output(bool val) {
    std::cout << (val ? "true" : "false") << std::endl;
}
void serialize_output(const std::string& val) {
    std::cout << "\\"" << val << "\\"" << std::endl;
}
void serialize_output(const std::vector<int>& val) {
    std::cout << "[";
    for (size_t i = 0; i < val.size(); ++i) {
        std::cout << val[i] << (i + 1 < val.size() ? ", " : "");
    }
    std::cout << "]" << std::endl;
}
void serialize_output(ListNode* head) {
    std::cout << "[";
    ListNode* curr = head;
    while (curr) {
        std::cout << curr->val << (curr->next ? ", " : "");
        curr = curr->next;
    }
    std::cout << "]" << std::endl;
}
#endif
"""

    # 2. Main function setup
    main_body = []
    
    # Declarations and assignments
    params = entry_info.get("params", [])
    for p in params:
        p_name = p["name"]
        p_type = p["type"]
        val = test_case_data.get(p_name, None)
        main_body.append(f"    {to_cpp_init(p_name, p_type, val)}")

    # Function call execution
    param_names_str = ", ".join(p["name"] for p in params)
    ret_type = entry_info.get("return_type", "void").strip()
    is_void = ret_type == 'void'
    
    is_class = entry_info.get("is_class", False)
    class_name = entry_info.get("class_name", "Solution")
    
    if is_class:
        main_body.append(f"    {class_name} _sol;")
        if is_void:
            main_body.append(f"    _sol.{entry_info['name']}({param_names_str});")
        else:
            main_body.append(f"    auto _res = _sol.{entry_info['name']}({param_names_str});")
    else:
        if is_void:
            main_body.append(f"    {entry_info['name']}({param_names_str});")
        else:
            main_body.append(f"    auto _res = {entry_info['name']}({param_names_str});")
            
    # Serialize outputs
    if is_void:
        main_body.append('    std::cout << "null" << std::endl;')
    else:
        main_body.append("    serialize_output(_res);")
        
    main_code = "\n".join(main_body)
    
    driver_main = f"""
int main() {{
{main_code}
    return 0;
}}
"""

    return driver_helpers + "\n" + driver_main

def merge_and_write(user_code: str, driver_code: str, target_filepath: str) -> None:
    headers = []
    if "<vector>" not in user_code:
        headers.append("#include <vector>")
    if "<queue>" not in user_code:
        headers.append("#include <queue>")
    if "<string>" not in user_code:
        headers.append("#include <string>")
    if "<iostream>" not in user_code:
        headers.append("#include <iostream>")
        
    headers_str = "\n".join(headers)
    full_program = f"{headers_str}\n{user_code}\n\n{driver_code}"
    
    with open(target_filepath, 'w', encoding='utf-8') as f:
        f.write(full_program)
