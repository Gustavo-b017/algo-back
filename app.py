
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from cachetools import TTLCache
from bst import BST
import os
import logging

app = Flask(__name__)
CORS(app)
token_cache = TTLCache(maxsize=1, ttl=3500)
autocomplete_bst = BST()

# Configurar logging
logging.basicConfig(level=logging.INFO)

def obter_token():
    if "token" in token_cache:
        return token_cache["token"]
    url_token = "https://sso-catalogo.redeancora.com.br/connect/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": os.getenv("CLIENT_ID", "65tvh6rvn4d7uer3hqqm2p8k2pvnm5wx"),
        "client_secret": os.getenv("CLIENT_SECRET", "9Gt2dBRFTUgunSeRPqEFxwNgAfjNUPLP5EBvXKCn")
    }
    try:
        res = requests.post(url_token, headers=headers, data=data, verify=False)
        if res.status_code == 200:
            token_cache["token"] = res.json().get("access_token")
            return token_cache["token"]
    except Exception as e:
        logging.error(f"Erro ao obter token: {e}")
    return None

def requisitar_produtos(token, termo, pagina, itens_por_pagina):
    url_api = "https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao/catalogo/produtos/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "produtoFiltro": {
            "nomeProduto": termo
        },
        "veiculoFiltro": {
            "veiculoPlaca": "DEM8i14"
        },
        "pagina": pagina,
        "itensPorPagina": itens_por_pagina
    }
    print("🔍 Payload enviado:", payload)
    res = requests.post(url_api, headers=headers, json=payload, verify=False)
    print("📡 Status:", res.status_code)
    print("📦 Resposta:", res.text)
    return res

@app.route("/buscar", methods=["GET"])
def buscar():
    termo = request.args.get("produto", "").strip().lower()
    marca_filtro = request.args.get("marca", "").strip().lower()
    ordem = request.args.get("ordem", "asc").lower()
    pagina = int(request.args.get("pagina", 0))
    itens_por_pagina = int(request.args.get("itensPorPagina", 10))

    token = obter_token()
    if not token:
        return jsonify({"error": "Token inválido"}), 401

    res = requisitar_produtos(token, termo, pagina, itens_por_pagina)
    if res.status_code != 200:
        return jsonify({"error": "Erro ao buscar dados"}), 502

    produtos = res.json().get("results", [])
    resultados = []
    marcas = set()
    nomes_para_bst = set()

    for p in produtos:
        data = p.get("data", {})
        nome = data.get("nomeProduto", "")
        marca = data.get("marca", "")
        marcas.add(marca)
        nomes_para_bst.add(nome)

        if marca_filtro and marca.lower() != marca_filtro:
            continue

        aplicacoes = data.get("aplicacoes", [])
        if aplicacoes:
            app_data = aplicacoes[0]
            montadora = app_data.get("montadora", "-")
            carroceria = app_data.get("carroceria", "-")
            potencia = app_data.get("hp", "-")
            ano_ini = app_data.get("fabricacaoInicial", "")
            ano_fim = app_data.get("fabricacaoFinal", "")
            ano = f"{ano_ini} - {ano_fim}" if ano_ini and ano_fim else "-"
        else:
            montadora = carroceria = potencia = ano = "-"

        resultados.append({
            "nome": nome,
            "marca": marca,
            "montadora": montadora,
            "carroceria": carroceria,
            "ano": ano,
            "potencia": potencia
        })

    if pagina == 0:
        autocomplete_bst.from_iterable(nomes_para_bst)

    resultados.sort(key=lambda x: x["nome"].lower(), reverse=(ordem == "desc"))

    return jsonify({
        "results": resultados,
        "brands": list(marcas)
    })

@app.route("/autocomplete", methods=["GET"])
def autocomplete():
    prefix = request.args.get("prefix", "").strip().lower()
    if not prefix:
        return jsonify([])
    suggestions = autocomplete_bst.search_prefix(prefix)
    return jsonify(suggestions)

@app.route("/")
def home():
    return "Backend da API está no ar!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
