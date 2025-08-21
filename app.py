import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_compress import Compress

# 1. Importamos os nossos Blueprints de rotas
from routes.search import search_bp
from routes.product import product_bp

# Função para criar e configurar a aplicação Flask
def create_app():
    app = Flask(__name__)
    
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

    return app

# Ponto de entrada para executar a nossa aplicação
if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)