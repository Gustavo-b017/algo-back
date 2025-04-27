from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
import threading
from utils.bst import BST
from utils.preprocess import tratar_dados
from utils.sort import quick_sort
from flask_compress import Compress

app = Flask(__name__)
CORS(app)
Compress(app)

autocomplete_bst = BST()
produtos_tratados = []
ultimo_prefixo = ""

# Variáveis para novo fluxo de produto detalhado
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

# =========================== Novas rotas /produto /item /similares ===========================

@app.route("/produto", methods=["GET"])
def produto():
    global produto_detalhado_bruto, item_consumido, similares_consumido
    codigo = request.args.get("codigoReferencia", "").strip()
    if not codigo:
        return jsonify({"error": "Código de referência não informado"}), 400

    token = obter_token()
    if not token:
        return jsonify({"error": "Token inválido"}), 401

    url = f"https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao/catalogo/produtos/{codigo}"
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.get(url, headers=headers)

    if res.status_code != 200:
        return jsonify({"error": "Erro ao buscar detalhe do produto"}), 500

    produto_detalhado_bruto = res.json().get("data", {})
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

    aplicacoes = []
    for app_item in produto_detalhado_bruto.get("aplicacoes", []):
        aplicacoes.append({
            "carroceria": app_item.get("carroceria"),
            "cilindros": app_item.get("cilindros"),
            "combustivel": app_item.get("combustivel"),
            "fabricacaoFinal": app_item.get("fabricacaoFinal"),
            "fabricacaoInicial": app_item.get("fabricacaoInicial"),
            "hp": app_item.get("hp"),
            "id": app_item.get("id"),
            "modelo": app_item.get("modelo"),
            "montadora": app_item.get("montadora"),
            "versao": app_item.get("versao")
        })

    aplicacoes_gerais = []
    for geral in produto_detalhado_bruto.get("aplicacoesGerais", []):
        aplicacoes_gerais.append({
            "codigoReferencia": geral.get("codigoReferencia"),
            "familia": geral.get("familia"),
            "descricao": geral.get("descricao"),
            "subFamilia": geral.get("subFamilia", {}).get("descricao")
        })

    produto = {
        "nomeProduto": produto_detalhado_bruto.get("nomeProduto"),
        "marca": produto_detalhado_bruto.get("marca"),
        "imagemReal": produto_detalhado_bruto.get("imagemReal"),
        "logomarca": produto_detalhado_bruto.get("logoMarca"),
        "score": produto_detalhado_bruto.get("score"),
        "aplicacoes": aplicacoes,
        "aplicacoesGerais": aplicacoes_gerais
    }

    return jsonify(produto)

@app.route("/similares", methods=["GET"])
def similares():
    global produto_detalhado_bruto, similares_consumido
    if not produto_detalhado_bruto:
        return jsonify({"error": "Produto expirado, refaça a busca."}), 400

    similares_consumido = True
    verificar_e_limpar_dados()

    similares_data = []
    for sim in produto_detalhado_bruto.get("similares", []):
        similares_data.append({
            "id": sim.get("id"),
            "logoMarca": sim.get("logoMarca"),
            "marca": sim.get("marca"),
            "codigoReferencia": sim.get("codigoReferencia")
        })

    produtos_parcialmente_similares = []
    for ps in produto_detalhado_bruto.get("produtosParcialmenteSimilares", []):
        produtos_parcialmente_similares.append({
            "codigoReferencia": ps.get("codigoReferencia"),
            "marca": ps.get("marca"),
            "nomeProduto": ps.get("nomeProduto")
        })

    similares = {
        "similares": similares_data,
        "produtosParcialmenteSimilares": produtos_parcialmente_similares,
        "produtosSistemasFilhos": produto_detalhado_bruto.get("produtosSistemasFilhos", []),
        "produtosSistemasPais": produto_detalhado_bruto.get("produtosSistemasPais", [])
    }

    return jsonify(similares)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
