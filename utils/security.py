# utils/security.py
import os, datetime, jwt
from passlib.context import CryptContext
from flask import current_app

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
_ALG = "HS256"

def _get_secret():
    # pega da config do Flask se existir; senão do env; fallback fixo
    return (getattr(current_app, "config", {}) or {}).get("JWT_SECRET") or os.getenv("JWT_SECRET", "dev-secret")

def hash_password(raw: str) -> str:
    return _pwd.hash(raw)

def verify_password(raw: str, hashed: str) -> bool:
    return _pwd.verify(raw, hashed)

def create_access_token(user_id: int, minutes: int = 60*24*7) -> str:
    now = datetime.datetime.utcnow()
    payload = {
        "sub": str(user_id),                 # <<< AQUI: string!
        "iat": now,
        "exp": now + datetime.timedelta(minutes=minutes),
    }
    return jwt.encode(payload, _get_secret(), algorithm=_ALG)

def decode_token(token: str) -> dict:
    return jwt.decode(token, _get_secret(), algorithms=[_ALG])
