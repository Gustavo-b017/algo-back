# services/auth_service.py

import os
import time
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)


class AuthService:
    def __init__(self):
        # cache do token
        self._cached_token = None
        self._token_expiry = 0

        # helper para ler envs (obriga as sensíveis)
        def _env(
            name: str, default: str | None = None, required: bool = False
        ) -> str | None:
            val = os.getenv(name, default)
            if required and not val:
                raise RuntimeError(f"ENV obrigatória ausente: {name}")
            return val

        # configs vindas do .env
        self.token_url = _env("AUTH_TOKEN_URL", required=True)
        self.client_id = _env("AUTH_CLIENT_ID", required=True)
        self.client_secret = _env("AUTH_CLIENT_SECRET", required=True)
        self.timeout = float(_env("REQUEST_TIMEOUT_SECONDS", "10"))

        # Session com pool + retry/backoff
        self.session = requests.Session()
        retry = Retry(
            total=2,
            connect=2,
            read=2,
            status=2,
            backoff_factor=0.6,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "POST"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({"Accept": "application/json"})

    def obter_token(self, min_ttl_seconds: int = 30) -> str | None:
        """
        Obtém e cacheia o token.
        - Renova faltando 'min_ttl_seconds' para expirar.
        - Usa 'expires_in' do servidor se disponível; senão, 300s (fallback).
        """
        agora = time.time()
        if self._cached_token and (agora + min_ttl_seconds) < self._token_expiry:
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
                log.error("AUTH 401 ao obter token (credenciais inválidas?)")
                return None

            res.raise_for_status()

            payload = res.json()
            token = payload.get("access_token")
            if not token:
                log.error("AUTH: resposta sem access_token: %s", str(payload)[:200])
                return None

            expires_in = int(payload.get("expires_in", 300))
            self._cached_token = token
            self._token_expiry = agora + max(0, expires_in - min_ttl_seconds)

            log.info("AUTH: novo token obtido (expira em ~%ss)", expires_in)
            return self._cached_token

        except requests.exceptions.Timeout:
            log.error("AUTH timeout ao obter token (>%ss).", self.timeout)
            return None
        except requests.exceptions.RequestException as e:
            log.error("AUTH erro ao obter token: %s", e)
            return None
        except ValueError:
            log.error(
                "AUTH resposta inválida (JSON decode error). Body: %s",
                res.text[:200] if "res" in locals() else "",
            )
            return None


# Instância única
auth_service_instance = AuthService()
