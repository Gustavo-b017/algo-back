# app.py
import os
import logging
from urllib.parse import quote_plus
from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
from flask_compress import Compress
from database.__init__ import db
from routes.search import search_bp
from routes.product import product_bp
from routes.auth import auth_bp

# =============================================================================
# Comentário geral
# -----------------------------------------------------------------------------
# Este arquivo mantém TODA a lógica original. Foram adicionados apenas:
# - Docstrings e comentários objetivos nas funções/rotas existentes.
# - Bloco de Swagger (OpenAPI 3) que expõe:
#     • UI em /apidocs (via CDN, sem Flasgger)
#     • Arquivo OpenAPI em /openapi.yaml (carrega openapi.yaml ou openapi-oficina.yaml da raiz)
# Nada mais foi alterado.
# =============================================================================

# -----------------------------------------------------------------------------
# .env local (dev). Em produção o Railway injeta as ENVs.
# -----------------------------------------------------------------------------
def _load_env():
    """Carrega variáveis do .env em ambiente de desenvolvimento (sem erro se ausente)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    base_dir = os.path.abspath(os.path.dirname(__file__))
    env_path = os.path.join(base_dir, ".env")
    if os.path.isfile(env_path):
        load_dotenv(env_path, override=True)
    else:
        load_dotenv(override=True)

_load_env()

# -----------------------------------------------------------------------------
# App / logging
# -----------------------------------------------------------------------------
app = Flask(__name__)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# DB URI (Railway ou local)
# -----------------------------------------------------------------------------
def _build_db_uri() -> str:
    """Monta a URI do MySQL a partir das ENVs do Railway; caso contrário, usa fallback local."""
    if os.getenv("MYSQLHOST"):
        host = os.getenv("MYSQLHOST")
        user = os.getenv("MYSQLUSER")
        password = os.getenv("MYSQLPASSWORD")
        database = os.getenv("MYSQLDATABASE")  # <- SEM underscore
        port = os.getenv("MYSQLPORT", "3306")

        missing = [k for k, v in {
            "MYSQLHOST": host, "MYSQLUSER": user, "MYSQLPASSWORD": password, "MYSQLDATABASE": database
        }.items() if not v]
        if missing:
            raise RuntimeError(f"Variáveis de ambiente ausentes para o DB: {', '.join(missing)}")

        pwd = quote_plus(password)
        return f"mysql+mysqlconnector://{user}:{pwd}@{host}:{port}/{database}"

    return os.getenv("DATABASE_URL", "mysql+mysqlconnector://root@localhost/ancora_teste")

db_url = _build_db_uri()
app.config.update(
    SQLALCHEMY_DATABASE_URI=db_url,
    JSON_SORT_KEYS=False,
    JSON_AS_ASCII=False,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_ENGINE_OPTIONS={
        "pool_pre_ping": True,
        "pool_recycle": 280,
    },
)

# -----------------------------------------------------------------------------
# CORS + Compress (com fallback manual para erros 500)
# -----------------------------------------------------------------------------
_default_origins = "http://localhost:5173,https://algo-front-kohl.vercel.app"
origins = [o.strip() for o in os.getenv("CORS_ORIGINS", _default_origins).split(",") if o.strip()]
CORS(app, resources={r"/*": {"origins": origins, "supports_credentials": True}})
app.config.setdefault("COMPRESS_MIMETYPES", ["application/json", "text/json", "text/plain"])
Compress(app)

def _add_cors_headers(resp):
    """Aplica cabeçalhos CORS conforme origem permitida, incluindo credenciais e métodos."""
    origin = request.headers.get("Origin")
    if origin and origin in origins:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Credentials"] = "true"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return resp

@app.before_request
def _preflight():
    """Atende requisições OPTIONS (CORS preflight) com 204 e cabeçalhos adequados."""
    if request.method == "OPTIONS":
        return _add_cors_headers(make_response("", 204))

@app.after_request
def _after(resp):
    """Garante cabeçalhos CORS em todas as respostas."""
    return _add_cors_headers(resp)

# -----------------------------------------------------------------------------
# DB init + criação opcional do schema (USE UMA VEZ)
# -----------------------------------------------------------------------------
from database.models import Usuario, Produto  # importa modelos

db.init_app(app)
if os.getenv("CREATE_SCHEMA") == "1":
    with app.app_context():
        db.create_all()
        log.info("Schema criado/validado (dev/prod).")

# -----------------------------------------------------------------------------
# Blueprints
# -----------------------------------------------------------------------------
app.register_blueprint(search_bp)
app.register_blueprint(product_bp)
app.register_blueprint(auth_bp, url_prefix="/auth")

# -----------------------------------------------------------------------------
# Rotas base e handlers
# -----------------------------------------------------------------------------
@app.route("/")
def home():
    """Rota raiz: indica que a API está ativa e aponta as áreas disponíveis."""
    return "API ativa. Acesso às rotas de busca, produtos e auth."

@app.route("/health")
def health():
    """Healthcheck simples para monitoramento."""
    return jsonify({"status": "ok"}), 200

@app.errorhandler(404)
def not_found(e):
    """Handler para rotas inexistentes (404)."""
    return jsonify({"success": False, "error": "Rota não encontrada."}), 404

@app.errorhandler(Exception)
def internal_error(e):
    """Handler global de exceções não tratadas, com log e resposta 500 genérica."""
    log.exception("Erro interno não tratado")
    return jsonify({"success": False, "error": "Erro interno do servidor."}), 500

# -----------------------------------------------------------------------------
# Swagger UI (OpenAPI 3) SEM Flasgger — compatível com seu openapi.yaml
# - UI: /apidocs
# - YAML: /openapi.yaml  (carrega openapi.yaml OU openapi-oficina.yaml na raiz)
# -----------------------------------------------------------------------------
from flask import Response as _Response, send_file as _send_file
import pathlib as _pathlib

@app.get("/openapi.yaml")
def __serve_openapi_yaml():
    """
    Servir o arquivo OpenAPI (YAML) diretamente.
    Procura por 'openapi.yaml' ou 'openapi-oficina.yaml' na raiz do projeto.
    """
    for candidate in ("openapi.yaml", "openapi-oficina.yaml"):
        p = _pathlib.Path(candidate)
        if p.exists():
            return _send_file(str(p), mimetype="application/yaml")
    return _Response("Arquivo openapi.yaml não encontrado.", status=404)


@app.get("/apidocs")
def __swagger_ui_page():
    """
    Página HTML mínima que carrega o Swagger UI a partir do CDN,
    apontando para /openapi.yaml (OpenAPI 3.x).
    """
    html = """
    <!doctype html>
    <html lang="pt-br">
    <head>
      <meta charset="utf-8">
      <title>API Docs</title>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <link rel="stylesheet"
            href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
      <style>
        body { margin:0; }
        #swagger-ui { max-width: 100%; }
      </style>
    </head>
    <body>
      <div id="swagger-ui"></div>
      <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
      <script>
        window.ui = SwaggerUIBundle({
          url: '/openapi.yaml',
          dom_id: '#swagger-ui',
          deepLinking: true,
          presets: [SwaggerUIBundle.presets.apis],
          layout: 'BaseLayout'
        });
      </script>
    </body>
    </html>
    """
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}

@app.get("/redoc")
def __redoc_page():
    """Página ReDoc carregada via CDN, apontando para /openapi.yaml."""
    html = """
    <!doctype html>
    <html lang="pt-br">
    <head>
      <meta charset="utf-8">
      <title>API Docs (ReDoc)</title>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <style> body { margin:0; padding:0; } </style>
    </head>
    <body>
      <redoc spec-url="/openapi.yaml"></redoc>
      <script src="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"></script>
    </body>
    </html>
    """
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}

# -----------------------------------------------------------------------------
# Execução
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(debug=debug, host="0.0.0.0", port=port)
