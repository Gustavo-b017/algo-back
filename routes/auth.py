# routes/auth.py
from flask import Blueprint, request, jsonify
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from database.__init__ import db
from database.models import Usuario
from utils.security import hash_password, verify_password, create_access_token
from decorators.auth_decorator import login_required

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(force=True, silent=True) or {}
    nome = (data.get("nome") or "").strip()
    email = (data.get("email") or "").strip().lower()
    senha = data.get("senha") or ""

    if not nome or not email or not senha:
        return jsonify({"success": False, "error": "nome, email e senha são obrigatórios."}), 400

    try:
        if db.session.query(Usuario).filter_by(email=email).first():
            return jsonify({"success": False, "error": "Email já cadastrado."}), 409

        user = Usuario(nome=nome, email=email, password_hash=hash_password(senha))
        db.session.add(user)
        db.session.commit()
        return jsonify({"success": True, "user": user.to_public_dict()}), 201

    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "error": "Email já cadastrado."}), 409
    except SQLAlchemyError as ex:
        db.session.rollback()
        # durante o ajuste, devolva a classe do erro para sabermos exatamente a causa
        return jsonify({"success": False, "error": f"Erro de banco de dados: {ex.__class__.__name__}"}), 500

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    senha = data.get("senha") or ""

    user = db.session.query(Usuario).filter_by(email=email).first()
    if not user or not verify_password(senha, user.password_hash):
        return jsonify({"success": False, "error": "Credenciais inválidas."}), 401

    token = create_access_token(user.id)
    return jsonify({"success": True, "token": token, "user": user.to_public_dict()}), 200

@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    return jsonify({"success": True, "user": request.current_user.to_public_dict()}), 200

@auth_bp.route("/me", methods=["PUT"])
@login_required
def update_me():
    data = request.get_json(force=True, silent=True) or {}
    u = request.current_user
    if "nome" in data: u.nome = (data["nome"] or "").strip()
    if "telefone" in data: u.telefone = (data["telefone"] or "").strip()
    if "avatar_url" in data: u.avatar_url = (data["avatar_url"] or "").strip()

    senha_atual = data.get("senha_atual")
    nova_senha = data.get("nova_senha")
    if senha_atual or nova_senha:
        if not (senha_atual and nova_senha):
            return jsonify({"success": False, "error": "Informe senha_atual e nova_senha."}), 400
        if not verify_password(senha_atual, u.password_hash):
            return jsonify({"success": False, "error": "Senha atual incorreta."}), 401
        u.password_hash = hash_password(nova_senha)

    db.session.commit()
    return jsonify({"success": True, "user": u.to_public_dict()}), 200
