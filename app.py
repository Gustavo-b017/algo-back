from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_compress import Compress
from cachetools import TTLCache
import requests
import heapq
import os

app = Flask(__name__)

# CORS liberado para todas as origens
CORS(app)
Compress(app)

# Segue o restante do código...


# Cache global
token_cache = TTLCache(maxsize=1, ttl=3500)  # TTL ~58min
produto_cache = TTLCache(maxsize=1000, ttl=600)  # TTL ~10min

# Autenticação com client_credentials
def obter_token():
    if "token" in token_cache:
        return token_cache["token"]
    url_token = "https://sso-catalogo.redeancora.com.br/connect/token"
    headers_token = {"Content-Type": "application/x-www-form-urlencoded"}
    data_token = {
        "grant_type": "client_credentials",
        "client_id": "65tvh6rvn4d7uer3hqqm2p8k2pvnm5wx",
        "client_secret": "9Gt2dBRFTUgunSeRPqEFxwNgAfjNUPLP5EBvXKCn"
    }
    response = requests.post(url_token, headers=headers_token, data=data_token, verify=False)
    if response.status_code == 200:
        token_cache["token"] = response.json().get('access_token')
        return token_cache["token"]
    return None

# Utilidades
def get_nome(prod):
    if isinstance(prod, dict):
        if "data" in prod and isinstance(prod["data"], dict):
            return (prod["data"].get("nomeProduto") or "").lower()
        return (prod.get("nomeProduto") or "").lower()
    return ""

@app.route("/buscar", methods=["GET"])
def buscar():
    produto = request.args.get("produto", "").strip().lower()
    marca = request.args.get("marca", "").strip().lower()
    pagina = int(request.args.get("pagina", 1))
    itens_por_pagina = int(request.args.get("itensPorPagina", 15))
    ordem = request.args.get("ordem", "asc").lower()

    cache_key = f"{produto}::{marca}"
    if cache_key in produto_cache:
        resultados_filtrados = produto_cache[cache_key]
    else:
        token = obter_token()
        if not token:
            return jsonify({"error": "Erro ao obter token de autenticação"}), 401

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        url_api = f"https://catalogo.redeancora.com.br/produtos/buscar?termo={produto}"
        response = requests.get(url_api, headers=headers, verify=False)
        if response.status_code != 200:
            return jsonify({"error": "Erro ao buscar dados da API externa"}), 502

        todos_resultados = response.json().get("results", [])
        resultados_filtrados = [
            r for r in todos_resultados
            if marca in (r.get("data", {}).get("marca", "") or r.get("marca", "")).lower()
        ]

        # Ordenação
        resultados_filtrados.sort(key=lambda x: get_nome(x), reverse=(ordem == "desc"))
        produto_cache[cache_key] = resultados_filtrados

    inicio = (pagina - 1) * itens_por_pagina
    fim = inicio + itens_por_pagina
    pagina_resultados = resultados_filtrados[inicio:fim]

    return jsonify({
        "results": pagina_resultados,
        "total": len(resultados_filtrados),
        "pagina": pagina,
        "itensPorPagina": itens_por_pagina
    })


@app.route("/tabela", methods=["GET"])
def tabela():
    produto = request.args.get("produto", "").strip().lower()
    marca = request.args.get("marca", "").strip().lower()
    pagina = int(request.args.get("pagina", 1))
    itens_por_pagina = int(request.args.get("itensPorPagina", 15))
    ordem = request.args.get("ordem", "asc").lower()

    cache_key = f"tabela::{produto}::{marca}"
    if cache_key in produto_cache:
        dados = produto_cache[cache_key]
    else:
        token = obter_token()
        if not token:
            return jsonify({"error": "Token inválido"}), 401
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        url = f"https://catalogo.redeancora.com.br/produtos/buscar?termo={produto}"
        response = requests.get(url, headers=headers, verify=False)
        if response.status_code != 200:
            return jsonify({"error": "Erro externo"}), 502
        produtos = response.json().get("results", [])
        filtrados = [
            {
                "nome": p.get("data", {}).get("nomeProduto") or p.get("nomeProduto", ""),
                "marca": p.get("data", {}).get("marca") or p.get("marca", ""),
                "preco": p.get("data", {}).get("preco", 0),
                "ano": p.get("data", {}).get("ano", ""),
                "potencia": p.get("data", {}).get("potencia", "")
            }
            for p in produtos if marca in (p.get("data", {}).get("marca", "") or p.get("marca", "")).lower()
        ]
        filtrados.sort(key=lambda x: x["nome"].lower(), reverse=(ordem == "desc"))
        produto_cache[cache_key] = filtrados

    inicio = (pagina - 1) * itens_por_pagina
    fim = inicio + itens_por_pagina
    return jsonify({
        "results": dados[inicio:fim],
        "total": len(dados),
        "pagina": pagina
    })

@app.route("/heap", methods=["GET"])
def heap():
    produto = request.args.get("produto", "").strip().lower()
    marca = request.args.get("marca", "").strip().lower()
    criterio = request.args.get("criterio", "hp").lower()
    modo = request.args.get("modo", "maior")
    k = int(request.args.get("k", 5))

    cache_key = f"heap::{produto}::{marca}"
    if cache_key in produto_cache:
        produtos = produto_cache[cache_key]
    else:
        token = obter_token()
        if not token:
            return jsonify({"error": "Token inválido"}), 401
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        url = f"https://catalogo.redeancora.com.br/produtos/buscar?termo={produto}"
        response = requests.get(url, headers=headers, verify=False)
        if response.status_code != 200:
            return jsonify({"error": "Erro externo"}), 502
        produtos_raw = response.json().get("results", [])
        produtos = [
            {
                "nome": p.get("data", {}).get("nomeProduto") or p.get("nomeProduto", ""),
                "marca": p.get("data", {}).get("marca") or p.get("marca", ""),
                "potencia": p.get("data", {}).get("potencia", 0),
                "ano": p.get("data", {}).get("ano", "")
            }
            for p in produtos_raw if marca in (p.get("data", {}).get("marca", "") or p.get("marca", "")).lower()
        ]
        produto_cache[cache_key] = produtos

    key_func = lambda x: x.get(criterio, 0)
    heap = heapq.nlargest(k, produtos, key=key_func) if modo == "maior" else heapq.nsmallest(k, produtos, key=key_func)

    return jsonify(heap)
