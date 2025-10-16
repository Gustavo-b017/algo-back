# utils/security.py (exemplo seguro e leve)
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash, check_password_hash
import jwt, os

SECRET = os.getenv("SECRET_KEY", "change-me")
ALGO = "HS256"

def hash_password(p: str) -> str:
    return generate_password_hash(p, method="pbkdf2:sha256", salt_length=16)

def verify_password(p: str, h: str) -> bool:
    return check_password_hash(h, p)

def create_access_token(user_id: int, hours: int = 12) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(hours=hours)}
    return jwt.encode(payload, SECRET, algorithm=ALGO)
