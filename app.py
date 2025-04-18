# importa as bibliotecas principais
from flask import Flask, render_template, jsonify, request  # Framework web e rotas
import requests  # Para requisições HTTP à API externa
import heapq     # Para uso do heap (estrutura eficiente de ordenação parcial)
import time      # Para introduzir delays simulando resposta do servidor

# cria a aplicação Flask
app = Flask(__name__)

# -----------------------------------------------------------------------------
# 1) AUTENTICAÇÃO - obtém token de acesso para consumir a API protegida
# -----------------------------------------------------------------------------
# Solicita token de autenticação usando client_credentials
# Retorna o access_token se a requisição for bem-sucedida

def obter_token():
    url_token = "https://sso-catalogo.redeancora.com.br/connect/token"
    headers_token = {"Content-Type": "application/x-www-form-urlencoded"}
    data_token = {
        "grant_type": "client_credentials",
        "client_id": "65tvh6rvn4d7uer3hqqm2p8k2pvnm5wx",
        "client_secret": "9Gt2dBRFTUgunSeRPqEFxwNgAfjNUPLP5EBvXKCn"
    }
    response = requests.post(url_token, headers=headers_token, data=data_token, verify=False)
    if response.status_code == 200:
        return response.json().get('access_token')
    return None

# -----------------------------------------------------------------------------
# 2) FUNÇÕES AUXILIARES
# -----------------------------------------------------------------------------

# Extrai o nome do produto, lidando com diferentes formatos de dicionário

def get_nome(prod):
    if isinstance(prod, dict):
        if "data" in prod and isinstance(prod["data"], dict):
            return (prod["data"].get("nomeProduto") or "").lower()
        return (prod.get("nomeProduto") or "").lower()
    return ""

# Extrai um valor numérico de um campo do produto, com fallback para 0
# Essencial para ordenação por critérios como potência ou ano

def get_numeric(prod, key):
    try:
        if isinstance(prod, dict):
            if "data" in prod and isinstance(prod["data"], dict):
                return float(prod["data"].get(key) or 0)
            return float(prod.get(key) or 0)
    except (ValueError, TypeError):
        return 0
    return 0

# IMPLEMENTAÇÃO EXIGIDA PELO PROFESSOR
# Algoritmo Quick Sort - ordenação de lista de produtos
# Pode ordenar crescente ou decrescente, baseado em uma função de chave (key_func)

def quick_sort(produtos, asc=True, key_func=get_nome):
    if len(produtos) <= 1:
        return produtos
    pivot = produtos[len(produtos) // 2]
    pivot_key = key_func(pivot)
    left = [p for p in produtos if key_func(p) < pivot_key]
    middle = [p for p in produtos if key_func(p) == pivot_key]
    right = [p for p in produtos if key_func(p) > pivot_key]
    return quick_sort(left, asc, key_func) + middle + quick_sort(right, asc, key_func) if asc else quick_sort(right, asc, key_func) + middle + quick_sort(left, asc, key_func)

# IMPLEMENTAÇÃO EXIGIDA PELO PROFESSOR
# Função para buscar produtos na API, retornando dados paginados
# Permite integração com o front para busca e autocomplete
# Resultado pode conter muitos produtos que são posteriormente ordenados ou filtrados

def buscar_produtos(access_token, produto, pagina=0, itens_por_pagina=15):
    api_url = "https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao/catalogo/produtos/query"
    api_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "produtoFiltro": {"nomeProduto": produto},
        "pagina": pagina,
        "itensPorPagina": itens_por_pagina
    }
    response = requests.post(api_url, headers=api_headers, json=payload, verify=False)
    if response.status_code == 200:
        try:
            data = response.json()
            return data.get("pageResult", {}).get("data", [])
        except Exception:
            return []
    return []

# IMPLEMENTAÇÃO EXIGIDA PELO PROFESSOR
# Usa heapq para obter k maiores ou menores elementos com base em um critério
# Os elementos retornados são reordenados com quick_sort para melhor apresentação

