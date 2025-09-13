import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_compress import Compress

# Importe a instância do SQLAlchemy e os modelos da nova pasta
from database.__init__ import db
from database.models import Usuario, Produto 

# 1. Importamos os nossos Blueprints de rotas
from routes.search import search_bp
from routes.product import product_bp

# Cria a instância da aplicação Flask no nível superior
app = Flask(__name__)

import os # <-- Adicione esta importação
from flask import Flask, jsonify
# ... (outras importações)

app = Flask(__name__)

# --- INÍCIO DA MODIFICAÇÃO ---

# Lógica para usar o banco de dados do Railway em produção ou o local em desenvolvimento
db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("mysql://"):
    # O Railway usa "mysql://", mas o mysqlconnector precisa de "mysql+mysqlconnector://"
    db_url = db_url.replace("mysql://", "mysql+mysqlconnector://", 1)

# Define a URI do banco de dados. Se a variável de ambiente não existir, usa a string local.
app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'mysql+mysqlconnector://root@localhost/ancora_teste'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicialize o objeto db com o app
db.init_app(app)

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