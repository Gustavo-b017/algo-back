# services/auth_service.py

import time
import requests

class AuthService:
    def __init__(self):
        self._cached_token = None
        self._token_expiry = 0
        self.session = requests.Session()

    def obter_token(self):
        """Obtém um token de acesso, usando a cache se for válido."""
        agora = time.time()
        if self._cached_token and agora < self._token_expiry:
            return self._cached_token

        url_token = "https://sso-catalogo.redeancora.com.br/connect/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": "65tvh6rvn4d7uer3hqqm2p8k2pvnm5wx",
            "client_secret": "9Gt2dBRFTUgunSeRPqEFxwNgAfjNUPLP5EBvXKCn"
        }
        
        try:
            res = self.session.post(url_token, headers=headers, data=data)
            res.raise_for_status()
            
            self._cached_token = res.json().get("access_token")
            self._token_expiry = agora + 290  # Cache por pouco menos de 5 minutos
            print("--- NOVO TOKEN OBTIDO ---") # Para depuração
            return self._cached_token

        except requests.exceptions.RequestException as e:
            print(f"Erro ao obter token: {e}")
            return None

# Instância única para ser usada em toda a aplicação
auth_service_instance = AuthService()