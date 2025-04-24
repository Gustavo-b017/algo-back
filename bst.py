
class BSTNode:
    def __init__(self, value):
        self.value = value
        self.left = None
        self.right = None

class BST:
    def __init__(self):
        self.root = None

    def insert(self, value):
        def _insert(root, value):
            if not root:
                return BSTNode(value)
            if value.lower() < root.value.lower():
                root.left = _insert(root.left, value)
            elif value.lower() > root.value.lower():
                root.right = _insert(root.right, value)
            return root
        self.root = _insert(self.root, value)

    def search_prefix(self, prefix):
        matches = []
        prefix = prefix.lower()

        def _search(node):
            if not node:
                return
            if prefix in node.value.lower():
                matches.append(node.value)
            _search(node.left)
            _search(node.right)

        _search(self.root)
        return sorted(matches)[:12]  # limitar a 8 sugestões

    def from_iterable(self, values):
        for val in values:
            self.insert(val)
