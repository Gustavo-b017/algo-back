import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_compress import Compress
from database.__init__ import db
from database.models import Usuario, Produto 
from routes.search import search_bp
from routes.product import product_bp

# Cria a instância da aplicação Flask no nível superior
app = Flask(__name__)

# --- INÍCIO DA NOVA MODIFICAÇÃO ---

# Lógica para construir a URI do banco de dados a partir de variáveis de ambiente separadas
if "MYSQLHOST" in os.environ:
    # Se MYSQLHOST existe, presumimos que estamos no ambiente de produção (Railway)
    host = os.environ.get("MYSQLHOST")
    user = os.environ.get("MYSQLUSER")
    password = os.environ.get("MYSQLPASSWORD")
    database = os.environ.get("MYSQLDATABASE")
    port = os.environ.get("MYSQLPORT")
    
    db_url = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}"
else:
    # Se não, usamos o banco de dados local como fallback
    db_url = 'mysql+mysqlconnector://root@localhost/ancora_teste'

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- FIM DA NOVA MODIFICAÇÃO ---

# Inicialize o objeto db com o app
db.init_app(app)

# Configuramos as extensões
CORS(app)
Compress(app)

# Registamos os nossos Blueprints na aplicação
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