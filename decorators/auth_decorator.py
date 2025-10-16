# decorators/auth_decorator.py
from functools import wraps
from flask import request, jsonify
from database.__init__ import db
from database.models import Usuario
from utils.security import decode_token

def _unauth(msg="Não autorizado."):
    return jsonify({"success": False, "error": msg}), 401

def _extract_bearer_token() -> str | None:
    # Authorization: Bearer <token>
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip() or None
    # fallback opcionais (query/cookie), se você quiser habilitar:
    # token = request.args.get("access_token") or request.cookies.get("access_token")
    # return token
    return None

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # libera preflight CORS
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

            # busca usuário
            user = db.session.get(Usuario, user_id) or db.session.query(Usuario).get(user_id)
            if not user:
                return _unauth("Usuário não encontrado.")

            # injeta no request
            request.current_user = user

        except ValueError as e:
            return _unauth(str(e))
        except Exception:
            return _unauth("Token inválido.")

        return fn(*args, **kwargs)
    return wrapper