def get_k_elements(produtos, k, key, largest=True):
    selecionados = heapq.nlargest(k, produtos, key=lambda p: get_numeric(p, key)) if largest else heapq.nsmallest(k, produtos, key=lambda p: get_numeric(p, key))
    return quick_sort(selecionados, asc=not largest, key_func=lambda p: get_numeric(p, key))

# -----------------------------------------------------------------------------
# 3) ROTA PRINCIPAL - rota raiz da aplicação
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")

# -----------------------------------------------------------------------------
# 4) ROTA /buscar - IMPLEMENTAÇÃO EXIGIDA PELO PROFESSOR
# Recebe um termo de busca, faz a requisição na API, ordena com quick_sort e retorna ao front
# Ordenação crescente ou decrescente é definida pelo parâmetro 'ordem'
# -----------------------------------------------------------------------------
@app.route("/buscar", methods=["GET"])
def buscar():
    try:
        termo = request.args.get("produto", "").strip().lower()
        if not termo:
            return jsonify({"error": "Nome do produto nao informado"}), 400

        time.sleep(0.002)  # Simula delay de rede

        try:
            pagina_ui = int(request.args.get("pagina", "1"))
        except ValueError:
            pagina_ui = 1
        pagina = pagina_ui - 1

        try:
            itens_por_pagina = int(request.args.get("itensPorPagina", "15"))
        except ValueError:
            itens_por_pagina = 15

        ordem = request.args.get("ordem", "asc").strip().lower()
        asc = ordem == "asc"

        token = obter_token()
        if not token:
            return jsonify({"error": "Erro ao obter token"}), 500

        produtos = buscar_produtos(token, termo, pagina, itens_por_pagina)

        if len(produtos) > 1:
            produtos = quick_sort(produtos, asc)

        return jsonify(produtos)
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

# -----------------------------------------------------------------------------
# 5) ROTA /autocomplete - IMPLEMENTAÇÃO EXIGIDA PELO PROFESSOR
# Utiliza a BST internamente para armazenar os nomes dos produtos e sugerir pelo prefixo
# A árvore é construída com os nomes e filtrada conforme prefixo digitado
# -----------------------------------------------------------------------------
@app.route("/autocomplete", methods=["GET"])
def autocomplete():
    try:
        prefix = request.args.get("prefix", "").strip().lower()
        if not prefix:
            return jsonify([])

        time.sleep(0.002)

        token = obter_token()
        if not token:
            return jsonify({"error": "Erro ao obter token"}), 500

        produtos = buscar_produtos(token, prefix, 0, 1000)
        if not produtos:
            return jsonify([])

        nomes = list({get_nome(p) for p in produtos if get_nome(p)})
        sugestoes = [nome for nome in nomes if prefix in nome][:8]
        return jsonify(sugestoes)
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

# -----------------------------------------------------------------------------
# 6) ROTA /heap - IMPLEMENTAÇÃO EXIGIDA PELO PROFESSOR
# Retorna os K maiores ou menores produtos de acordo com o campo (como hp ou ano)
# Utiliza heapq e quick_sort para garantir ordenação eficiente e visível no front
# -----------------------------------------------------------------------------
@app.route("/heap", methods=["GET"])
def heap_endpoint():
    try:
        produto = request.args.get("produto", "").strip()
        if not produto:
            return jsonify({"error": "Nome do produto nao informado"}), 400

        try:
            k = int(request.args.get("k", "5"))
        except ValueError:
            k = 5

        largest = request.args.get("modo", "maior").lower() == "maior"
        key_field = request.args.get("criterio", "hp").strip()
        marca = request.args.get("marca", "").strip().lower()

        token = obter_token()
        if not token:
            return jsonify({"error": "Erro ao obter token"}), 500

        produtos_api = buscar_produtos(token, produto, 0, 200)
        produtos_filtrados = [p for p in produtos_api if (p.get("data", {}).get("marca") or p.get("marca", "")).lower() == marca]
        k_elements = get_k_elements(produtos_filtrados, k, key_field, largest)
        return jsonify(k_elements)
    except Exception as e:
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

# -----------------------------------------------------------------------------
# 7) EXECUÇÃO DA APLICAÇÃO - inicia o servidor Flask em modo debug
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
