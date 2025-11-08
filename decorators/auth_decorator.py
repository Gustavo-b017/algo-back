# decorators/auth_decorator.py
"""
Decorators de autenticação/autorização
-------------------------------------------------------------------------------
login_required:
    - Exige JWT no header Authorization (formato "Bearer <token>").
    - Decodifica/valida o token e injeta o usuário autenticado em
      `request.current_user` para uso nas rotas protegidas.
    - Responde 204 para preflight CORS (OPTIONS) sem exigir token.
    - Em falhas (token ausente/inválido/expirado, usuário inexistente),
      retorna JSON padronizado {"success": False, "error": "..."} com 401.

Boas práticas:
    - Em produção, rotacionar SECRET_KEY periodicamente (ver utils.security).
    - Evitar logar tokens em claro.
    - Se necessário, estender para validar `iss`/`aud` em decode_token.

Contrato:
    - Rotas que utilizam @login_required acessam o usuário autenticado via:
        `u = request.current_user`
-------------------------------------------------------------------------------
"""

from functools import wraps
from flask import request, jsonify
from database.__init__ import db
from database.models import Usuario
from utils.security import decode_token


def _unauth(msg="Não autorizado."):
    """Retorna resposta JSON de não autorizado (401) com mensagem padronizada."""
    return jsonify({"success": False, "error": msg}), 401


def _extract_bearer_token() -> str | None:
    """Extrai o token do header Authorization (esquema Bearer).

    Retorna:
        str | None: token sem o prefixo "Bearer ", ou None se ausente.
    """
    # Ex.: Authorization: Bearer <token>
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip() or None
    # Fallbacks opcionais (descomentá-los se desejar aceitar em query/cookie):
    # token = request.args.get("access_token") or request.cookies.get("access_token")
    # return token
    return None


def login_required(fn):
    """Decorator para proteger rotas com JWT.

    Comportamento:
        - OPTIONS (preflight CORS): retorna 204 de imediato (sem exigir token).
        - Demais métodos: exige token Bearer; valida e injeta `request.current_user`.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Libera preflight CORS sem exigir token
        if request.method == "OPTIONS":
            return "", 204

        token = _extract_bearer_token()
        if not token:
            return _unauth("Token ausente.")

        try:
            payload = decode_token(token)
            sub = payload.get("sub")
            try:
                user_id = int(sub)
            except (TypeError, ValueError):
                return _unauth("Token inválido (sub ausente).")

            # Busca o usuário (compatível com SQLAlchemy 1.x/2.x)
            user = db.session.get(Usuario, user_id) or db.session.query(Usuario).get(user_id)
            if not user:
                return _unauth("Usuário não encontrado.")

            # Injeta usuário autenticado para consumo na view
            request.current_user = user

        except ValueError as e:
            # decode_token lança ValueError com mensagens amigáveis
            return _unauth(str(e))
        except Exception:
            # Qualquer outra falha é tratada como token inválido
            return _unauth("Token inválido.")

        return fn(*args, **kwargs)

    return wrapper
