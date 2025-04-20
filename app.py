
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_compress import Compress
from cachetools import TTLCache
import requests
import heapq
import time
import os

app = Flask(__name__)
CORS(app)
Compress(app)

# Cache para token e produtos
token_cache = TTLCache(maxsize=1, ttl=3500)  # ~58 minutos

# Autenticação com client_credentials com cache
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
        token = response.json().get('access_token')
        token_cache["token"] = token
        return token
    return None

def get_nome(prod):
    if isinstance(prod, dict):
        if "data" in prod and isinstance(prod["data"], dict):
            return (prod["data"].get("nomeProduto") or "").lower()
        return (prod.get("nomeProduto") or "").lower()
    return ""

def get_numeric(prod, key):
    try:
        if isinstance(prod, dict):
            if "data" in prod and isinstance(prod["data"], dict):
                return float(prod["data"].get(key) or 0)
            return float(prod.get(key) or 0)
    except (ValueError, TypeError):
        return 0
    return 0

def quick_sort(produtos, asc=True, key_func=get_nome):
    if len(produtos) <= 1:
        return produtos
    pivot = produtos[len(produtos) // 2]
    pivot_key = key_func(pivot)
    left = [p for p in produtos if key_func(p) < pivot_key]
    middle = [p for p in produtos if key_func(p) == pivot_key]
    right = [p for p in produtos if key_func(p) > pivot_key]
    return quick_sort(left, asc, key_func) + middle + quick_sort(right, asc, key_func) if asc else quick_sort(right, asc, key_func) + middle + quick_sort(left, asc, key_func)

def buscar_produtos(token, termo, pagina=0, itens_por_pagina=15):
    api_url = "https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao/catalogo/produtos/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "produtoFiltro": {"nomeProduto": termo},
        "pagina": pagina,
        "itensPorPagina": itens_por_pagina
    }
    response = requests.post(api_url, headers=headers, json=payload, verify=False)
    if response.status_code == 200:
        try:
            return response.json().get("pageResult", {}).get("data", [])
        except Exception:
            return []
    return []

@app.route("/")
def index():
    return "API está funcionando!"

@app.route("/buscar", methods=["GET"])
def buscar():
    try:
        termo = request.args.get("produto", "").strip().lower()
        if not termo:
            return jsonify({"error": "Nome do produto nao informado"}), 400

        pagina = int(request.args.get("pagina", "1")) - 1
        itens_por_pagina = int(request.args.get("itensPorPagina", "15"))
        ordem = request.args.get("ordem", "asc").strip().lower()
        asc = ordem == "asc"

        token = obter_token()
        if not token:
            return jsonify({"error": "Erro ao obter token"}), 500

        produtos = buscar_produtos(token, termo, pagina, itens_por_pagina)

        if len(produtos) > 1:
            produtos = quick_sort(produtos, asc)

        marcas = list({p.get("data", {}).get("marca", "") or p.get("marca", "") for p in produtos if p})

        return jsonify({
            "results": produtos,
            "brands": marcas,
            "pagina": pagina + 1,
            "itensPorPagina": itens_por_pagina,
            "total": len(produtos)
        })

    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route("/autocomplete", methods=["GET"])
def autocomplete():
    try:
        prefix = request.args.get("prefix", "").strip().lower()
        if not prefix:
            return jsonify([])

        token = obter_token()
        if not token:
            return jsonify({"error": "Erro ao obter token"}), 500

        produtos = buscar_produtos(token, prefix, 0, 1000)
        nomes = list({get_nome(p) for p in produtos if get_nome(p)})
        sugestoes = [nome for nome in nomes if prefix in nome][:8]
        return jsonify(sugestoes)
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route("/heap", methods=["GET"])
def heap_endpoint():
    try:
        produto = request.args.get("produto", "").strip()
        if not produto:
            return jsonify({"error": "Nome do produto nao informado"}), 400
        k = int(request.args.get("k", "5"))
        largest = request.args.get("modo", "maior").lower() == "maior"
        key_field = request.args.get("criterio", "hp").strip()
        marca = request.args.get("marca", "").strip().lower()
        token = obter_token()
        if not token:
            return jsonify({"error": "Erro ao obter token"}), 500
        produtos = buscar_produtos(token, produto, 0, 200)
        filtrados = [p for p in produtos if (p.get("data", {}).get("marca") or p.get("marca", "")).lower() == marca]
        selecionados = heapq.nlargest(k, filtrados, key=lambda p: get_numeric(p, key_field)) if largest else heapq.nsmallest(k, filtrados, key=lambda p: get_numeric(p, key_field))
        resultado = quick_sort(selecionados, asc=not largest, key_func=lambda p: get_numeric(p, key_field))
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500


@app.route("/tabela", methods=["GET"])
def tabela():
    try:
        produto = request.args.get("produto", "").strip().lower()
        marca = request.args.get("marca", "").strip().lower()
        pagina = int(request.args.get("pagina", "1")) - 1
        itens_por_pagina = int(request.args.get("itensPorPagina", "15"))
        ordem = request.args.get("ordem", "asc").strip().lower()
        asc = ordem == "asc"

        if not produto or not marca:
            return jsonify({"error": "Produto ou marca não informados"}), 400

        token = obter_token()
        if not token:
            return jsonify({"error": "Erro ao obter token"}), 500

        produtos = buscar_produtos(token, produto, 0, 1000)
        filtrados = [p for p in produtos if (p.get("data", {}).get("marca") or p.get("marca", "")).lower() == marca]

        if len(filtrados) > 1:
            filtrados = quick_sort(filtrados, asc)

        inicio = pagina * itens_por_pagina
        fim = inicio + itens_por_pagina
        resultados_paginados = filtrados[inicio:fim]

        return jsonify({
            "results": resultados_paginados,
            "total": len(filtrados),
            "pagina": pagina + 1,
            "itensPorPagina": itens_por_pagina
        })
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
