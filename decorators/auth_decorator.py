# decorators/auth_decorator.py
from functools import wraps
from flask import request, jsonify
from utils.security import decode_token
from database.models import Usuario
from database.__init__ import db

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"success": False, "error": "Token ausente."}), 401
        token = auth.split(" ", 1)[1].strip()
        try:
            payload = decode_token(token)
            sub = payload.get("sub")
            user_id = int(sub) if sub is not None else None   # <<< AQUI
            if user_id is None:
                return jsonify({"success": False, "error": "Token inválido."}), 401
            user = db.session.get(Usuario, user_id)
            if not user:
                return jsonify({"success": False, "error": "Usuário não encontrado."}), 401
            request.current_user = user
        except Exception:
            return jsonify({"success": False, "error": "Token inválido ou expirado."}), 401
        return fn(*args, **kwargs)
    return wrapper
