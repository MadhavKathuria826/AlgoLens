export interface Template {
  name: string;
  category: string;
  description: string;
  code: string;
}

export const CODE_TEMPLATES: Template[] = [
  {
    name: "Factorial (Recursion)",
    category: "Basic Structures",
    description: "Simple factorial function showing call stacks and recursion visualizer.",
    code: `def factorial(n):
    if n == 0:
        return 1
    return n * factorial(n - 1)

result = factorial(3)`
  },
  {
    name: "Stack Operations",
    category: "Basic Structures",
    description: "Visualizes standard stack (LIFO) operations like push and pop.",
    code: `stack = []
stack.append(10)
stack.append(20)
stack.append(30)
top = stack.pop()`
  },
  {
    name: "Queue Operations",
    category: "Basic Structures",
    description: "Visualizes standard queue (FIFO) operations using collections.deque.",
    code: `from collections import deque
queue = deque()
queue.append(10)
queue.append(20)
queue.append(30)
front = queue.popleft()`
  },
  {
    name: "Min Heap Construction",
    category: "Basic Structures",
    description: "Uses heapq to construct a binary min-heap from an array, mapping array indices to a tree layout.",
    code: `import heapq

h = []
for val in [20, 15, 30, 5, 10]:
    heapq.heappush(h, val)

min_val = heapq.heappop(h)`
  },
  {
    name: "Singly Linked List",
    category: "Basic Structures",
    description: "Creates and traverses a standard singly linked list.",
    code: `class Node:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

class LinkedList:
    def __init__(self):
        self.head = None

    def insert(self, val):
        new_node = Node(val)
        if not self.head:
            self.head = new_node
            return
        curr = self.head
        while curr.next:
            curr = curr.next
        curr.next = new_node

ll = LinkedList()
for val in [10, 20, 30]:
    ll.insert(val)`
  },
  {
    name: "Binary Search Tree",
    category: "Trees",
    description: "Simple BST insertion creating a classic left-right tree visualization.",
    code: `class Node:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

class BST:
    def __init__(self):
        self.root = None

    def insert(self, val):
        self.root = self._insert(self.root, val)

    def _insert(self, node, val):
        if not node:
            return Node(val)
        if val < node.val:
            node.left = self._insert(node.left, val)
        else:
            node.right = self._insert(node.right, val)
        return node

tree = BST()
for val in [20, 10, 30, 5, 15]:
    tree.insert(val)`
  },
  {
    name: "AVL Tree (LL Rotation)",
    category: "Trees",
    description: "Demonstrates Left-Left unbalance and the resulting Right rotation.",
    code: `class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right
        self.height = 1

class AVLTree:
    def __init__(self):
        self.root = None

    def get_height(self, node):
        if not node:
            return 0
        return node.height

    def get_balance(self, node):
        if not node:
            return 0
        return self.get_height(node.left) - self.get_height(node.right)

    def right_rotate(self, y):
        x = y.left
        T2 = x.right
        x.right = y
        y.left = T2
        y.height = 1 + max(self.get_height(y.left), self.get_height(y.right))
        x.height = 1 + max(self.get_height(x.left), self.get_height(x.right))
        return x

    def insert(self, val):
        self.root = self._insert(self.root, val)

    def _insert(self, node, val):
        if not node:
            return TreeNode(val)
        if val < node.val:
            node.left = self._insert(node.left, val)
        else:
            node.right = self._insert(node.right, val)

        node.height = 1 + max(self.get_height(node.left), self.get_height(node.right))
        balance = self.get_balance(node)

        # Left Left Rotation
        if balance > 1 and val < node.left.val:
            return self.right_rotate(node)

        return node

tree = AVLTree()
for v in [30, 20, 10]:
    tree.insert(v)`
  },
  {
    name: "AVL Tree (All Rotations & Deletion)",
    category: "Trees",
    description: "Full self-balancing BST with support for LL/RR/LR/RL rotations and tree deletion.",
    code: `class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right
        self.height = 1

class AVLTree:
    def __init__(self):
        self.root = None

    def get_height(self, node):
        if not node: return 0
        return node.height

    def get_balance(self, node):
        if not node: return 0
        return self.get_height(node.left) - self.get_height(node.right)

    def right_rotate(self, y):
        x = y.left
        T2 = x.right
        x.right = y
        y.left = T2
        y.height = 1 + max(self.get_height(y.left), self.get_height(y.right))
        x.height = 1 + max(self.get_height(x.left), self.get_height(x.right))
        return x

    def left_rotate(self, x):
        y = x.right
        T2 = y.left
        y.left = x
        x.right = T2
        x.height = 1 + max(self.get_height(x.left), self.get_height(x.right))
        y.height = 1 + max(self.get_height(y.left), self.get_height(y.right))
        return y

    def insert(self, val):
        self.root = self._insert(self.root, val)

    def _insert(self, node, val):
        if not node: return TreeNode(val)
        if val < node.val:
            node.left = self._insert(node.left, val)
        else:
            node.right = self._insert(node.right, val)

        node.height = 1 + max(self.get_height(node.left), self.get_height(node.right))
        balance = self.get_balance(node)

        if balance > 1 and val < node.left.val:
            return self.right_rotate(node)
        if balance < -1 and val > node.right.val:
            return self.left_rotate(node)
        if balance > 1 and val > node.left.val:
            node.left = self.left_rotate(node.left)
            return self.right_rotate(node)
        if balance < -1 and val < node.right.val:
            node.right = self.right_rotate(node.right)
            return self.left_rotate(node)
        return node

    def delete(self, key):
        self.root = self._delete(self.root, key)

    def _delete(self, node, key):
        if not node: return node
        if key < node.val:
            node.left = self._delete(node.left, key)
        elif key > node.val:
            node.right = self._delete(node.right, key)
        else:
            if not node.left: return node.right
            elif not node.right: return node.left
            temp = self._get_min(node.right)
            node.val = temp.val
            node.right = self._delete(node.right, temp.val)

        node.height = 1 + max(self.get_height(node.left), self.get_height(node.right))
        balance = self.get_balance(node)

        if balance > 1 and self.get_balance(node.left) >= 0:
            return self.right_rotate(node)
        if balance > 1 and self.get_balance(node.left) < 0:
            node.left = self.left_rotate(node.left)
            return self.right_rotate(node)
        if balance < -1 and self.get_balance(node.right) <= 0:
            return self.left_rotate(node)
        if balance < -1 and self.get_balance(node.right) > 0:
            node.right = self.right_rotate(node.right)
            return self.left_rotate(node)
        return node

    def _get_min(self, node):
        if not node or not node.left: return node
        return self._get_min(node.left)

tree = AVLTree()
for v in [30, 20, 40, 10, 25]:
    tree.insert(v)
tree.delete(40)`
  },
  {
    name: "Red-Black Tree Insertion",
    category: "Trees",
    description: "Demonstrates node color balance and RBT rules after inserting keys.",
    code: `class TreeNode:
    def __init__(self, val=0, color="RED", left=None, right=None, parent=None):
        self.val = val
        self.color = color  # "RED" or "BLACK"
        self.left = left
        self.right = right
        self.parent = parent

class RedBlackTree:
    def __init__(self):
        self.root = None

    def left_rotate(self, x):
        y = x.right
        x.right = y.left
        if y.left:
            y.left.parent = x
        y.parent = x.parent
        if not x.parent:
            self.root = y
        elif x == x.parent.left:
            x.parent.left = y
        else:
            x.parent.right = y
        y.left = x
        x.parent = y

    def right_rotate(self, y):
        x = y.left
        y.left = x.right
        if x.right:
            x.right.parent = y
        x.parent = y.parent
        if not y.parent:
            self.root = x
        elif y == y.parent.left:
            y.parent.left = x
        else:
            y.parent.right = x
        x.right = y
        y.parent = x

    def insert(self, val):
        new_node = TreeNode(val)
        if not self.root:
            new_node.color = "BLACK"
            self.root = new_node
            return

        curr = self.root
        parent = None
        while curr:
            parent = curr
            if val < curr.val:
                curr = curr.left
            else:
                curr = curr.right

        new_node.parent = parent
        if val < parent.val:
            parent.left = new_node
        else:
            parent.right = new_node

        self.fix_insert(new_node)

    def fix_insert(self, z):
        while z.parent and z.parent.color == "RED":
            gp = z.parent.parent
            if not gp:
                break
            if z.parent == gp.left:
                uncle = gp.right
                if uncle and uncle.color == "RED":
                    z.parent.color = "BLACK"
                    uncle.color = "BLACK"
                    gp.color = "RED"
                    z = gp
                else:
                    if z == z.parent.right:
                        z = z.parent
                        self.left_rotate(z)
                    z.parent.color = "BLACK"
                    z.parent.parent.color = "RED"
                    self.right_rotate(z.parent.parent)
            else:
                uncle = gp.left
                if uncle and uncle.color == "RED":
                    z.parent.color = "BLACK"
                    uncle.color = "BLACK"
                    gp.color = "RED"
                    z = gp
                else:
                    if z == z.parent.left:
                        z = z.parent
                        self.right_rotate(z)
                    z.parent.color = "BLACK"
                    z.parent.parent.color = "RED"
                    self.left_rotate(z.parent.parent)
        self.root.color = "BLACK"

tree = RedBlackTree()
for v in [10, 20, 30, 15]:
    tree.insert(v)`
  },
  {
    name: "Fibonacci (1D Tabulation)",
    category: "Dynamic Programming",
    description: "Computes Fibonacci using a bottom-up 1D tabulation array. Renders the DP table mapping grid.",
    code: `def fib(n):
    dp = [0] * (n + 1)
    dp[0] = 0
    if n > 0:
        dp[1] = 1
    for i in range(2, n + 1):
        dp[i] = dp[i-1] + dp[i-2]
    return dp[n]

result = fib(5)`
  },
  {
    name: "Fibonacci (DP Memoization)",
    category: "Dynamic Programming",
    description: "Computes Fibonacci top-down using a recursion cache (memo dict). Renders active logs and cache hits.",
    code: `memo = {}
def fib(n):
    if n in memo:
        return memo[n]
    if n <= 1:
        return n
    memo[n] = fib(n - 1) + fib(n - 2)
    return memo[n]

result = fib(5)`
  },
  {
    name: "Edit Distance (2D Tabulation)",
    category: "Dynamic Programming",
    description: "Computes min edit distance between two strings using a 2D DP matrix. Renders grid cells highlighting source vs target transitions.",
    code: `def min_edit_distance(word1, word2):
    m, n = len(word1), len(word2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
        
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if word1[i-1] == word2[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = 1 + min(
                    dp[i-1][j],    # deletion
                    dp[i][j-1],    # insertion
                    dp[i-1][j-1]   # substitution
                )
    return dp[m][n]

result = min_edit_distance("abc", "yaby")`
  }
];
