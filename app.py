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

app = Flask(__name__)
CORS(app)
Compress(app)
session = requests.Session()

autocomplete_engine = AutocompleteAdaptativo()
termo_buffer = ""
produto_detalhado_bruto = None

# Funções auxiliares e de gerenciamento de buffer (sem alterações)
def headers_com_token(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

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
    return "API ativa. Rotas: /pesquisar, /autocomplete, /produto, /item, /similares"

# Apenas as rotas de montadoras/categorias foram removidas por enquanto
# O resto do seu app.py está aqui...

@app.route("/pesquisar", methods=["GET"])
@require_token
def pesquisar():
    global termo_buffer

    # 1. Pega os parâmetros da requisição
    termo = request.args.get("produto", "").strip().lower()
    placa = request.args.get("placa", "").strip()
    marca = request.args.get("marca", "").strip().lower()
    ordem = request.args.get("ordem", "asc").strip().lower() == "asc"
    pagina = int(request.args.get("pagina", 1))
    itens_por_pagina = 15

    if not termo:
        return jsonify({"dados": [], "marcas": [], "pagina": 1, "total_paginas": 0, "proxima_pagina": False, "mensagem_busca": "", "tipo_mensagem": ""})

    token = request.token
    headers = headers_com_token(token)
    produtos_brutos = []
    mensagem_busca = ""
    tipo_mensagem = ""

    # --- LÓGICA DE BUSCA CORRIGIDA ---
    # 2. Tenta a busca específica (PRODUTO + PLACA) se a placa for fornecida
    if placa:
        payload_especifico = {"produtoFiltro": {"nomeProduto": termo}, "veiculoFiltro": {"veiculoPlaca": placa}, "pagina": 0, "itensPorPagina": 500}
        res_especifico = session.post("https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao/catalogo/produtos/query", headers=headers, json=payload_especifico)
        if res_especifico.status_code == 200:
            produtos_brutos = res_especifico.json().get("pageResult", {}).get("data", [])
            if produtos_brutos:
                mensagem_busca = f"Exibindo resultados compatíveis com a placa '{placa}'."
                tipo_mensagem = "success"

    # 3. Se a busca específica falhou (ou não foi feita), faz a busca genérica
    if not produtos_brutos:
        payload_generico = {"produtoFiltro": {"nomeProduto": termo}, "pagina": 0, "itensPorPagina": 500}
        res_generico = session.post("https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao/catalogo/produtos/query", headers=headers, json=payload_generico)
        if res_generico.status_code == 200:
            produtos_genericos = res_generico.json().get("pageResult", {}).get("data", [])
            if placa and produtos_genericos:
                mensagem_busca = f"Não encontramos resultados para a placa '{placa}'. Exibindo resultados gerais."
                tipo_mensagem = "info"
            produtos_brutos = produtos_genericos
        else:
            return erro("Erro ao buscar produtos", 500)

    # 4. Processa os resultados obtidos (sejam eles da busca específica ou genérica)
    produtos_tratados = tratar_dados(produtos_brutos)
    if termo and termo != termo_buffer:
        autocomplete_engine.build(produtos_tratados, termo)
        termo_buffer = termo

    marcas_disponiveis = sorted(set(p.get("marca", "") for p in produtos_tratados if p.get("marca")))
    
    resultados_filtrados = produtos_tratados
    if marca:
        resultados_filtrados = [p for p in produtos_tratados if p.get("marca", "").lower() == marca]

    resultados_ordenados = ordenar_produtos(resultados_filtrados, asc=ordem, key_func=lambda x: x.get('nome', '').lower())
    
    total_itens = len(resultados_ordenados)
    total_paginas = (total_itens + itens_por_pagina - 1) // itens_por_pagina if itens_por_pagina > 0 else 0
    inicio = (pagina - 1) * itens_por_pagina
    fim = inicio + itens_por_pagina

    # 5. Retorna a resposta completa
    return jsonify({
        "marcas": marcas_disponiveis,
        "dados": resultados_ordenados[inicio:fim],
        "pagina": pagina,
        "total_paginas": total_paginas,
        "proxima_pagina": pagina < total_paginas,
        "mensagem_busca": mensagem_busca,
        "tipo_mensagem": tipo_mensagem
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
    payload = { "produtoFiltro": { "nomeProduto": nome_produto.upper().strip(), "codigoReferencia": codigo_referencia, "id": id_enviado }, "pagina": 0, "itensPorPagina": 20 }
    res = session.post("https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao/catalogo/produtos/query", headers=headers, json=payload)
    if res.status_code != 200:
        return erro("Erro ao consultar produtos", 500)

    produtos = res.json().get("pageResult", {}).get("data", [])
    produto_correto = next((p for p in produtos if p.get("data", {}).get("id") == id_enviado), None)
    
    if not produto_correto:
        return erro("Produto não encontrado", 404)

    produto_detalhado_bruto = produto_correto.get("data", {})
    item_consumido = similares_consumido = componentes_consumido = False
    iniciar_expiracao()
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)