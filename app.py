# app.py
import os
import logging
from urllib.parse import quote_plus

# Carrega .env de forma robusta (sem find_dotenv)
def _load_env():
    from dotenv import load_dotenv
    base_dir = os.path.abspath(os.path.dirname(__file__))
    # tenta .env na raiz do projeto (mesmo dir do app.py)
    env_path = os.path.join(base_dir, ".env")
    if os.path.isfile(env_path):
        load_dotenv(env_path, override=True)
    else:
        # fallback: tenta a partir do CWD (útil em alguns runners)
        load_dotenv(override=True)

_load_env()

from flask import Flask, jsonify
from flask_cors import CORS
from flask_compress import Compress
from database.__init__ import db
from database.models import Usuario, Produto
from routes.search import search_bp
from routes.product import product_bp


# -----------------------------------------------------------------------------
# Criação da app
# -----------------------------------------------------------------------------
app = Flask(__name__)

# -----------------------------------------------------------------------------
# Logging básico (legível e configurável por ENV)
# -----------------------------------------------------------------------------
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Configuração do Banco (Railway ou local)
# -----------------------------------------------------------------------------
def _build_db_uri() -> str:
    """
    Monta a URI do MySQL a partir das ENVs do Railway ou usa fallback local.
    Faz escapes seguros na senha (caso tenha '@', '#', etc.).
    """
    if os.getenv("MYSQLHOST"):
        # Em produção (Railway), trate todas como obrigatórias
        host = os.getenv("MYSQLHOST")
        user = os.getenv("MYSQLUSER")
        password = os.getenv("MYSQLPASSWORD")
        database = os.getenv("MYSQLDATABASE")
        port = os.getenv("MYSQLPORT", "3306")

        missing = [k for k, v in {
            "MYSQLHOST": host, "MYSQLUSER": user, "MYSQLPASSWORD": password, "MYSQLDATABASE": database
        }.items() if not v]
        if missing:
            raise RuntimeError(f"Variáveis de ambiente ausentes para o DB: {', '.join(missing)}")

        # Escapa a senha para a URI
        pwd = quote_plus(password)
        return f"mysql+mysqlconnector://{user}:{pwd}@{host}:{port}/{database}"

    # Fallback local (mantive teu default)
    return os.getenv("DATABASE_URL", "mysql+mysqlconnector://root@localhost/ancora_teste")


db_url = _build_db_uri()

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config.update(
    JSON_SORT_KEYS=False,               # não reordena chaves de JSON (mantém tua ordem)
    JSON_AS_ASCII=False,                # preserva acentuação
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    # Engine options para conexões estáveis no Railway
    SQLALCHEMY_ENGINE_OPTIONS={
        "pool_pre_ping": True,         # evita "MySQL server has gone away"
        "pool_recycle": 280,           # recicla antes do timeout comum de 300s
        # Descomente/ajuste se precisar tunar:
        # "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
        # "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
    },
)


# -----------------------------------------------------------------------------
# Extensões (CORS e Compress)
# -----------------------------------------------------------------------------
# CORS: por default libera localhost:5173 e teu domínio Vercel; pode sobrescrever por ENV
_default_origins = "http://localhost:5173,https://algo-front-kohl.vercel.app"
origins = [o.strip() for o in os.getenv("CORS_ORIGINS", _default_origins).split(",") if o.strip()]
CORS(app, resources={r"/*": {"origins": origins, "supports_credentials": True}})

# Compress: útil para JSON; mantém default sem exageros
app.config.setdefault("COMPRESS_MIMETYPES", ["application/json", "text/json", "text/plain"])
Compress(app)


# -----------------------------------------------------------------------------
# Banco (init)
# -----------------------------------------------------------------------------
db.init_app(app)

# (Opcional) Em dev, você pode querer auto-criar as tabelas.
# Use CREATE_SCHEMA=1 para habilitar.
if os.getenv("CREATE_SCHEMA") == "1":
    with app.app_context():
        db.create_all()
        log.info("Schema criado/validado (dev).")


# -----------------------------------------------------------------------------
# Blueprints
# -----------------------------------------------------------------------------
app.register_blueprint(search_bp)
app.register_blueprint(product_bp)


# -----------------------------------------------------------------------------
# Rotas básicas
# -----------------------------------------------------------------------------
@app.route("/")
def home():
    return "API ativa. Acesso às rotas de busca e de produtos."

@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


# -----------------------------------------------------------------------------
# Error handlers (JSON, discretos)
# -----------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "Rota não encontrada."}), 404

@app.errorhandler(500)
def internal_error(e):
    log.exception("Erro interno não tratado")
    return jsonify({"success": False, "error": "Erro interno do servidor."}), 500


# -----------------------------------------------------------------------------
# Execução
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(debug=debug, host="0.0.0.0", port=port)
