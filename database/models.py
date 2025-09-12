# database/models.py

from .__init__ import db


class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return f"<Usuario {self.nome}>"


class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_api_externa = db.Column(db.Integer, nullable=False)
    nome = db.Column(db.String(255), nullable=False)
    codigo_referencia = db.Column(db.String(100), nullable=False)
    url_imagem = db.Column(db.String(255), nullable=True)
    preco_original = db.Column(db.Float, nullable=False)
    preco_final = db.Column(db.Float, nullable=False)
    desconto = db.Column(db.Float, nullable=True)
    marca = db.Column(db.String(100), nullable=False)

    # ADICIONE ESTE MÉTODO
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
        }
