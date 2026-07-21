from cpp_adapter import build_driver_code

def test_plain_type():
    print("=== Case 1: Plain-type Function (fibonacci) ===")
    entry_info = {
        "name": "fibonacci",
        "return_type": "int",
        "params": [
            {"name": "n", "type": "int"},
            {"name": "label", "type": "std::string"}
        ],
        "is_class": False
    }
    test_case_str = '{"n": 10, "label": "test"}'
    driver = build_driver_code(entry_info, test_case_str)
    print(driver)
    
    # Assertions
    assert "int n = 10;" in driver
    assert 'std::string label = "test";' in driver
    assert "auto _res = fibonacci(n, label);" in driver
    assert "serialize_output(_res);" in driver
    assert driver.count("{") == driver.count("}")

def test_tree_input():
    print("\n=== Case 2: Tree-input Function (invertTree) ===")
    entry_info = {
        "name": "invertTree",
        "return_type": "TreeNode*",
        "params": [
            {"name": "root", "type": "TreeNode*"}
        ],
        "is_class": True,
        "class_name": "Solution"
    }
    test_case_str = 'root = [4, 2, 7, 1, 3, None, 9]'
    driver = build_driver_code(entry_info, test_case_str)
    print(driver)
    
    # Assertions
    assert "std::vector<std::string> _temp_vals_root = {\"4\", \"2\", \"7\", \"1\", \"3\", \"null\", \"9\"};" in driver
    assert "TreeNode* root = deserialize_tree(_temp_vals_root);" in driver
    assert "Solution _sol;" in driver
    assert "auto _res = _sol.invertTree(root);" in driver
    assert "serialize_output(_res);" in driver
    assert driver.count("{") == driver.count("}")

def test_list_input():
    print("\n=== Case 3: Linked-list-input Function (reverseList) ===")
    entry_info = {
        "name": "reverseList",
        "return_type": "ListNode*",
        "params": [
            {"name": "head", "type": "ListNode*"}
        ],
        "is_class": False
    }
    test_case_str = 'head = [1, 2, 3, 4, 5]'
    driver = build_driver_code(entry_info, test_case_str)
    print(driver)
    
    # Assertions
    assert "std::vector<int> _temp_vals_head = {1, 2, 3, 4, 5};" in driver
    assert "ListNode* head = deserialize_list(_temp_vals_head);" in driver
    assert "auto _res = reverseList(head);" in driver
    assert "serialize_output(_res);" in driver
    assert driver.count("{") == driver.count("}")

def test_serialize_overloads_completeness():
    print("\n=== Case 4: Overload Completeness Test ===")
    entry_info = {
        "name": "dummy",
        "return_type": "int",
        "params": [],
        "is_class": False
    }
    driver = build_driver_code(entry_info, "")
    
    required_overloads = [
        "void serialize_output(int",
        "void serialize_output(double",
        "void serialize_output(bool",
        "void serialize_output(const std::string&",
        "void serialize_output(const std::vector<int>&",
        "void serialize_output(const std::vector<std::string>&",
        "void serialize_output(ListNode*",
        "void serialize_output(TreeNode*"
    ]
    
    for overload in required_overloads:
        assert overload in driver, f"Missing required overload: {overload}"
    print("All required overloads are present in the helper block!")

def run_tests():
    test_plain_type()
    test_tree_input()
    test_list_input()
    test_serialize_overloads_completeness()
    print("\nALL ADAPTER DRIVER GENERATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
