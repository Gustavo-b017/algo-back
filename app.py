from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
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

@app.route("/")
def home():
    return "API ativa. Rotas: /buscar, /tratados, /autocomplete"

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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)