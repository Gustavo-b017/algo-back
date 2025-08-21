# decorators/token_decorator.py

from functools import wraps
from flask import request, jsonify
from services.auth_service import auth_service_instance

def require_token(func):
    """Decorador que injeta um token válido na requisição."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        token = auth_service_instance.obter_token()
        if not token:
            return jsonify({"success": False, "error": "Falha na autenticação com a API externa"}), 500
        
        request.token = token
        return func(*args, **kwargs)
    return wrapper