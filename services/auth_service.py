"""Auth Service
------------------------------------------------------------------------------
Responsável por obter e cachear o token de acesso (client_credentials) junto ao
provedor de autenticação externo, com:
- Cache em memória até próximo da expiração (min_ttl_seconds).
- Retentativas (retry/backoff) e pool de conexões HTTP (requests.Session).
- Carregamento opcional de variáveis do .env quando importado fora do app.py.

Variáveis de ambiente esperadas:
- AUTH_TOKEN_URL        (obrigatória)
- AUTH_CLIENT_ID        (obrigatória)
- AUTH_CLIENT_SECRET    (obrigatória)
- REQUEST_TIMEOUT_SECONDS (opcional; padrão 10s)

Padrões de log:
- Mensagens informativas ao renovar token.
- Erros detalhados para facilitar troubleshooting em produção/homolog.
------------------------------------------------------------------------------
"""

import os
import time
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# tenta carregar .env caso este módulo seja importado fora do app.py
try:
    from dotenv import load_dotenv

    if not (
        os.getenv("AUTH_TOKEN_URL")
        and os.getenv("AUTH_CLIENT_ID")
        and os.getenv("AUTH_CLIENT_SECRET")
    ):
        # carrega .env do CWD se existir; não sobrescreve valores já definidos
        load_dotenv(override=False)
except Exception:
    # Falhas aqui não devem impedir a aplicação; apenas seguimos adiante.
    pass

log = logging.getLogger(__name__)


class AuthService:
    """Serviço de autenticação baseado em client credentials.

    Mantém um cache simples em memória para o access_token, renovando-o quando
    estiver próximo de expirar (janela definida por min_ttl_seconds).
    """

    def __init__(self):
        # cache do token
        self._cached_token = None
        self._token_expiry = 0  # epoch (segundos). Usado para decidir renovação.

        def _env(
            name: str, default: str | None = None, required: bool = False
        ) -> str | None:
            """Obtém variável de ambiente com validação opcional.

            Args:
                name: Nome da ENV.
                default: Valor padrão caso não exista.
                required: Se True, lança erro se a ENV não existir.

            Returns:
                Valor da ENV (ou default).
            """
            val = os.getenv(name, default)
            if required and not val:
                raise RuntimeError(f"ENV obrigatória ausente: {name}")
            return val

        # configs vindas do .env
        self.token_url = _env("AUTH_TOKEN_URL", required=True)
        self.client_id = _env("AUTH_CLIENT_ID", required=True)
        self.client_secret = _env("AUTH_CLIENT_SECRET", required=True)
        self.timeout = float(_env("REQUEST_TIMEOUT_SECONDS", "10"))

        # Session com pool + retry/backoff (robustez contra flutuações transitórias)
        self.session = requests.Session()
        retry = Retry(
            total=2,                 # máx. de tentativas por requisição (inclui backoff)
            connect=2,               # retentativas para falhas de conexão
            read=2,                  # retentativas para falhas de leitura
            status=2,                # retentativas com base em códigos de status
            backoff_factor=0.6,      # tempo base de espera exponencial entre tentativas
            status_forcelist=(429, 500, 502, 503, 504),  # erros transitórios comuns
            allowed_methods=frozenset(["GET", "POST"]),
            raise_on_status=False,   # não lançar exceção automática em status HTTP
        )
        # Pool conservador; ajuste conforme volume/concorrência do seu ambiente
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({"Accept": "application/json"})

    def obter_token(self, min_ttl_seconds: int = 30) -> str | None:
        """Obtém e cacheia o token de acesso (Bearer).

        Estratégia:
        - Se há token válido no cache e ainda resta mais que `min_ttl_seconds`,
          retorna o cache.
        - Caso contrário, solicita novo token ao servidor (grant_type=client_credentials).
        - Armazena o token em cache e calcula o instante de expiração localmente,
          deduzindo a janela de segurança `min_ttl_seconds`.

        Args:
            min_ttl_seconds: Janela de segurança para evitar expirar "no fio".
                             Ao renovar, considera expires_in - min_ttl_seconds.

        Returns:
            str | None: Token de acesso (sem o prefixo "Bearer "), ou None se falhar.
        """
        agora = time.time()
        if self._cached_token and (agora + min_ttl_seconds) < self._token_expiry:
            # Cache válido: retorna sem ir ao servidor
            return self._cached_token

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            res = self.session.post(
                self.token_url, headers=headers, data=data, timeout=self.timeout
            )
            if res.status_code == 401:
                # Credenciais inválidas ou client não autorizado no auth server
                log.error("AUTH 401 ao obter token (credenciais inválidas?)")
                return None

            # Para outros códigos não 2xx, raise_for_status delega ao bloco de exceção
            res.raise_for_status()

            payload = res.json()
            token = payload.get("access_token")
            if not token:
                # Evita registrar payload completo (pode conter dados sensíveis).
                log.error("AUTH: resposta sem access_token: %s", str(payload)[:200])
                return None

            # Caso o servidor não informe expires_in, usa fallback de 300s
            expires_in = int(payload.get("expires_in", 300))
            self._cached_token = token
            # Armazena o instante em que devemos renovar (janela de segurança aplicada)
            self._token_expiry = agora + max(0, expires_in - min_ttl_seconds)

            log.info("AUTH: novo token obtido (expira em ~%ss)", expires_in)
            return self._cached_token

        except requests.exceptions.Timeout:
            log.error("AUTH timeout ao obter token (>%ss).", self.timeout)
            return None
        except requests.exceptions.RequestException as e:
            # Erros de rede, SSL, proxies, DNS, etc.
            log.error("AUTH erro ao obter token: %s", e)
            return None
        except ValueError:
            # JSON inválido ou corpo inesperado
            log.error(
                "AUTH resposta inválida (JSON decode error). Body: %s",
                res.text[:200] if "res" in locals() else "",
            )
            return None


# Instância única (singleton simples por módulo)
auth_service_instance = AuthService()
