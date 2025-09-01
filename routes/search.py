from utils.sort import ordenar_produtos
from utils.preprocess import tratar_dados
from flask import Blueprint, jsonify, request
from decorators.token_decorator import require_token 
from services.search_service import search_service_instance
from utils.autocomplete_adaptativo import autocomplete_engine

search_bp = Blueprint('search', __name__)

@search_bp.route("/montadoras", methods=["GET"])
@require_token
def get_montadoras():
    resposta_api = search_service_instance.buscar_montadoras(request.token)
    if not resposta_api:
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
    sugestoes = autocomplete_engine.obter_sugestoes_ao_vivo(prefix, request.token)
    return jsonify({"sugestoes": sugestoes})


@search_bp.route("/pesquisar", methods=["GET"])
@require_token
def pesquisar_produtos():
    print("\n--- NOVA REQUISIÇÃO /pesquisar ---")
    
    familia_id = request.args.get("familia_id")
    familia_nome = request.args.get("familia_nome", "").strip()
    marca_filtro = request.args.get("marca", "").strip().upper()
    termo = request.args.get("termo", "").strip().lower()
    placa = request.args.get("placa", "").strip().upper()
    subfamilia_id = request.args.get("subfamilia_id")
    subfamilia_nome = request.args.get("subfamilia_nome", "").strip()

    pagina = int(request.args.get("pagina", 1))
    ordem = request.args.get("ordem", "asc").strip().lower() == "asc"
    itens_por_pagina = 15

    produtos_brutos = []
    mensagem = ""
    filtro_produto_api = {}

    print(f"Parâmetros Recebidos: familia_id={familia_id}, familia_nome='{familia_nome}', marca='{marca_filtro}', termo='{termo}'")

    if termo:
        print("-> Modo de busca: TERMO")
        filtro_produto_api["nomeProduto"] = termo
        filtro_veiculo = {"veiculoPlaca": placa} if placa else {}
        resposta_api = search_service_instance.buscar_produtos(request.token, filtro_produto=filtro_produto_api, filtro_veiculo=filtro_veiculo, itens_por_pagina=500)
        
        if resposta_api and resposta_api.get("pageResult", {}).get("data"):
            produtos_brutos = resposta_api.get("pageResult", {}).get("data", [])
            mensagem = f"Resultados para '{termo}'."
        elif placa:
            resposta_api = search_service_instance.buscar_produtos(request.token, filtro_produto=filtro_produto_api, itens_por_pagina=500)
            if resposta_api:
                produtos_brutos = resposta_api.get("pageResult", {}).get("data", [])
                mensagem = f"Placa não encontrada. Exibindo resultados para '{termo}'."

    # LÓGICA DE FILTRO ATUALIZADA PARA SER FLEXÍVEL
    elif marca_filtro and familia_id:
        filtro_produto_api = {
            "familiaId": int(familia_id),
            # Usa o nome da subfamília se disponível, senão, o da família
            "nomeProduto": subfamilia_nome if subfamilia_id else familia_nome
        }
        
        # Adiciona o ID da subfamília ao filtro apenas se ele foi selecionado
        if subfamilia_id:
            filtro_produto_api["ultimoNivelId"] = int(subfamilia_id)

        resposta_api = search_service_instance.buscar_produtos(request.token, filtro_produto=filtro_produto_api, itens_por_pagina=5000)
        
        if resposta_api:
            todos_os_produtos = resposta_api.get("pageResult", {}).get("data", [])
            
            # Filtra manualmente pela montadora
            for produto_item in todos_os_produtos:
                for aplicacao in produto_item.get("data", {}).get("aplicacoes", []):
                    if aplicacao.get("montadora", "").upper() == marca_filtro:
                        produtos_brutos.append(produto_item)
                        break
    
    print(f"Encontrados {len(produtos_brutos)} produtos brutos após a lógica.")
    
    produtos_tratados = tratar_dados(produtos_brutos)
    resultados_ordenados = ordenar_produtos(produtos_tratados, asc=ordem, key_func=lambda x: x.get('nome', '').lower())
    
    total_itens = len(resultados_ordenados)
    total_paginas = (total_itens + itens_por_pagina - 1) // itens_por_pagina if itens_por_pagina > 0 else 0
    inicio = (pagina - 1) * itens_por_pagina
    fim = inicio + itens_por_pagina
    
    print(f"Retornando {len(resultados_ordenados[inicio:fim])} produtos na página {pagina}.")
    
    return jsonify({
        "dados": resultados_ordenados[inicio:fim],
        "pagina": pagina,
        "total_paginas": total_paginas,
        "mensagem": mensagem
    })


# ROTA ADICIONADA PARA BUSCAR SUBFAMÍLIAS
@search_bp.route("/familias/<int:familia_id>/subfamilias", methods=["GET"])
@require_token
def get_subfamilias_por_familia(familia_id):
    """Retorna as subfamílias (últimos níveis) para uma família específica."""
    resposta_api = search_service_instance.buscar_grupos_produtos(request.token)
    
    if not resposta_api:
        return jsonify([])

    todos_os_grupos = resposta_api.get("data", [])
    
    subfamilias_filtradas = [
        {"id": item.get("id"), "nome": item.get("descricao")}
        for item in todos_os_grupos
        if item.get("familia", {}).get("id") == familia_id
    ]
    
    subfamilias_ordenadas = sorted(subfamilias_filtradas, key=lambda x: x["nome"])
    
    return jsonify(subfamilias_ordenadas)   