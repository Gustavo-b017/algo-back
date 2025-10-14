# database/models.py

from .__init__ import db


class Usuario(db.Model):
    __tablename__ = "usuario"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)  # antes era unique=True; removi para não travar nomes iguais
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    telefone = db.Column(db.String(20))
    avatar_url = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

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
    id = db.Column(db.Integer, primary_key=True)
    id_api_externa = db.Column(
        db.Integer, nullable=False, unique=True
    )  # Adicionado unique=True para garantir um produto por carrinho
    nome = db.Column(db.String(255), nullable=False)
    codigo_referencia = db.Column(db.String(100), nullable=False)
    url_imagem = db.Column(db.String(255), nullable=True)
    preco_original = db.Column(db.Numeric(10,2), nullable=False)
    preco_final = db.Column(db.Numeric(10,2), nullable=False)
    desconto = db.Column(db.Numeric(10,2), nullable=True)
    marca = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False, default=1)  # <-- NOVA COLUNA
    

    def to_dict(self):
        return {
            "id": self.id,
            "id_api_externa": self.id_api_externa,
            "nome": self.nome,
            "codigo_referencia": self.codigo_referencia,
            "url_imagem": self.url_imagem,
            "preco_original": self.preco_original,
            "preco_final": self.preco_final,
            "desconto": self.desconto,
            "marca": self.marca,
            "quantidade": self.quantidade,  # <-- INCLUIR NO MÉTODO
        }
