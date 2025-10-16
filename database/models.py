# database/models.py

from .__init__ import db
from sqlalchemy.sql import func
from sqlalchemy import text

class Usuario(db.Model):
    __tablename__ = "usuario"

    id            = db.Column(db.Integer, primary_key=True)
    nome          = db.Column(db.String(80),  nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # opcionais
    telefone   = db.Column(db.String(20),  nullable=True)
    avatar_url = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now())

    # relacionamento (mantido)
    produtos = db.relationship(
        "Produto",
        backref="usuario",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def to_public_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "email": self.email,
            "telefone": self.telefone,
            "avatar_url": self.avatar_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Produto(db.Model):
    __tablename__ = "produto"

    id = db.Column(db.Integer, primary_key=True)

    # item sempre vinculado a um usuário
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False)

    id_api_externa    = db.Column(db.Integer,     nullable=False)
    nome              = db.Column(db.String(255), nullable=False)
    codigo_referencia = db.Column(db.String(100), nullable=False)
    url_imagem        = db.Column(db.String(255), nullable=True)

    preco_original = db.Column(db.Numeric(10, 2), nullable=False)
    preco_final    = db.Column(db.Numeric(10, 2), nullable=False)
    desconto       = db.Column(db.Numeric(10, 2), nullable=True)

    marca       = db.Column(db.String(100), nullable=False)
    quantidade  = db.Column(db.Integer,     nullable=False, server_default=text("1"))  # <- default no DB

    # evita duplicar o mesmo produto no carrinho do mesmo usuário
    __table_args__ = (
        db.UniqueConstraint("usuario_id", "id_api_externa", name="_usuario_produto_uc"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "id_api_externa": self.id_api_externa,
            "nome": self.nome,
            "codigo_referencia": self.codigo_referencia,
            "url_imagem": self.url_imagem,
            "preco_original": float(self.preco_original),
            "preco_final": float(self.preco_final),
            "desconto": float(self.desconto) if self.desconto is not None else 0.0,
            "marca": self.marca,
            "quantidade": self.quantidade,
        }
