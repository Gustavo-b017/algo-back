# services/search_service.py
"""
Search Service
------------------------------------------------------------------------------
Cliente HTTP resiliente para o catálogo externo:
- Usa requests.Session com pool e retry/backoff.
- Padroniza timeouts (DEFAULT_TIMEOUT) e cabeçalhos.
- Implementa cache em memória (12h) para recursos “lentos”/estáveis:
  montadoras, famílias e grupos (últimos níveis).
- Exposição de métodos de busca (query/sumário) com contratos simples.

Observações de manutenção:
- As funções retornam `dict` (JSON) ou `None` em falhas, mantendo compatibilidade
  com o restante do projeto.
- Em caso de 401, `_post_request` tenta renovar o token 1x (se `AuthService` estiver
  disponível) e repete a chamada — comportamento útil em cenários de expiração.
- DEFAULT_TIMEOUT foi elevado para 30s por demanda do projeto (variável de ambiente
  REQUEST_TIMEOUT_SECONDS pode ajustar).
------------------------------------------------------------------------------
"""

import os
import time
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

# Cache longo (12h) para listas “catálogo” que mudam pouco
TTL_LONGO = 12 * 60 * 60  # 12h
# Timeout padrão para todas as requisições do serviço (ajustável por ENV)
DEFAULT_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "30.0"))


