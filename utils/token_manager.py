import time
import requests
from functools import wraps
from flask import jsonify, request

_cached_token = None
_token_expiry = 0

def obter_token():
    global _cached_token, _token_expiry
    agora = time.time()
    if _cached_token and agora < _token_expiry:
        return _cached_token

    url_token = "https://sso-catalogo.redeancora.com.br/connect/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": "65tvh6rvn4d7uer3hqqm2p8k2pvnm5wx",
        "client_secret": "9Gt2dBRFTUgunSeRPqEFxwNgAfjNUPLP5EBvXKCn"
    }
    res = requests.post(url_token, headers=headers, data=data)
    if res.status_code == 200:
        _cached_token = res.json().get("access_token")
        _token_expiry = agora + 300  # 5 minutos
        return _cached_token
    return None

def require_token(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        token = obter_token()
        if not token:
            return jsonify({"error": "Token inválido"}), 401
        request.token = token
        return func(*args, **kwargs)
    return wrapper