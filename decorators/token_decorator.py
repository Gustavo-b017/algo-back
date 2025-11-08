# decorators/token_decorator.py
"""
Decorator de injeção de token de serviço
-------------------------------------------------------------------------------
Escopo:
- Garante que a view executará com um token de acesso válido para a API externa.
- O token é obtido via `auth_service_instance.obter_token()` (client credentials).
- Em caso de falha (token None), retorna 500 com JSON padronizado.

Observações de uso:
- Utilize este decorator em rotas que precisam autenticar-se como "serviço"
  perante o provedor externo (não confundir com JWT de usuário).
- O token é injetado na requisição como `request.token` para consumo na view.
-------------------------------------------------------------------------------
"""

from functools import wraps
from flask import request, jsonify
from services.auth_service import auth_service_instance


def require_token(func):
    """Decorador que injeta um token válido na requisição.

    Comportamento:
        - Obtém um access_token junto ao AuthService.
        - Se indisponível, responde 500 (falha na autenticação externa).
        - Se OK, injeta `request.token` e chama a função decorada.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        token = auth_service_instance.obter_token()
        if not token:
            # Falha ao autenticar com o provedor externo (SSO/OAuth etc.)
            return jsonify({"success": False, "error": "Falha na autenticação com a API externa"}), 500

        # Torna o token acessível na view e serviços chamados por ela
        request.token = token
        return func(*args, **kwargs)

    return wrapper
