from utils.sort import ordenar_produtos
from utils.preprocess import tratar_dados
from flask import Blueprint, jsonify, request
from decorators.token_decorator import require_token
from services.search_service import search_service_instance
from utils.autocomplete_adaptativo import autocomplete_engine

search_bp = Blueprint("search", __name__)


@search_bp.route("/montadoras", methods=["GET"])
@require_token
def get_montadoras():
    resposta_api = search_service_instance.buscar_montadoras(request.token)
    if not resposta_api:
        return (
            jsonify(
                {"success": False, "error": "Não foi possível buscar as montadoras."}
            ),
            502,
        )
    data = resposta_api.get("data", [])
    montadoras_formatado = [
        {"id": item.get("id"), "nome": item.get("descricao")} for item in data
    ]
    montadoras_ordenado = sorted(montadoras_formatado, key=lambda x: x["nome"])
    return jsonify(montadoras_ordenado)


@search_bp.route("/familias", methods=["GET"])
@require_token
def get_familias():
    resposta_api = search_service_instance.buscar_familias(request.token)
    if not resposta_api:
        return (
            jsonify(
                {"success": False, "error": "Não foi possível buscar as famílias."}
            ),
            502,
        )
    data = resposta_api.get("data", [])
    familias_formatado = [
        {"id": item.get("id"), "nome": item.get("descricao")} for item in data
    ]
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
    familia_nome = (request.args.get("familia_nome") or "").strip()
    marca_filtro = (request.args.get("marca") or "").strip().upper()
    termo = (request.args.get("termo") or "").strip().lower()
    placa = (request.args.get("placa") or "").strip().upper()
    subfamilia_id = request.args.get("subfamilia_id")
    subfamilia_nome = (request.args.get("subfamilia_nome") or "").strip()

    pagina = int(request.args.get("pagina", 1))
    itens_por_pagina = 15

    # ---------- ORDENAR ----------
    # front pode mandar: relevancia | score | mais_vendidos | vendidos | mais_bem_avaliados | avaliacao | maior_preco | menor_preco | nome
    raw_ordenar = (request.args.get("ordenar_por", "nome") or "nome").strip().lower()
    raw_ordem = (request.args.get("ordem", "") or "").strip().lower()

    alias = {
        "relevancia": "score",
        "mais_vendidos": "vendidos",
        "mais_bem_avaliados": "avaliacao",
        "maior_preco": "preco_desc",
        "menor_preco": "preco_asc",
    }
    norm = alias.get(raw_ordenar, raw_ordenar)

    if norm in ("preco_asc", "preco_desc"):
        ordenar_por = "preco"
        ordem_asc = (norm == "preco_asc")
    elif norm in ("score", "vendidos", "avaliacao"):
        ordenar_por = norm
        ordem_asc = (raw_ordem == "asc") if raw_ordem in ("asc", "desc") else False  # default desc
    else:
        ordenar_por = "nome"
        ordem_asc = (raw_ordem != "desc")  # default asc

    produtos_brutos = []
    mensagem = ""
    filtro_produto_api = {}

    print(f"Params: termo='{termo}', familia_id={familia_id}, marca='{marca_filtro}', "
          f"ordenar_por='{ordenar_por}', ordem_asc={ordem_asc}")

    # ---------- BUSCA POR TERMO ----------
    if termo:
        filtro_produto_api["nomeProduto"] = termo
        filtro_veiculo = {"veiculoPlaca": placa} if placa else {}
        resp = search_service_instance.buscar_produtos(
            request.token, filtro_produto=filtro_produto_api, filtro_veiculo=filtro_veiculo, itens_por_pagina=500
        )
        if resp and resp.get("pageResult", {}).get("data"):
            produtos_brutos = resp["pageResult"]["data"]
            mensagem = f"Resultados para '{termo}'."
        elif placa:
            resp = search_service_instance.buscar_produtos(
                request.token, filtro_produto=filtro_produto_api, itens_por_pagina=500
            )
            if resp:
                produtos_brutos = resp.get("pageResult", {}).get("data", [])
                mensagem = f"Placa não encontrada. Exibindo resultados para '{termo}'."

    # ---------- BUSCA POR FAMILIA/SUB + MARCA ----------
    elif marca_filtro and familia_id:
        filtro_produto_api = {
            "familiaId": int(familia_id),
            "nomeProduto": subfamilia_nome if subfamilia_id else familia_nome
        }
        if subfamilia_id:
            filtro_produto_api["ultimoNivelId"] = int(subfamilia_id)
        resp = search_service_instance.buscar_produtos(
            request.token, filtro_produto=filtro_produto_api, itens_por_pagina=5000
        )
        if resp:
            todos = resp.get("pageResult", {}).get("data", [])
            for it in todos:
                for ap in (it.get("data", {}) or {}).get("aplicacoes", []):
                    if (ap.get("montadora", "") or "").upper() == marca_filtro:
                        produtos_brutos.append(it)
                        break

    print(f"Encontrados {len(produtos_brutos)} produtos brutos.")

    # ---------- SCORE POR ID (wrapper da API) ----------
    def _score_map(itens):
        mapa = {}
        for it in itens or []:
            if not isinstance(it, dict): 
                continue
            d = it.get("data")
            if isinstance(d, dict) and d.get("id") is not None:
                mapa[d["id"]] = it.get("score")
            elif it.get("id") is not None and "score" in it:
                mapa[it["id"]] = it.get("score")
        return mapa
    score_by_id = _score_map(produtos_brutos)

    # ---------- NORMALIZAÇÃO ----------
    produtos_tratados = tratar_dados(produtos_brutos)
    for p in produtos_tratados:
        if p.get("score") is None:
            pid = p.get("id")
            if pid in score_by_id:
                p["score"] = score_by_id[pid]

    # ---------- ORDENAÇÃO (None sempre por último; tie-break por nome) ----------
    from utils.sort import ordenar_produtos

    if ordenar_por == "score":
        def key(x):
            s = x.get("score")
            return (s is None, -(s or 0.0), (x.get("nome") or "").lower())
        resultados = ordenar_produtos(produtos_tratados, asc=True, key_func=key)

    elif ordenar_por == "vendidos":
        def key(x):
            v = x.get("vendidos")
            return (v is None, -(v or 0), (x.get("nome") or "").lower())
        resultados = ordenar_produtos(produtos_tratados, asc=True, key_func=key)

    elif ordenar_por == "avaliacao":
        def key(x):
            r = x.get("avaliacao_media")
            n = x.get("avaliacoes") or 0
            return (r is None, -(r or 0.0), -n, (x.get("nome") or "").lower())
        resultados = ordenar_produtos(produtos_tratados, asc=True, key_func=key)

    elif ordenar_por == "preco":
        def key(x):
            p = x.get("preco")
            return (p is None, p or 0.0, (x.get("nome") or "").lower())
        resultados = ordenar_produtos(produtos_tratados, asc=ordem_asc, key_func=key)

    else:  # nome (default)
        resultados = ordenar_produtos(
            produtos_tratados,
            asc=ordem_asc,
            key_func=lambda x: (x.get("nome") or "").lower()
        )

    # ---------- PAGINAÇÃO ----------
    total_itens = len(resultados)
    total_paginas = (total_itens + itens_por_pagina - 1) // itens_por_pagina if itens_por_pagina > 0 else 0
    inicio = (pagina - 1) * itens_por_pagina
    fim = inicio + itens_por_pagina

    print(f"Retornando {len(resultados[inicio:fim])} itens (ordenar_por={ordenar_por}, ordem_asc={ordem_asc}).")

    return jsonify({
        "dados": resultados[inicio:fim],
        "pagina": pagina,
        "total_paginas": total_paginas,
        "mensagem": mensagem,
        "ordenar_por": ordenar_por,
        "ordem": "asc" if ordem_asc else "desc"
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
