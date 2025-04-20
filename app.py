
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from cachetools import TTLCache
import os

app = Flask(__name__)
CORS(app)
token_cache = TTLCache(maxsize=1, ttl=3500)

def obter_token():
    if "token" in token_cache:
        return token_cache["token"]
    url_token = "https://sso-catalogo.redeancora.com.br/connect/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": "65tvh6rvn4d7uer3hqqm2p8k2pvnm5wx",
        "client_secret": "9Gt2dBRFTUgunSeRPqEFxwNgAfjNUPLP5EBvXKCn"
    }
    res = requests.post(url_token, headers=headers, data=data, verify=False)
    if res.status_code == 200:
        token_cache["token"] = res.json().get("access_token")
        return token_cache["token"]
    return None

@app.route("/buscar", methods=["GET"])
def buscar():
    termo = request.args.get("produto", "").strip().lower()
    marca_filtro = request.args.get("marca", "").strip().lower()
    ordem = request.args.get("ordem", "asc").lower()

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
        "itensPorPagina": 200
    }
    res = requests.post(url_api, headers=headers, json=payload, verify=False)
    if res.status_code != 200:
        return jsonify({"error": "Erro ao buscar dados"}), 502

    produtos = res.json().get("results", [])
    resultados = []
    marcas = set()

    for p in produtos:
        data = p.get("data", {})
        nome = data.get("nomeProduto", "")
        marca = data.get("marca", "")
        marcas.add(marca)
        if marca_filtro and marca.lower() != marca_filtro:
            continue

        aplicacoes = data.get("aplicacoes", [])
        if aplicacoes:
            primeira_aplicacao = aplicacoes[0]
            montadora = primeira_aplicacao.get("montadora", "")
            carroceria = primeira_aplicacao.get("carroceria", "")
            potencia = primeira_aplicacao.get("hp", "")
            ano_ini = primeira_aplicacao.get("fabricacaoInicial", "")
            ano_fim = primeira_aplicacao.get("fabricacaoFinal", "")
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

    resultados.sort(key=lambda x: x["nome"].lower(), reverse=(ordem == "desc"))
    return jsonify({
        "results": resultados,
        "brands": list(marcas)
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
