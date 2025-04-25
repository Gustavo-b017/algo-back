import heapq

class BSTNode:
    def __init__(self, value):
        self.value = value.lower()
        self.left = None
        self.right = None

class BST:
    def __init__(self):
        self.root = None

    def insert(self, value):
        value = value.lower()
        def _insert(node, value):
            if not node:
                return BSTNode(value)
            if value < node.value:
                node.left = _insert(node.left, value)
            elif value > node.value:
                node.right = _insert(node.right, value)
            return node
        self.root = _insert(self.root, value)

    def build_balanced(self, values):
        values = sorted(set(v.lower() for v in values))
        def _build(lst):
            if not lst:
                return None
            mid = len(lst) // 2
            node = BSTNode(lst[mid])
            node.left = _build(lst[:mid])
            node.right = _build(lst[mid+1:])
            return node
        self.root = _build(values)

    def search_prefix(self, prefix):
        prefix = prefix.lower()
        heap = []
        def _search(node):
            if not node:
                return
            if node.value.startswith(prefix):
                heapq.heappush(heap, node.value)
                if len(heap) > 8:
                    heapq.heappop(heap)
            _search(node.left)
            _search(node.right)
        _search(self.root)
        return sorted(heap)