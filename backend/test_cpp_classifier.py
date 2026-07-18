import sys
from cpp_classifier import classify_tabulation, classify_memoization, classify_tree, classify_linked_list, detect_entry_point

dp_tab_code = """
int fibonacci(int n) {
    int dp[100];
    dp[0] = 0;
    dp[1] = 1;
    for (int i = 2; i <= n; ++i) {
        dp[i] = dp[i - 1] + dp[i - 2];
    }
    return dp[n];
}
"""

dp_memo_code = """
#include <unordered_map>
std::unordered_map<int, int> memo;
int fib(int n) {
    if (memo.count(n)) return memo[n];
    if (n <= 1) return n;
    return memo[n] = fib(n - 1) + fib(n - 2);
}
"""

tree_code = """
struct TreeNode {
    int val;
    TreeNode* left;
    TreeNode* right;
};
"""

list_code = """
struct ListNode {
    int val;
    ListNode* next;
};
"""

def test_all():
    print("=== DP TABULATION CLASSIFICATION ===")
    tab_res = classify_tabulation(dp_tab_code)
    print(tab_res)
    assert tab_res["is_tabulation"] == True
    assert tab_res["table_var_name"] == "dp"
    assert tab_res["dimensions"] == 1
    assert len(tab_res["recurrence_relations"]) > 0

    print("\n=== DP MEMOIZATION CLASSIFICATION ===")
    memo_res = classify_memoization(dp_memo_code)
    print(memo_res)
    assert memo_res["is_memoization"] == True
    assert memo_res["cache_var_name"] == "memo"
    assert len(memo_res["recurrence_relations"]) > 0

    print("\n=== TREE CLASSIFICATION ===")
    tree_res = classify_tree(tree_code)
    print(tree_res)
    assert tree_res["is_tree"] == True
    assert tree_res["node_type_name"] == "TreeNode"
    assert tree_res["left_field"] == "left"
    assert tree_res["right_field"] == "right"

    print("\n=== LINKED LIST CLASSIFICATION ===")
    list_res = classify_linked_list(list_code)
    print(list_res)
    assert list_res["is_linked_list"] == True
    assert list_res["node_type_name"] == "ListNode"
    assert list_res["next_field"] == "next"

    print("\n=== ENTRY POINT DETECTION ===")
    entry_res = detect_entry_point(dp_tab_code)
    print(entry_res)
    assert entry_res["name"] == "fibonacci"
    assert len(entry_res["params"]) == 1

    print("\nALL CLASSIFICATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_all()
