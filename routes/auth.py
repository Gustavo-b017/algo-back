# routes/auth.py
from flask import Blueprint, request, jsonify
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from database.__init__ import db
from database.models import Usuario
from utils.security import hash_password, verify_password, create_access_token
from decorators.auth_decorator import login_required

# =============================================================================
# Módulo de Autenticação
# -----------------------------------------------------------------------------
# Responsável por cadastro, login e perfil do usuário.
# - Persistência: SQLAlchemy (tabela Usuario)
# - Senhas: hash/verify via utils.security
# - Sessão: JWT no header Authorization: Bearer <token>
# Convenção de erro: {"success": False, "error": "<mensagem>"} com status adequado.
# =============================================================================

auth_bp = Blueprint("auth", __name__)

def _json_error(message, status=400):
    """Retorna payload de erro padronizado para a API.

    Args:
        message (str): Mensagem de erro (curta e objetiva).
        status (int): Código HTTP (default 400).

    Returns:
        Response: JSON {"success": False, "error": <message>} + status.
    """
    return jsonify({"success": False, "error": message}), status


@auth_bp.route("/register", methods=["POST"])
def register():
    """Registrar novo usuário.

    Corpo JSON esperado:
        {
          "nome":  "Nome Sobrenome",   # obrigatório
          "email": "email@dominio",    # obrigatório (único, minúsculo)
          "senha": "segredo123"        # obrigatório
        }

    Fluxo:
      1) Valida campos obrigatórios.
      2) Verifica duplicidade por e-mail.
      3) Gera hash da senha (fora do commit para capturar falhas de lib).
      4) Persiste e confirma a transação.

    Respostas:
      201: {"success": True, "user": {...}}
      409: Email já cadastrado.
      400: Campos obrigatórios ausentes.
      500: Falha ao hashear senha / erro de banco.

    Observações de manutenção:
      - db.session.flush() ajuda a revelar IntegrityError antes do commit.
      - Mensagens de erro são propositalmente claras nesta fase (útil em dev).
    """
    data = request.get_json(force=True, silent=True) or {}

    nome  = (data.get("nome")  or "").strip()
    email = (data.get("email") or "").strip().lower()
    senha = data.get("senha") or ""

    if not nome or not email or not senha:
        return _json_error("nome, email e senha são obrigatórios.", 400)

    try:
        # checagem rápida de duplicidade
        if db.session.query(Usuario.id).filter_by(email=email).first():
            return _json_error("Email já cadastrado.", 409)

        # hash fora do commit para capturar erros aqui (ex.: lib ausente)
        try:
            pwd_hash = hash_password(senha)
        except Exception as ex:  # captura qualquer falha de hashing
            return _json_error(f"Falha ao gerar hash da senha: {ex.__class__.__name__}", 500)

        user = Usuario(nome=nome, email=email, password_hash=pwd_hash)
        db.session.add(user)

        # flush força o INSERT e revela IntegrityError/erros de coluna/default antes do commit
        db.session.flush()
        db.session.commit()

        return jsonify({"success": True, "user": user.to_public_dict()}), 201

    except IntegrityError:
        db.session.rollback()
        return _json_error("Email já cadastrado.", 409)

    except SQLAlchemyError as ex:
        db.session.rollback()
        # deixe verboso por enquanto para diagnosticar (depois troque por msg genérica)
        return _json_error(f"Erro de banco de dados: {ex.__class__.__name__}", 500)

    except Exception as ex:
        # captura QUALQUER outra causa (ex.: KeyError, ValueError, libs ausentes)
        db.session.rollback()
        return _json_error(f"Erro inesperado: {ex.__class__.__name__}", 500)


@auth_bp.route("/login", methods=["POST"])
def login():
    """Autenticar usuário e emitir JWT.

    Corpo JSON esperado:
        {
          "email": "email@dominio",   # obrigatório
          "senha": "segredo123"       # obrigatório
        }

    Fluxo:
      1) Valida presença de email e senha.
      2) Busca usuário e confere hash.
      3) Emite JWT via create_access_token(user.id).

    Respostas:
      200: {"success": True, "token": "<jwt>", "user": {...}}
      401: Credenciais inválidas.
      400: Campos obrigatórios ausentes.

    Manutenção:
      - O payload do token (sub = id) é definido em utils.security.
      - Ajustes de claims/expiração devem ser centralizados lá.
    """
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    senha = data.get("senha") or ""

    if not email or not senha:
        return _json_error("email e senha são obrigatórios.", 400)

    user = db.session.query(Usuario).filter_by(email=email).first()
    if not user or not verify_password(senha, user.password_hash):
        return _json_error("Credenciais inválidas.", 401)

    token = create_access_token(user.id)
    return jsonify({"success": True, "token": token, "user": user.to_public_dict()}), 200


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    """Retornar dados do usuário autenticado.

    Requer:
      - Header Authorization: Bearer <jwt>

    Respostas:
      200: {"success": True, "user": {...}}

    Observações:
      - O decorador @login_required popula request.current_user.
      - Não há acesso ao password_hash no dicionário público.
    """
    return jsonify({"success": True, "user": request.current_user.to_public_dict()}), 200


@auth_bp.route("/me", methods=["PUT"])
@login_required
def update_me():
    """Atualizar perfil do usuário autenticado.

    Corpo JSON aceito (todos opcionais):
        {
          "nome": "Novo Nome",
          "telefone": "6399...",
          "avatar_url": "https://...",
          "senha_atual": "old",
          "nova_senha": "new"
        }

    Regras de senha:
      - Para trocar senha é obrigatório informar ambos: senha_atual e nova_senha.
      - senha_atual deve validar contra o hash armazenado.

    Respostas:
      200: {"success": True, "user": {...}}
      400: Falta de campos obrigatórios na troca de senha.
      401: Senha atual incorreta.
      500: Falha ao gerar novo hash.

    Manutenção:
      - Qualquer regra extra de perfil deve ser aplicada aqui (ex.: validação de avatar).
    """
    data = request.get_json(force=True, silent=True) or {}
    u = request.current_user

    if "nome" in data:
        u.nome = (data["nome"] or "").strip()
    if "telefone" in data:
        u.telefone = (data["telefone"] or "").strip()
    if "avatar_url" in data:
        u.avatar_url = (data["avatar_url"] or "").strip()

    senha_atual = data.get("senha_atual")
    nova_senha = data.get("nova_senha")
    if senha_atual or nova_senha:
        if not (senha_atual and nova_senha):
            return _json_error("Informe senha_atual e nova_senha.", 400)
        if not verify_password(senha_atual, u.password_hash):
            return _json_error("Senha atual incorreta.", 401)
        try:
            u.password_hash = hash_password(nova_senha)
        except Exception as ex:
            return _json_error(f"Falha ao gerar hash da nova senha: {ex.__class__.__name__}", 500)

    db.session.commit()
    return jsonify({"success": True, "user": u.to_public_dict()}), 200


# -------- rota de diagnóstico opcional (pode remover depois) -----------------
@auth_bp.route("/__debug/ping_db")
def ping_db():
    """Verifica conectividade com o banco (uso temporário para diagnóstico).

    ATENÇÃO (manutenção/segurança):
      - Rota de suporte para ambientes de dev/homolog.
      - Evite deixá-la exposta em produção.
    """
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify({"ok": True})
    except Exception as ex:
        return _json_error(f"DB indisponível: {ex.__class__.__name__}", 500)
