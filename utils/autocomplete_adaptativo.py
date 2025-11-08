# utils/autocomplete_adaptativo.py
"""
Motor de Autocomplete Adaptativo
------------------------------------------------------------------------------
Objetivo
- Oferecer sugestões de termos (nome, marca, código) a partir de um prefixo.
- Aprender dinamicamente com os resultados consultados na API externa
  (superbusca), alimentando uma estrutura Trie em memória.

Componentes
- AutocompleteTrieNode / AutocompleteTrie: estrutura de dados para busca por prefixo.
- AutocompleteAdaptativo: coordena a Trie, um conjunto de substrings e
  a coleta em tempo real na API externa.

Dependências
- python-Levenshtein (função distance) para medir similaridade entre prefixos.
- requests para consumo da API externa.
- utils.preprocess.tratar_dados para normalizar o retorno da API no formato interno.

Observações
- Sem persistência: tudo reside em memória do processo.
- A URL/headers da superbusca estão definidos aqui para manter o comportamento
  existente (não acoplamos ao SearchService).
------------------------------------------------------------------------------
"""

from collections import deque
from Levenshtein import distance as levenshtein_distance
import requests
from .preprocess import tratar_dados  # Importamos a função de pré-processamento


class AutocompleteTrieNode:
    """Nó da Trie de autocomplete.

    Atributos:
        children (dict): Mapa char -> AutocompleteTrieNode.
        is_end_of_word (bool): Indica término de um termo inserido.
        entries (list[str]): Lista de termos completos que terminam neste nó.
                             Limitado a 8 para proteger consumo de memória.
    """

    def __init__(self):
        self.children = {}
        self.is_end_of_word = False
        self.entries = []


class AutocompleteTrie:
    """Trie simples para armazenar e recuperar termos por prefixo.

    Observação:
        Implementação minimalista, suficiente para o caso de uso atual.
        Mantém até 8 entradas por nó-terminal para evitar crescimento excessivo.
    """

    # ... (O código da classe AutocompleteTrie continua exatamente o mesmo) ...
    def __init__(self):
        self.root = AutocompleteTrieNode()

    def insert(self, term):
        """Insere um termo (case-insensitive) na Trie."""
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
        """Insere em lote uma lista/iterável de termos."""
        for termo in termos:
            self.insert(termo)

    def clear(self):
        """Reinicia a Trie (limpa toda a estrutura)."""
        self.root = AutocompleteTrieNode()

    def search_prefix(self, prefix):
        """Retorna os termos que iniciam com o prefixo informado."""
        prefix = prefix.lower()
        node = self.root
        for char in prefix:
            if char not in node.children:
                return []
            node = node.children[char]
        return self._collect_terms(node)

    def _collect_terms(self, node):
        """Coleta recursivamente termos a partir de um nó."""
        results = []

        def dfs(n):
            if n.is_end_of_word:
                results.extend(n.entries)
            for child in n.children.values():
                dfs(child)

        dfs(node)
        return sorted(set(results))[:8]


class AutocompleteAdaptativo:
    """Camada de orquestração do autocomplete.

    Estratégia:
    - Mantém uma Trie para respostas rápidas por prefixo.
    - Mantém também um conjunto de substrings (fallback) para casos em que
      a Trie não possua resultados.
    - Evita reconstruções excessivas via `prefixos_utilizados` (deque) e
      uma checagem de similaridade por distância de Levenshtein.
    - A cada consulta ao vivo (superbusca), normaliza os dados via `tratar_dados`
      e realimenta o motor (Trie + substrings).
    """

    def __init__(self):
        self.trie = AutocompleteTrie()
        self.substrings = set()
        self.prefixos_utilizados = deque(maxlen=4)  # janela de controle anti-rebuild
        self.termo_mais_recente = ""
        self.session = requests.Session()  # Reutiliza conexões HTTP

    # ... (As funções _prefixo_similar e build continuam as mesmas) ...
    def _prefixo_similar(self, novo_prefixo):
        """Evita retrabalho quando o novo prefixo é muito parecido com os últimos."""
        for antigo in self.prefixos_utilizados:
            if levenshtein_distance(novo_prefixo, antigo) <= 2:
                return True
        return False

    def build(self, produtos, novo_prefixo=""):
        """Atualiza a Trie e o conjunto de substrings com base em produtos tratados.

        Args:
            produtos (iterable[dict]): Registros normalizados por `tratar_dados`.
            novo_prefixo (str): Prefixo digitado recentemente (opcional).
        """
        termos = set()
        for p in produtos:
            nome = p.get('nome', '').strip().lower()
            codigo = p.get('codigoReferencia', '').strip().lower()
            marca = p.get('marca', '').strip().lower()
            if nome:
                termos.add(nome)
                # também inclui palavras individuais do nome (busca mais granular)
                termos.update(w for w in nome.split() if w)
            if codigo:
                termos.add(codigo)
            if marca:
                termos.add(marca)

        if novo_prefixo:
            # registra o novo prefixo (e controla rebuilds por similaridade)
            if not self._prefixo_similar(novo_prefixo):
                self.prefixos_utilizados.append(novo_prefixo)
                self.termo_mais_recente = novo_prefixo
            # se atingiu a janela, reconstrói a Trie do zero
            if len(self.prefixos_utilizados) >= 4:
                self.trie.clear()
                self.prefixos_utilizados.clear()
                self.prefixos_utilizados.append(self.termo_mais_recente)
                self.trie.build(termos)
            else:
                # caso contrário, apenas incrementa
                for termo in termos:
                    self.trie.insert(termo)

        # mantém também um conjunto de substrings como fallback
        self.substrings.update(termos)

    def search(self, prefix):
        """Consulta por prefixo. Usa Trie; se vazio, cai para substrings."""
        results = self.trie.search_prefix(prefix)
        if not results:
            results = [t for t in self.substrings if prefix in t][:8]
        return results

    # --- NOVA FUNÇÃO COM TODA A LÓGICA ---
    def obter_sugestoes_ao_vivo(self, prefix, token):
        """Busca sugestões na API externa, alimenta o motor e retorna as melhores.

        Fluxo:
            1) Chama a rota de sumário (superbusca) com o prefixo atual.
            2) Adapta o payload para o formato consumido por `tratar_dados`.
            3) Atualiza o motor (Trie + substrings) via `build`.
            4) Retorna a busca padrão do motor (`search`).

        Observações:
            - A sessão HTTP (self.session) melhora latência reutilizando conexões.
            - Não são lançadas exceções: qualquer erro de rede/log é ignorado
              e a função retorna o melhor esforço local.
        """
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
            # Mantemos comportamento silencioso, apenas registrando em console.
            # (Se quiser, troque por logging no futuro.)
            print(f"Erro ao buscar sugestões ao vivo: {e}")

        # Retornamos a busca do nosso motor, que agora está atualizado
        return self.search(prefix)


# Criamos uma instância única para ser usada em toda a aplicação
autocomplete_engine = AutocompleteAdaptativo()
