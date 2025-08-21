from utils.sort import ordenar_produtos
from utils.preprocess import tratar_dados
from flask import Blueprint, jsonify, request
from decorators.token_decorator import require_token 
from services.search_service import search_service_instance
from utils.autocomplete_adaptativo import autocomplete_engine
# 1. Criamos o nosso Blueprint
# O primeiro argumento, 'search', é o nome do Blueprint.
# O segundo, __name__, diz ao Flask onde o encontrar.
search_bp = Blueprint('search', __name__)


# 2. Movemos a nossa rota para o Blueprint
# A única mudança é que usamos '@search_bp.route' em vez de '@app.route'
@search_bp.route("/montadoras", methods=["GET"])
@require_token
def get_montadoras():
    resposta_api = search_service_instance.buscar_montadoras(request.token)
    
    if not resposta_api:
        # Nota: Idealmente, teríamos uma função de erro partilhada, mas por agora está bem assim
        return jsonify({"success": False, "error": "Não foi possível buscar as montadoras."}), 502

    data = resposta_api.get("data", [])
    montadoras_formatado = [{"id": item.get("id"), "nome": item.get("descricao")} for item in data]
    montadoras_ordenado = sorted(montadoras_formatado, key=lambda x: x["nome"])
    
    return jsonify(montadoras_ordenado)

@search_bp.route("/familias", methods=["GET"])
@require_token
def get_familias():
    resposta_api = search_service_instance.buscar_familias(request.token)
    
    if not resposta_api:
        return jsonify({"success": False, "error": "Não foi possível buscar as famílias."}), 502

    data = resposta_api.get("data", [])
    familias_formatado = [{"id": item.get("id"), "nome": item.get("descricao")} for item in data]
    familias_ordenado = sorted(familias_formatado, key=lambda x: x["nome"])
    
    return jsonify(familias_ordenado)


@search_bp.route("/autocomplete", methods=["GET"])
@require_token
def get_autocomplete():
    prefix = request.args.get("prefix", "").strip().lower()
    if not prefix:
        return jsonify({"sugestoes": []})

    # A rota delega toda a lógica para o nosso motor adaptativo
    sugestoes = autocomplete_engine.obter_sugestoes_ao_vivo(prefix, request.token)
    
    return jsonify({"sugestoes": sugestoes})


@search_bp.route("/pesquisar", methods=["GET"])
@require_token
def pesquisar_produtos():
    # Parâmetros da busca guiada
    familia_id = request.args.get("familia_id")
    montadora_nome = request.args.get("montadora_nome", "").strip().upper()
    familia_nome = request.args.get("familia_nome", "").strip() # <-- NOVO

    # Parâmetros da busca por texto
    termo = request.args.get("termo", "").strip().lower()
    marca_filtro = request.args.get("marca", "").strip().lower()
    
    # Parâmetros de paginação e ordenação
    pagina = int(request.args.get("pagina", 1))
    ordem = request.args.get("ordem", "asc").strip().lower() == "asc"
    itens_por_pagina = 15

    produtos_brutos = []
    
    if familia_id and montadora_nome:
        # --- MUDANÇA AQUI ---
        # Agora o filtro é mais específico
        filtro_produto = {
            "familiaId": int(familia_id),
            "nomeProduto": familia_nome 
        }
        resposta_api = search_service_instance.buscar_produtos(request.token, filtro_produto=filtro_produto, itens_por_pagina=5000)
        
        # --- DEBUG: VAMOS VER O QUE A API NOS DEU ---
        if resposta_api:
            print(f"API retornou {resposta_api.get('pageResult', {}).get('count', 0)} produtos para esta família.")
        else:
            print("API não retornou uma resposta válida.")
        # --- FIM DO DEBUG ---

        if resposta_api:
            todos_os_produtos = resposta_api.get("pageResult", {}).get("data", [])
            
            for produto_item in todos_os_produtos:
                for aplicacao in produto_item.get("data", {}).get("aplicacoes", []):
                    if aplicacao.get("montadora", "").upper() == montadora_nome:
                        produtos_brutos.append(produto_item)
                        break

    # Senão, se temos um termo, fazemos a busca por texto
    elif termo:
        filtro_produto = {"nomeProduto": termo}
        resposta_api = search_service_instance.buscar_produtos(request.token, filtro_produto=filtro_produto, itens_por_pagina=500)
        if resposta_api:
            produtos_brutos = resposta_api.get("pageResult", {}).get("data", [])
    
    print(f"Encontrados {len(produtos_brutos)} produtos após o nosso filtro.")
    print(f"--- FIM DA BUSCA GUIADA ---")

    # --- PROCESSAMENTO E RESPOSTA ---
    produtos_tratados = tratar_dados(produtos_brutos)
    
    marcas_disponiveis = sorted(set(p.get("marca", "") for p in produtos_tratados if p.get("marca")))
    
    resultados_filtrados = produtos_tratados
    if marca_filtro:
        resultados_filtrados = [p for p in produtos_tratados if p.get("marca", "").lower() == marca_filtro]

    resultados_ordenados = ordenar_produtos(resultados_filtrados, asc=ordem, key_func=lambda x: x.get('nome', '').lower())
    
    # Lógica de paginação
    total_itens = len(resultados_ordenados)
    total_paginas = (total_itens + itens_por_pagina - 1) // itens_por_pagina if itens_por_pagina > 0 else 0
    inicio = (pagina - 1) * itens_por_pagina
    fim = inicio + itens_por_pagina
    
    return jsonify({
        "marcas": marcas_disponiveis,
        "dados": resultados_ordenados[inicio:fim],
        "pagina": pagina,
        "total_paginas": total_paginas,
        "proxima_pagina": pagina < total_paginas
    })