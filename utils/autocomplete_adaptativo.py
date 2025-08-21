# utils/autocomplete_adaptativo.py

from collections import deque
from Levenshtein import distance as levenshtein_distance
import requests
from .preprocess import tratar_dados # Importamos a função de pré-processamento

class AutocompleteTrieNode:
    def __init__(self):
        self.children = {}
        self.is_end_of_word = False
        self.entries = []

class AutocompleteTrie:
    # ... (O código da classe AutocompleteTrie continua exatamente o mesmo) ...
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
        self.prefixos_utilizados = deque(maxlen=4)
        self.termo_mais_recente = ""
        self.session = requests.Session() # Criamos uma sessão para reutilizar conexões

    # ... (As funções _prefixo_similar e build continuam as mesmas) ...
    def _prefixo_similar(self, novo_prefixo):
        for antigo in self.prefixos_utilizados:
            if levenshtein_distance(novo_prefixo, antigo) <= 2:
                return True
        return False

    def build(self, produtos, novo_prefixo=""):
        termos = set()
        for p in produtos:
            nome = p.get('nome', '').strip().lower()
            codigo = p.get('codigoReferencia', '').strip().lower()
            marca = p.get('marca', '').strip().lower()
            if nome:
                termos.add(nome)
                termos.update(w for w in nome.split() if w)
            if codigo:
                termos.add(codigo)
            if marca:
                termos.add(marca)

        if novo_prefixo:
            if not self._prefixo_similar(novo_prefixo):
                self.prefixos_utilizados.append(novo_prefixo)
                self.termo_mais_recente = novo_prefixo
            if len(self.prefixos_utilizados) >= 4:
                self.trie.clear()
                self.prefixos_utilizados.clear()
                self.prefixos_utilizados.append(self.termo_mais_recente)
                self.trie.build(termos)
            else:
                for termo in termos:
                    self.trie.insert(termo)
        self.substrings.update(termos)

    def search(self, prefix):
        results = self.trie.search_prefix(prefix)
        if not results:
            results = [t for t in self.substrings if prefix in t][:8]
        return results
    
    # --- NOVA FUNÇÃO COM TODA A LÓGICA ---
    def obter_sugestoes_ao_vivo(self, prefix, token):
        """Busca sugestões na API externa, alimenta o motor e retorna as melhores."""
        
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        url_superbusca = "https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao/catalogo/v2/produtos/query/sumario"
        payload = {"superbusca": prefix, "pagina": 0, "itensPorPagina": 20}

        try:
            res = self.session.post(url_superbusca, headers=headers, json=payload)
            if res.status_code == 200:
                produtos_brutos = res.json().get("pageResult", {}).get("data", [])
                
                # Adaptamos o formato para a função `tratar_dados`
                produtos_para_tratar = [{"data": p} for p in produtos_brutos]
                produtos_tratados = tratar_dados(produtos_para_tratar)
                
                # Alimentamos o motor com os novos dados
                self.build(produtos_tratados, prefix)
        
        except requests.exceptions.RequestException as e:
            print(f"Erro ao buscar sugestões ao vivo: {e}")

        # Retornamos a busca do nosso motor, que agora está atualizado
        return self.search(prefix)
    
# Criamos uma instância única para ser usada em toda a aplicação
autocomplete_engine = AutocompleteAdaptativo()