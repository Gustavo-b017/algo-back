from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
import threading
from utils.bst import BST
from utils.preprocess import tratar_dados
from utils.sort import quick_sort
from utils.processar_item import processar_item
from utils.processar_similares import processar_similares
from flask_compress import Compress

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
Compress(app)

autocomplete_bst = BST()
produtos_tratados = []
ultimo_prefixo = ""

produto_detalhado_bruto = None
item_consumido = False
similares_consumido = False
timer_produto = None

# =========================== Funções auxiliares ===========================

def obter_token():
    url_token = "https://sso-catalogo.redeancora.com.br/connect/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": "65tvh6rvn4d7uer3hqqm2p8k2pvnm5wx",
        "client_secret": "9Gt2dBRFTUgunSeRPqEFxwNgAfjNUPLP5EBvXKCn"
    }
    res = requests.post(url_token, headers=headers, data=data)
    if res.status_code == 200:
        return res.json().get("access_token")
    return None

def verificar_e_limpar_dados():
    global produto_detalhado_bruto, item_consumido, similares_consumido, timer_produto
    if item_consumido and similares_consumido:
        produto_detalhado_bruto = None
        item_consumido = False
        similares_consumido = False
        if timer_produto:
            timer_produto.cancel()
            timer_produto = None

def expirar_produto():
    global produto_detalhado_bruto, item_consumido, similares_consumido, timer_produto
    produto_detalhado_bruto = None
    item_consumido = False
    similares_consumido = False
    timer_produto = None

def iniciar_timer_expiracao():
    global timer_produto
    if timer_produto:
        timer_produto.cancel()
    timer_produto = threading.Timer(30.0, expirar_produto)
    timer_produto.start()

# =========================== Rotas principais ===========================

@app.route("/")
def home():
    return "API ativa. Rotas: /buscar, /tratados, /autocomplete, /produto, /item, /similares"

@app.route("/buscar", methods=["GET"])
def buscar():
    global produtos_tratados
    termo = request.args.get("produto", "").strip().lower()
    if not termo:
        return jsonify({"error": "Produto não informado"}), 400

    token = obter_token()
    if not token:
        return jsonify({"error": "Token inválido"}), 401

    url_api = "https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao/catalogo/produtos/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "produtoFiltro": {"nomeProduto": termo},
        "pagina": 0,
        "itensPorPagina": 300
    }
    res = requests.post(url_api, headers=headers, json=payload)
    if res.status_code != 200:
        return jsonify({"error": "Erro ao buscar produtos"}), 500

    produtos_brutos = res.json().get("pageResult", {}).get("data", [])
    produtos_tratados = tratar_dados(produtos_brutos)
    return jsonify({"mensagem": "Produtos tratados atualizados."})

@app.route("/tratados", methods=["GET"])
def tratados():
    marca = request.args.get("marca", "").strip().lower()
    ordem = request.args.get("ordem", "asc").strip().lower() == "asc"
    pagina = int(request.args.get("pagina", 1))
    itens_por_pagina = 15

    resultados = produtos_tratados
    marcas_unicas = sorted(set(p.get("marca", "") for p in resultados if p.get("marca")))

    if marca:
        resultados = [p for p in resultados if p.get("marca", "").lower() == marca]

    resultados = quick_sort(resultados, asc=ordem, key_func=lambda x: x.get('nome', '').lower())
    total_itens = len(resultados)
    total_paginas = (total_itens + itens_por_pagina - 1) // itens_por_pagina

    inicio = (pagina - 1) * itens_por_pagina
    fim = inicio + itens_por_pagina
    dados_paginados = resultados[inicio:fim]

    return jsonify({
        "marcas": marcas_unicas,
        "dados": dados_paginados,
        "pagina": pagina,
        "total_paginas": total_paginas,
        "proxima_pagina": pagina < total_paginas
    })

@app.route("/autocomplete", methods=["GET"])
def autocomplete():
    global ultimo_prefixo, autocomplete_bst
    prefix = request.args.get("prefix", "").strip().lower()
    if not prefix:
        return jsonify({"sugestoes": []})

    if prefix != ultimo_prefixo:
        nomes = [p['nome'] for p in produtos_tratados if p.get('nome')]
        autocomplete_bst = BST()
        autocomplete_bst.build_balanced(nomes)
        ultimo_prefixo = prefix

    sugestoes = autocomplete_bst.search_prefix(prefix)
    return jsonify({"sugestoes": sugestoes})

# =========================== Nova rota /produto com nome, id e codigoReferencia ===========================

@app.route("/produto", methods=["GET"])
def produto():
    global produto_detalhado_bruto, item_consumido, similares_consumido

    id_enviado = request.args.get("id", type=int)
    codigo_referencia = request.args.get("codigoReferencia", "").strip()
    nome_produto = request.args.get("nomeProduto", "").strip()

    if not (id_enviado and codigo_referencia and nome_produto):
        return jsonify({"error": "Parâmetros obrigatórios não enviados."}), 400

    token = obter_token()
    if not token:
        return jsonify({"error": "Token inválido"}), 401

    url_api = "https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao/catalogo/produtos/query"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "produtoFiltro": {
            "nomeProduto": nome_produto.upper().strip(),
            "codigoReferencia": codigo_referencia,
            "id": id_enviado
        },
        "pagina": 0,
        "itensPorPagina": 20
    }

    res = requests.post(url_api, headers=headers, json=payload)
    if res.status_code != 200:
        return jsonify({"error": "Erro ao consultar produtos"}), 500

    produtos = res.json().get("pageResult", {}).get("data", [])

    produto_correto = next(
        (p for p in produtos
            if p.get("data", {}).get("id") == id_enviado
            and p.get("data", {}).get("codigoReferencia") == codigo_referencia
            and p.get("data", {}).get("nomeProduto", "").strip().lower() == nome_produto.lower().strip()),
        None
    )

    if not produto_correto:
        return jsonify({"error": "Produto não encontrado."}), 404

    produto_detalhado_bruto = produto_correto.get("data", {})
    item_consumido = False
    similares_consumido = False
    iniciar_timer_expiracao()

    return jsonify({"mensagem": "Produto detalhado carregado."})

@app.route("/item", methods=["GET"])
def item():
    global produto_detalhado_bruto, item_consumido
    if not produto_detalhado_bruto:
        return jsonify({"error": "Produto expirado, refaça a busca."}), 400

    item_consumido = True
    verificar_e_limpar_dados()

    item_tratado = processar_item(produto_detalhado_bruto)
    return jsonify(item_tratado)

@app.route("/similares", methods=["GET"])
def similares():
    global produto_detalhado_bruto, similares_consumido
    if not produto_detalhado_bruto:
        return jsonify({"error": "Produto expirado, refaça a busca."}), 400

    similares_consumido = True

    similares_tratados = processar_similares(produto_detalhado_bruto)
    
    verificar_e_limpar_dados()
    
    return jsonify(similares_tratados)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
