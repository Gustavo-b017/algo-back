from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import os
from datetime import datetime, timedelta
from utils.autocomplete_adaptativo import AutocompleteAdaptativo
from utils.preprocess import tratar_dados
from utils.sort import ordenar_produtos
from utils.processar_item import processar_item
from utils.processar_similares import processar_similares
from flask_compress import Compress
from utils.token_manager import require_token, obter_token
from utils.lojas import obter_melhor_rota
from utils.entrega import calcular_rota_entregas

app = Flask(__name__)
CORS(app)

Compress(app)
session = requests.Session()

def headers_com_token(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

def erro(msg, status=400):
    return jsonify({"success": False, "error": msg}), status

def obrigatorios(campos: dict):
    faltando = [k for k, v in campos.items() if not v]
    if faltando:
        return erro(f"Parâmetro(s) obrigatório(s) faltando: {', '.join(faltando)}")
    return None

autocomplete_engine = AutocompleteAdaptativo()
produtos_buffer = []
termo_buffer = ""
contador_buscas = 0

# Buffer global de produto detalhado
produto_detalhado_bruto = None
item_consumido = False
similares_consumido = False
componentes_consumido = False
produto_expira_em = None

def is_produto_expirado():
    global produto_expira_em
    return not produto_expira_em or datetime.utcnow() > produto_expira_em

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
    return "API ativa. Rotas: /buscar, /tratados, /autocomplete, /produto, /item, /similares, /componentes-filhos"

@app.route("/buscar", methods=["GET"])
@require_token
def buscar():
    global produtos_buffer, contador_buscas, termo_buffer
    termo = request.args.get("produto", "").strip().lower()
    val = obrigatorios({"produto": termo})
    if val: return val

    token = request.token
    headers = headers_com_token(token)

    url_nome = "https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao/catalogo/produtos/query"
    payload_nome = {
        "produtoFiltro": {"nomeProduto": termo},
        "pagina": 0,
        "itensPorPagina": 300
    }
    res_nome = session.post(url_nome, headers=headers, json=payload_nome)
    if res_nome.status_code != 200:
        return erro("Erro ao buscar produtos", 500)

    produtos_brutos = res_nome.json().get("pageResult", {}).get("data", [])
    produtos_tratados = tratar_dados(produtos_brutos)

    url_super = "https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao/catalogo/v2/produtos/query/sumario"
    payload_super = {
        "veiculoFiltro": {},
        "superbusca": termo,
        "pagina": 0,
        "itensPorPagina": 100
    }
    res_super = session.post(url_super, headers=headers, json=payload_super)
    produtos_super = res_super.json().get("pageResult", {}).get("data", []) if res_super.status_code == 200 else []

    termos_extras = set()
    for p in produtos_super:
        data = p.get("data", {})
        termos_extras.update(data.get("nomeProduto", "").strip().lower().split())
        termos_extras.add(data.get("codigoReferencia", "").strip().lower())
        termos_extras.add(data.get("marca", "").strip().lower())

    if termo != termo_buffer:
        autocomplete_engine.build(produtos_tratados, termo)
        for termo_extra in termos_extras:
            autocomplete_engine.build([], termo_extra)
        termo_buffer = termo

    produtos_buffer = produtos_tratados.copy()
    contador_buscas = (contador_buscas + 1) % 3

    return jsonify({"mensagem": "Produtos tratados atualizados."})

@app.route("/tratados", methods=["GET"])
def tratados():
    global produtos_buffer
    marca = request.args.get("marca", "").strip().lower()
    ordem = request.args.get("ordem", "asc").strip().lower() == "asc"
    pagina = int(request.args.get("pagina", 1))
    itens_por_pagina = 15

    resultados = produtos_buffer
    if marca:
        resultados = [p for p in resultados if p.get("marca", "").lower() == marca]

    resultados = ordenar_produtos(resultados, asc=ordem, key_func=lambda x: x.get('nome', '').lower(), limite=itens_por_pagina + 5)
    total_itens = len(resultados)
    total_paginas = (total_itens + itens_por_pagina - 1) // itens_por_pagina

    inicio = (pagina - 1) * itens_por_pagina
    fim = inicio + itens_por_pagina

    return jsonify({
        "marcas": sorted(set(p.get("marca", "") for p in produtos_buffer if p.get("marca"))),
        "dados": resultados[inicio:fim],
        "pagina": pagina,
        "total_paginas": total_paginas,
        "proxima_pagina": pagina < total_paginas
    })

@app.route("/autocomplete", methods=["GET"])
def autocomplete():
    prefix = request.args.get("prefix", "").strip().lower()
    return jsonify({"sugestoes": autocomplete_engine.search(prefix) if prefix else []})

@app.route("/produto", methods=["GET"])
@require_token
def produto():
    global produto_detalhado_bruto, item_consumido, similares_consumido, componentes_consumido
    id_enviado = request.args.get("id", type=int)
    codigo_referencia = request.args.get("codigoReferencia", "").strip()
    nome_produto = request.args.get("nomeProduto", "").strip()

    val = obrigatorios({"id": id_enviado, "codigoReferencia": codigo_referencia, "nomeProduto": nome_produto})
    if val: return val

    token = request.token
    headers = headers_com_token(token)
    payload = {
        "produtoFiltro": {
            "nomeProduto": nome_produto.upper().strip(),
            "codigoReferencia": codigo_referencia,
            "id": id_enviado
        },
        "pagina": 0,
        "itensPorPagina": 20
    }
    res = session.post("https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao/catalogo/produtos/query", headers=headers, json=payload)
    if res.status_code != 200:
        return erro("Erro ao consultar produtos", 500)

    produtos = res.json().get("pageResult", {}).get("data", [])
    produto_correto = next(
        (p for p in produtos if p.get("data", {}).get("id") == id_enviado and
         p.get("data", {}).get("codigoReferencia") == codigo_referencia and
         p.get("data", {}).get("nomeProduto", "").strip().lower() == nome_produto.lower().strip()),
        None
    )
    if not produto_correto:
        return erro("Produto não encontrado", 404)

    produto_detalhado_bruto = produto_correto.get("data", {})
    item_consumido = similares_consumido = componentes_consumido = False
    iniciar_expiracao()
    # return jsonify({"mensagem": "Produto detalhado carregado."})
    return produto_detalhado_bruto

@app.route("/item", methods=["GET"])
def item():
    global produto_detalhado_bruto, item_consumido
    if not produto_detalhado_bruto or is_produto_expirado():
        return erro("Produto expirado, refaça a busca.", 400)
    item_consumido = True
    response = jsonify(processar_item(produto_detalhado_bruto))
    verificar_e_limpar_dados()
    return response

@app.route("/similares", methods=["GET"])
def similares():
    global produto_detalhado_bruto, similares_consumido
    if not produto_detalhado_bruto or is_produto_expirado():
        return erro("Produto expirado, refaça a busca.", 400)
    similares_consumido = True
    response = jsonify(processar_similares(produto_detalhado_bruto))
    verificar_e_limpar_dados()
    return response

@app.route("/lojas", methods=["GET"])
def lojas():
    try:
        rota = obter_melhor_rota()
        return jsonify({
            "fiap": {
                "nome": "FIAP Paulista",
                "coordenadas": [-23.564372, -46.653923],
                "endereco": "Av. Paulista, 1106 - Bela Vista, São Paulo - SP"
            },
            "loja_mais_proxima": rota
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/rota-entrega", methods=["GET"])
def rota_entrega():
    return jsonify(calcular_rota_entregas())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
