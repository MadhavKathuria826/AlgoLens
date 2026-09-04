"""
AlgoLens Golden Test Corpus (22 Standard Benchmark Categories)
Used for baseline validation between legacy Python AST interpreter and future event-driven runtimes.
"""

GOLDEN_TEST_CASES = {
    "G01_basic_scalars": {
        "category": "Basic scalar variables",
        "code": """
int test() {
    int a = 42;
    double b = 3.14;
    bool c = true;
    std::string d = "algolens";
    return a;
}
""",
        "entry_func": "test",
        "args": []
    },
    "G02_assignments": {
        "category": "Assignments and re-bindings",
        "code": """
int test() {
    int x = 10;
    int y = x;
    x = 20;
    return y;
}
""",
        "entry_func": "test",
        "args": []
    },
    "G03_arithmetic": {
        "category": "Arithmetic operations",
        "code": """
int test() {
    int a = 10;
    int b = 3;
    int c = a + b * 2;
    return c;
}
""",
        "entry_func": "test",
        "args": []
    },
    "G04_integer_overflow": {
        "category": "Integer overflow wrapping (2's complement)",
        "code": """
int test() {
    short max_s = 32767;
    max_s = max_s + 1;
    return max_s;
}
""",
        "entry_func": "test",
        "args": []
    },
    "G05_division_modulo": {
        "category": "Division and modulo semantics (truncate toward zero)",
        "code": """
int test() {
    int d1 = -7 / 2;
    int m1 = -7 % 2;
    return d1 + m1;
}
""",
        "entry_func": "test",
        "args": []
    },
    "G06_nested_scopes": {
        "category": "Nested lexical scopes",
        "code": """
int test() {
    int outer = 1;
    if (outer > 0) {
        int inner = 10;
        outer = outer + inner;
    }
    return outer;
}
""",
        "entry_func": "test",
        "args": []
    },
    "G07_function_calls": {
        "category": "Function calls and parameters",
        "code": """
int add(int x, int y) {
    return x + y;
}
int test() {
    int res = add(5, 7);
    return res;
}
""",
        "entry_func": "test",
        "args": []
    },
    "G08_recursion": {
        "category": "Recursion call stack",
        "code": """
int fib(int n) {
    if (n <= 1) return n;
    return fib(n - 1) + fib(n - 2);
}
int test() {
    return fib(4);
}
""",
        "entry_func": "test",
        "args": []
    },
    "G09_arrays": {
        "category": "Array reads and writes",
        "code": """
int test() {
    int arr[3];
    arr[0] = 10;
    arr[1] = 20;
    arr[2] = arr[0] + arr[1];
    return arr[2];
}
""",
        "entry_func": "test",
        "args": []
    },
    "G10_vector_operations": {
        "category": "std::vector operations",
        "code": """
int test() {
    std::vector<int> nums;
    nums.push_back(100);
    nums.push_back(200);
    int sz = nums.size();
    nums.pop_back();
    return sz;
}
""",
        "entry_func": "test",
        "args": []
    },
    "G11_stack_operations": {
        "category": "Stack LIFO operations",
        "code": """
int test() {
    std::stack<int> st;
    st.push(5);
    st.push(10);
    int top_val = st.top();
    st.pop();
    return top_val;
}
""",
        "entry_func": "test",
        "args": []
    },
    "G12_queue_operations": {
        "category": "Queue FIFO operations",
        "code": """
int test() {
    std::queue<int> q;
    q.push(15);
    q.push(30);
    int front_val = q.front();
    q.pop();
    return front_val;
}
""",
        "entry_func": "test",
        "args": []
    },
    "G13_map_operations": {
        "category": "Map key-value operations",
        "code": """
int test() {
    std::map<std::string, int> m;
    m["alpha"] = 1;
    m["beta"] = 2;
    int val = m["alpha"];
    return val;
}
""",
        "entry_func": "test",
        "args": []
    },
    "G14_linked_lists": {
        "category": "Linked list creation and traversal",
        "code": """
struct ListNode {
    int val;
    ListNode* next;
};
int test() {
    ListNode* n1 = new ListNode;
    n1->val = 10;
    ListNode* n2 = new ListNode;
    n2->val = 20;
    n1->next = n2;
    n2->next = nullptr;
    return n1->next->val;
}
""",
        "entry_func": "test",
        "args": []
    },
    "G15_binary_trees": {
        "category": "Binary tree node allocations",
        "code": """
struct TreeNode {
    int val;
    TreeNode* left;
    TreeNode* right;
};
int test() {
    TreeNode* root = new TreeNode;
    root->val = 100;
    TreeNode* left_child = new TreeNode;
    left_child->val = 50;
    root->left = left_child;
    root->right = nullptr;
    return root->left->val;
}
""",
        "entry_func": "test",
        "args": []
    },
    "G16_pointer_allocation": {
        "category": "Pointer allocations (Heap)",
        "code": """
struct Node {
    int val;
};
int test() {
    Node* ptr = new Node;
    ptr->val = 77;
    return ptr->val;
}
""",
        "entry_func": "test",
        "args": []
    },
    "G17_pointer_aliasing": {
        "category": "Pointer aliasing (Multiple pointers to one object)",
        "code": """
struct Node {
    int val;
};
int test() {
    Node* n1 = new Node;
    n1->val = 5;
    Node* n2 = n1;
    n2->val = 99;
    return n1->val;
}
""",
        "entry_func": "test",
        "args": []
    },
    "G18_reference_behavior": {
        "category": "Reference parameter mutations",
        "code": """
void increment(int &val) {
    val = val + 1;
}
int test() {
    int num = 10;
    increment(num);
    return num;
}
""",
        "entry_func": "test",
        "args": []
    },
    "G19_nested_calls": {
        "category": "Multi-level nested function calls",
        "code": """
int step3(int x) {
    return x * 2;
}
int step2(int x) {
    return step3(x) + 1;
}
int test() {
    return step2(5);
}
""",
        "entry_func": "test",
        "args": []
    },
    "G20_return_values": {
        "category": "Function return values",
        "code": """
int compute() {
    return 999;
}
int test() {
    int res = compute();
    return res;
}
""",
        "entry_func": "test",
        "args": []
    },
    "G21_conditional_branches": {
        "category": "Conditional branches (if/else)",
        "code": """
int test() {
    int val = 15;
    int result = 0;
    if (val > 20) {
        result = 1;
    } else if (val > 10) {
        result = 2;
    } else {
        result = 3;
    }
    return result;
}
""",
        "entry_func": "test",
        "args": []
    },
    "G22_loops": {
        "category": "For and while loops",
        "code": """
int test() {
    int sum = 0;
    for (int i = 1; i <= 3; i = i + 1) {
        sum = sum + i;
    }
    return sum;
}
""",
        "entry_func": "test",
        "args": []
    }
}
