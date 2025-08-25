# services/search_service.py

import requests
import time

class SearchService:
    def __init__(self):
        self.base_url = "https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao"
        self.session = requests.Session()
        
        # Variáveis de cache para montadoras
        self._cached_montadoras = None
        self._montadoras_expiry = 0
        
        # Variáveis de cache para famílias
        self._cached_familias = None
        self._familias_expiry = 0
        
        # Variáveis de cache para grupos de produtos
        self._cached_grupos_produtos = None
        self._grupos_produtos_expiry = 0

    def _get_headers(self, token):
        """Cria os cabeçalhos padrão para as requisições."""
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def _post_request(self, url, token, payload=None):
        """Função auxiliar para fazer requisições POST e tratar erros comuns."""
        try:
            res = self.session.post(url, headers=self._get_headers(token), json=payload or {})
            res.raise_for_status()  # Lança um erro para status codes 4xx ou 5xx
            return res.json()
        except requests.exceptions.RequestException as e:
            print(f"Erro na comunicação com a API em {url}: {e}")
            return None # Retorna None em caso de falha de comunicação

    # --- Métodos para cada endpoint da API ---

    def buscar_produtos(self, token, filtro_produto=None, filtro_veiculo=None, pagina=0, itens_por_pagina=50):
        """Busca produtos com base em filtros de produto e/ou veículo."""
        url = f"{self.base_url}/catalogo/produtos/query"
        payload = {
            "produtoFiltro": filtro_produto or {},
            "veiculoFiltro": filtro_veiculo or {},
            "pagina": pagina,
            "itensPorPagina": itens_por_pagina
        }
        return self._post_request(url, token, payload)

    def buscar_sugestoes_sumario(self, token, termo_busca, pagina=0, itens_por_pagina=10):
        """Busca sugestões de produtos (superbusca v2 resumida)."""
        url = f"{self.base_url}/catalogo/v2/produtos/query/sumario"
        payload = {"superbusca": termo_busca, "pagina": pagina, "itensPorPagina": itens_por_pagina}
        return self._post_request(url, token, payload)

    def buscar_montadoras(self, token):
        """Busca a lista de todas as montadoras."""
        agora = time.time()
        if self._cached_montadoras and agora < self._montadoras_expiry:
            return self._cached_montadoras

        url = f"{self.base_url}/veiculo/montadoras/query"
        payload = {"pagina": 0, "itensPorPagina": 500}
        resposta = self._post_request(url, token, payload)
        
        if resposta:
            self._cached_montadoras = resposta
            self._montadoras_expiry = agora + (12 * 60 * 60)
        
        return self._cached_montadoras

    def buscar_familias(self, token):
        """Busca a lista de todas as famílias (categorias) de produtos."""
        agora = time.time()
        if self._cached_familias and agora < self._familias_expiry:
            return self._cached_familias

        url = f"{self.base_url}/produto/familias/query"
        payload = {"pagina": 0, "itensPor_pagina": 1000}
        resposta = self._post_request(url, token, payload)
        
        if resposta:
            self._cached_familias = resposta
            self._familias_expiry = agora + (12 * 60 * 60)
            
        return self._cached_familias
        
    def buscar_grupos_produtos(self, token):
        """Busca a lista de grupos de produtos (último nível)."""
        agora = time.time()
        if self._cached_grupos_produtos and agora < self._grupos_produtos_expiry:
            return self._cached_grupos_produtos

        url = f"{self.base_url}/produto/ultimos-niveis/query"
        payload = {"pagina": 0, "itensPor_pagina": 1000}
        resposta = self._post_request(url, token, payload)
        
        if resposta:
            self._cached_grupos_produtos = resposta
            self._grupos_produtos_expiry = agora + (12 * 60 * 60)
            
        return self._cached_grupos_produtos

# Criamos uma instância única do serviço para ser usada em toda a aplicação
search_service_instance = SearchService()