class SearchService:
    """Camada de integração com a API de catálogo (superbusca)."""

    def __init__(self):
        # Base do catálogo; pode variar por ambiente (stg/prod)
        self.base_url = os.getenv(
            "API_BASE_URL",
            "https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao",
        )

        # Session com pooling e retry/backoff (inclui POST).
        # Mantém conexões abertas e lida com instabilidades transitórias (429/5xx).
        self.session = requests.Session()
        retry = Retry(
            total=2,                 # tentativas totais por request
            connect=2,               # tentativas ao estabelecer conexão
            read=2,                  # tentativas de leitura de resposta
            status=2,                # tentativas com base em códigos HTTP
            backoff_factor=0.6,      # atraso exponencial entre tentativas
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "POST"]),
            raise_on_status=False,   # não lança automaticamente em status não-2xx
        )
        adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({"Accept": "application/json"})

        # Caches locais (em memória) + controle de expiração
        self._cached_montadoras = None
        self._montadoras_expiry = 0

        self._cached_familias = None
        self._familias_expiry = 0

        self._cached_grupos_produtos = None
        self._grupos_produtos_expiry = 0

    # ---------- infra ----------
    def _get_headers(self, token: str) -> dict:
        """Cabeçalhos padrão (inclui Bearer)."""
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _post_request(
        self,
        url: str,
        token: str,
        payload: dict | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        """POST resiliente com tratamento de erros comuns.

        Comportamento:
        - Valida presença do token.
        - Executa POST com Session (pool/retry).
        - Se 401, tenta renovar token via AuthService uma única vez e repete.
        - Retorna JSON (dict) quando possível; {} em 204/corpo vazio; None em falhas.

        Observação:
        - Mantém compatibilidade com o restante do projeto retornando None em erros,
          ao invés de lançar exceções.
        """
        if not token:
            log.error("SEARCH: token ausente para %s", url)
            return None

        try:
            res = self.session.post(
                url,
                headers=self._get_headers(token),
                json=payload or {},
                timeout=timeout,
            )

            # Token expirado/ruim: tenta renovar 1x via AuthService (se disponível) e repetir
            if res.status_code == 401:
                log.warning("SEARCH 401 em %s. Tentando renovar token e repetir...", url)
                try:
                    from services.auth_service import auth_service_instance
                    novo_token = auth_service_instance.obter_token()
                    if novo_token and novo_token != token:
                        res = self.session.post(
                            url,
                            headers=self._get_headers(novo_token),
                            json=payload or {},
                            timeout=timeout,
                        )
                except Exception as e:
                    log.error("SEARCH: falha ao renovar token automaticamente: %s", e)

            # Após possível retry, valida status novamente
            if res.status_code == 401:
                log.error("SEARCH 401 persistente em %s", url)
                return None

            res.raise_for_status()

            if not res.content:
                # 204 No Content ou corpo realmente vazio
                return {}

            return res.json()

        except requests.exceptions.Timeout:
            log.error("SEARCH timeout (>%ss) em %s", timeout, url)
            return None
        except ValueError:
            # Falha ao decodificar JSON
            log.error(
                "SEARCH JSON inválido em %s. Body: %s",
                url,
                res.text[:200] if "res" in locals() else "",
            )
            return None
        except requests.exceptions.RequestException as e:
            # Erros de transporte, DNS, SSL, etc.
            log.error("SEARCH erro em %s: %s", url, e)
            return None

    # ---------- endpoints ----------
    def buscar_produtos(
        self,
        token,
        filtro_produto=None,
        filtro_veiculo=None,
        pagina=0,
        itens_por_pagina=50,
    ):
        """Busca produtos com base em filtros de produto e/ou veículo."""
        url = f"{self.base_url}/catalogo/produtos/query"
        payload = {
            "produtoFiltro": filtro_produto or {},
            "veiculoFiltro": filtro_veiculo or {},
            "pagina": pagina,
            "itensPorPagina": itens_por_pagina,  # padronizado
        }
        return self._post_request(url, token, payload)

    def buscar_sugestoes_sumario(self, token, termo_busca, pagina=0, itens_por_pagina=10):
        """Busca sugestões (v2/sumário). Usualmente retorna `score` quando há termo."""
        url = f"{self.base_url}/catalogo/v2/produtos/query/sumario"
        payload = {
            "superbusca": termo_busca or "",
            "pagina": pagina,
            "itensPorPagina": itens_por_pagina,  # padronizado
        }
        return self._post_request(url, token, payload)

    def buscar_montadoras(self, token):
        """Lista de montadoras (cache 12h para reduzir latência/custos)."""
        agora = time.time()
        if self._cached_montadoras and agora < self._montadoras_expiry:
            return self._cached_montadoras

        url = f"{self.base_url}/veiculo/montadoras/query"
        payload = {"pagina": 0, "itensPorPagina": 500}  # corrigido
        resposta = self._post_request(url, token, payload)

        if resposta:
            self._cached_montadoras = resposta
            self._montadoras_expiry = agora + TTL_LONGO

        return self._cached_montadoras

    def buscar_familias(self, token):
        """Lista de famílias (cache 12h)."""
        agora = time.time()
        if self._cached_familias and agora < self._familias_expiry:
            return self._cached_familias

        url = f"{self.base_url}/produto/familias/query"
        payload = {"pagina": 0, "itensPorPagina": 1000}  # corrigido
        resposta = self._post_request(url, token, payload)

        if resposta:
            self._cached_familias = resposta
            self._familias_expiry = agora + TTL_LONGO

        return self._cached_familias

    def buscar_grupos_produtos(self, token):
        """Lista de grupos (últimos níveis) (cache 12h)."""
        agora = time.time()
        if self._cached_grupos_produtos and agora < self._grupos_produtos_expiry:
            return self._cached_grupos_produtos

        url = f"{self.base_url}/produto/ultimos-niveis/query"
        payload = {"pagina": 0, "itensPorPagina": 1000}  # corrigido
        resposta = self._post_request(url, token, payload)

        if resposta:
            self._cached_grupos_produtos = resposta
            self._grupos_produtos_expiry = agora + TTL_LONGO

        return self._cached_grupos_produtos


# instância única (singleton simples por módulo)
search_service_instance = SearchService()


# ---------------------------------------------------------------------------
# ATENÇÃO: A função abaixo está FORA da classe, mas recebe `self` como parâmetro.
# Isso sugere que originalmente deveria ser um método de `SearchService`.
# Mantida como está para NÃO alterar a lógica/assinatura do seu projeto.
# Se for utilizar, chame com a instância explicitamente, por ex.:
#   buscar_produtos_filhos(search_service_instance, token, ...)
# (Caso queira corrigir futuramente, mova o corpo para dentro da classe.)
# ---------------------------------------------------------------------------
def buscar_produtos_filhos(self, token, filtro_produto=None, filtro_veiculo=None, pagina=0, itens_por_pagina=50):
    """Busca produtos (v2) filhos, refinando por último nível etc.

    Nota: função de módulo que espera `self` (instância de SearchService) como primeiro arg.
    """
    url = f"{self.base_url}/catalogo/v2/produtos-filhos/query"
    payload = {
        "produtoFiltro": filtro_produto or {},
        "veiculoFiltro": filtro_veiculo or {},
        "pagina": pagina,
        "itensPorPagina": itens_por_pagina
    }
    return self._post_request(url, token, payload)
