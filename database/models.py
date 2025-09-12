from .__init__ import db

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return f'<Usuario {self.nome}>'

class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(255), nullable=False)
    codigo_referencia = db.Column(db.String(100), nullable=False, unique=True)
    url_imagem = db.Column(db.String(255), nullable=True)
    preco_original = db.Column(db.Float, nullable=False)
    preco_final = db.Column(db.Float, nullable=False)
    desconto = db.Column(db.Float, nullable=True)

    def __repr__(self):
        return f'<Produto {self.nome}>'