# utils/security.py
from datetime import datetime, timedelta, timezone
import os
import jwt
from werkzeug.security import generate_password_hash, check_password_hash

# use uma ENV em produção
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-prod")
ALGORITHM = "HS256"


# ---- Senhas ---------------------------------------------------------------
def hash_password(password: str) -> str:
    """Gera hash seguro (pbkdf2:sha256)."""
    return generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)

def verify_password(password: str, password_hash: str) -> bool:
    """Confere senha vs hash."""
    return check_password_hash(password_hash, password)


# ---- JWT ------------------------------------------------------------------
def create_access_token(user_id: int, hours: int = 12) -> str:
    """Cria JWT com subject=user_id e expiração (horas)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),      # como string por compatibilidade com PyJWT
        "iat": now,
        "exp": now + timedelta(hours=hours),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    """
    Decodifica JWT e retorna o payload.
    Lança ValueError com mensagem amigável quando inválido/expirado.
    """
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return data
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expirado.")
    except jwt.InvalidTokenError:
        raise ValueError("Token inválido.")
