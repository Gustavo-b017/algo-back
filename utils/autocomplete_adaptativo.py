import difflib
from collections import deque

class AutocompleteTrieNode:
    def __init__(self):
        self.children = {}
        self.is_end_of_word = False
        self.entries = []

class AutocompleteTrie:
    def __init__(self):
        self.root = AutocompleteTrieNode()

    def insert(self, term):
        term = term.lower()
        node = self.root
        for char in term:
            if char not in node.children:
                node.children[char] = AutocompleteTrieNode()
            node = node.children[char]
        node.is_end_of_word = True
        if term not in node.entries:
            node.entries.append(term)
            if len(node.entries) > 8:
                node.entries = node.entries[:8]

    def build(self, termos):
        for termo in termos:
            self.insert(termo)

    def clear(self):
        self.root = AutocompleteTrieNode()

    def search_prefix(self, prefix):
        prefix = prefix.lower()
        node = self.root
        for char in prefix:
            if char not in node.children:
                return []
            node = node.children[char]
        return self._collect_terms(node)

    def _collect_terms(self, node):
        results = []

        def dfs(n):
            if n.is_end_of_word:
                results.extend(n.entries)
            for child in n.children.values():
                dfs(child)

        dfs(node)
        return sorted(set(results))[:8]

class AutocompleteAdaptativo:
    def __init__(self):
        self.trie = AutocompleteTrie()
        self.substrings = set()
        self.prefixos_utilizados = deque(maxlen=3)
        self.termo_mais_recente = ""

    def _prefixo_similar(self, novo_prefixo):
        for antigo in self.prefixos_utilizados:
            ratio = difflib.SequenceMatcher(None, novo_prefixo, antigo).ratio()
            if ratio > 0.6:
                return True
        return False

    def build(self, produtos, novo_prefixo=""):
        termos = set()
        for p in produtos:
            nome = p.get('nome', '').strip().lower()
            codigo = p.get('codigoReferencia', '').strip().lower()
            marca = p.get('marca', '').strip().lower()

            # evitar nomes compostos absurdamente repetitivos
            if nome and len(nome.split()) > 1 and nome.count(nome.split()[0]) > 1:
                continue

            if nome:
                termos.add(nome)
                termos.update(nome.split())
            if codigo:
                termos.add(codigo)
            if marca:
                termos.add(marca)

        if novo_prefixo:
            if not self._prefixo_similar(novo_prefixo):
                self.prefixos_utilizados.append(novo_prefixo)
                self.termo_mais_recente = novo_prefixo
            if len(self.prefixos_utilizados) == 3:
                self.trie.clear()
                self.prefixos_utilizados.clear()
                self.prefixos_utilizados.append(self.termo_mais_recente)

        self.trie.build(termos)
        self.substrings.update(termos)

    def search(self, prefix):
        results = self.trie.search_prefix(prefix)
        if not results:
            results = [t for t in self.substrings if prefix in t][:8]
        return results