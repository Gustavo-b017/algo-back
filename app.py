import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_compress import Compress

# Importa a extensão SQLAlchemy
from flask_sqlalchemy import SQLAlchemy

# 1. Importamos os nossos Blueprints de rotas
from routes.search import search_bp
from routes.product import product_bp

# Cria a instância da aplicação Flask no nível superior
app = Flask(__name__)

# Configurações do banco de dados
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root@localhost/ancora_teste'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializa o SQLAlchemy
db = SQLAlchemy(app)

# Define uma classe de modelo (tabela de exemplo)
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return f'<Usuario {self.nome}>'

# 2. Configuramos as extensões
CORS(app)
Compress(app)

# 3. Registamos os nossos Blueprints na aplicação
app.register_blueprint(search_bp)
app.register_blueprint(product_bp)

# Rota principal para verificar se a API está ativa
@app.route("/")
def home():
    return "API ativa. Acesso às rotas de busca e de produtos."

# Ponto de entrada para executar a nossa aplicação
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)