from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from datetime import datetime, timedelta
# Importa o search_service e o AutocompleteAdaptativo
from utils import search_service
from utils.autocomplete_adaptativo import AutocompleteAdaptativo
from utils.preprocess import tratar_dados
from utils.sort import ordenar_produtos
from utils.processar_item import processar_item
from utils.processar_similares import processar_similares
from flask_compress import Compress
from utils.token_manager import require_token

app = Flask(__name__)
CORS(app)
Compress(app)

produto_detalhado_bruto = None

# ... (Funções auxiliares e de buffer continuam iguais)
def erro(msg, status=400):
    return jsonify({"success": False, "error": msg}), status

def obrigatorios(campos: dict):
    faltando = [k for k, v in campos.items() if not v]
    if faltando:
        return erro(f"Parâmetro(s) obrigatório(s) faltando: {', '.join(faltando)}")
    return None

item_consumido = False
similares_consumido = False
componentes_consumido = False
produto_expira_em = None

def is_produto_expirado():
    global produto_detalhado_bruto
    return not produto_detalhado_bruto or datetime.utcnow() > produto_expira_em

def iniciar_expiracao():
    global produto_expira_em
    produto_expira_em = datetime.utcnow() + timedelta(seconds=30)

def verificar_e_limpar_dados():
    global produto_detalhado_bruto, item_consumido, similares_consumido, componentes_consumido, produto_expira_em
    if item_consumido and similares_consumido and componentes_consumido and is_produto_expirado():
        produto_detalhado_bruto = None
        item_consumido = False
        similares_consumido = False
        componentes_consumido = False
        produto_expira_em = None


@app.route("/")
def home():
    return "API ativa. Rotas: /pesquisar, /autocomplete, /produto, /item, /similares"

@app.route("/pesquisar", methods=["GET"])
@require_token
def pesquisar():
    # Esta rota está estável e não precisa de alterações
    termo = request.args.get("produto", "").strip().lower()
    placa = request.args.get("placa", "").strip()
    marca = request.args.get("marca", "").strip().lower()
    ordem = request.args.get("ordem", "asc").strip().lower() == "asc"
    pagina = int(request.args.get("pagina", 1))
    itens_por_pagina = 15

    if not termo:
        return jsonify({"dados": [], "marcas": [], "pagina": 1, "total_paginas": 0, "proxima_pagina": False, "mensagem_busca": "", "tipo_mensagem": ""})

    token = request.token
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    produtos_brutos = []
    mensagem_busca = ""
    tipo_mensagem = ""

    if placa:
        payload = {"produtoFiltro": {"nomeProduto": termo}, "veiculoFiltro": {"veiculoPlaca": placa}, "pagina": 0, "itensPorPagina": 500}
        res = search_service.session.post("https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao/catalogo/produtos/query", headers=headers, json=payload)
        if res.status_code == 200:
            produtos_brutos = res.json().get("pageResult", {}).get("data", [])
            if produtos_brutos:
                mensagem_busca = f"Exibindo resultados compatíveis com a placa '{placa}'."
                tipo_mensagem = "success"
    
    if not produtos_brutos:
        payload = {"produtoFiltro": {"nomeProduto": termo}, "pagina": 0, "itensPorPagina": 500}
        res = search_service.session.post("https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao/catalogo/produtos/query", headers=headers, json=payload)
        if res.status_code == 200:
            produtos_genericos = res.json().get("pageResult", {}).get("data", [])
            if placa and produtos_genericos:
                mensagem_busca = f"Não encontramos resultados para a placa '{placa}'. Exibindo resultados gerais."
                tipo_mensagem = "info"
            produtos_brutos = produtos_genericos
        else:
            return erro("Erro ao buscar produtos", 500)

    produtos_tratados = tratar_dados(produtos_brutos)
    
    marcas_disponiveis = sorted(set(p.get("marca", "") for p in produtos_tratados if p.get("marca")))
    resultados_filtrados = [p for p in produtos_tratados if not marca or p.get("marca", "").lower() == marca]
    resultados_ordenados = ordenar_produtos(resultados_filtrados, asc=ordem, key_func=lambda x: x.get('nome', '').lower())
    
    total_itens = len(resultados_ordenados)
    total_paginas = (total_itens + itens_por_pagina - 1) // itens_por_pagina if itens_por_pagina > 0 else 0
    inicio = (pagina - 1) * itens_por_pagina
    fim = inicio + itens_por_pagina

    return jsonify({
        "marcas": marcas_disponiveis,
        "dados": resultados_ordenados[inicio:fim],
        "pagina": pagina, "total_paginas": total_paginas, "proxima_pagina": pagina < total_paginas,
        "mensagem_busca": mensagem_busca, "tipo_mensagem": tipo_mensagem
    })

@app.route("/autocomplete", methods=["GET"])
@require_token
def autocomplete():
    prefix = request.args.get("prefix", "").strip().lower()
    placa = request.args.get("placa", "").strip()
    if not prefix:
        return jsonify({"sugestoes": []})
    
    # Chama a nova função orquestradora
    sugestoes = search_service.get_autocomplete_suggestions(request.token, prefix, placa)
    return jsonify({"sugestoes": sugestoes})

# ... (rotas /produto, /item, /similares e o resto do arquivo continuam iguais)
@app.route("/produto", methods=["GET"])
@require_token
def produto():
    global produto_detalhado_bruto
    #... (seu código)

@app.route("/item", methods=["GET"])
def item():
    global produto_detalhado_bruto
    #... (seu código)

@app.route("/similares", methods=["GET"])
def similares():
    global produto_detalhado_bruto
    #... (seu código)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)