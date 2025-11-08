# utils/security.py
"""
Utilitários de Segurança
-------------------------------------------------------------------------------
Escopo:
- Hash/validação de senhas (Werkzeug, pbkdf2:sha256).
- Emissão e validação de JWT (PyJWT) para autenticação stateless.

Boas práticas (para operação/DevOps):
- Em produção, definir SECRET_KEY via variável de ambiente e rotacioná-la
  periodicamente. A rotação invalida tokens antigos.
- Ajustar o tempo de expiração conforme o risco do domínio (menor em áreas
  sensíveis). Aqui o padrão é 12h (configurável no emissor).
- Opcionalmente, incluir claims como `iss` (issuer) e `aud` (audience) e validar
  esses campos no `decode_token`.
- Evitar logar tokens completos; preferir apenas prefixos/sufixos para debug.
-------------------------------------------------------------------------------
"""

from datetime import datetime, timedelta, timezone
import os
import jwt
from werkzeug.security import generate_password_hash, check_password_hash

# use uma ENV em produção (NÃO versionar segredo real)
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-prod")
ALGORITHM = "HS256"


# ---- Senhas ---------------------------------------------------------------
def hash_password(password: str) -> str:
    """Gera hash seguro (pbkdf2:sha256, com salt aleatório de 16 bytes)."""
    return generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)


def verify_password(password: str, password_hash: str) -> bool:
    """Confere senha em texto-clar o vs hash armazenado (tempo-constante)."""
    return check_password_hash(password_hash, password)


# ---- JWT ------------------------------------------------------------------
def create_access_token(user_id: int, hours: int = 12) -> str:
    """Cria um JWT com subject=user_id e expiração em `hours`.

    Claims:
        sub: identificador do usuário (string, por compatibilidade PyJWT)
        iat: emitido em (UTC)
        exp: expira em (UTC)

    Observação:
        - Retorna uma string codificada (header.payload.signature).
        - `hours` é o TTL do token; regule conforme necessidades do negócio.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),      # como string por compatibilidade com PyJWT
        "iat": now,
        "exp": now + timedelta(hours=hours),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decodifica/valida um JWT e retorna o payload (claims) como dict.

    Levanta:
        ValueError: com mensagem amigável para token expirado ou inválido.

    Observação:
        - Aqui validamos apenas assinatura/expiração. Caso use `iss`/`aud`,
          acrescentar parâmetros no `jwt.decode(..., issuer=..., audience=...)`.
    """
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return data
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expirado.")
    except jwt.InvalidTokenError:
        raise ValueError("Token inválido.")
