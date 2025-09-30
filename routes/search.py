import os
import time
from collections import Counter
from utils.sort import ordenar_produtos
from utils.preprocess import tratar_dados
from flask import Blueprint, jsonify, request
from decorators.token_decorator import require_token
from services.search_service import search_service_instance
from utils.autocomplete_adaptativo import autocomplete_engine

# NOVO: extras

search_bp = Blueprint("search", __name__)

# ============ Helpers compartilhados (facetas/cache) ============
_FACET_CACHE = {}
_FACET_TTL = int(os.getenv("FACET_TTL_SECONDS", "600"))  # 10 min default

def _cache_get(key):
    rec = _FACET_CACHE.get(key)
    if not rec:
        return None
    exp, payload = rec
    if time.time() > exp:
        _FACET_CACHE.pop(key, None)
        return None
    return payload

def _cache_set(key, payload, ttl=_FACET_TTL):
    _FACET_CACHE[key] = (time.time() + ttl, payload)

def _nz(s):  # normalize string
    return (s or "").strip()

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


# ======================== Metadados básicos ========================
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


# ======================== Autocomplete ========================
@search_bp.route("/autocomplete", methods=["GET"])
@require_token
def get_autocomplete():
    prefix = _nz(request.args.get("prefix")).lower()
    if not prefix:
        return jsonify({"sugestoes": []})
    sugestoes = autocomplete_engine.obter_sugestoes_ao_vivo(prefix, request.token)
    return jsonify({"sugestoes": sugestoes})


# ======================== Facetas limpas ========================
@search_bp.route("/facetas-produto", methods=["GET"])
@require_token
def facetas_produto():
    """
    Facetas (subprodutos e marcas) válidas para um produto (família).
    Query params:
      - produto_nome OU familia_nome (string)
      - familia_id (int, opcional mas recomendado)
      - subfamilia_id (int, opcional) -> refina marcas
      - placa (string, opcional)
    """
    token = request.token
    produto_nome = _nz(request.args.get("produto_nome") or request.args.get("familia_nome"))
    familia_id = request.args.get("familia_id", type=int)
    subfamilia_id = request.args.get("subfamilia_id", type=int)
    placa = _nz(request.args.get("placa"))

    if not produto_nome and not familia_id:
        return jsonify({"success": False, "error": "Informe 'produto_nome' (ou 'familia_nome') ou 'familia_id'."}), 400

    # Resolver nome pelo ID, se necessário
    if not produto_nome and familia_id:
        resp_fam = search_service_instance.buscar_familias(token)
        familias = (resp_fam or {}).get("data", [])
        for f in familias:
            if int(f.get("id", -1)) == int(familia_id):
                produto_nome = _nz(f.get("descricao"))
                break
    if not produto_nome:
        return jsonify({"success": False, "error": "Não foi possível resolver o nome do produto pela família."}), 400

    # Cache
    cache_key = ("facets", produto_nome.lower(), str(familia_id or ""), str(subfamilia_id or ""), placa.upper())
    cached = _cache_get(cache_key)
    if cached:
        return jsonify(cached), 200

    # 1) Sumário (rápido)
    itens = []
    sumario = search_service_instance.buscar_sugestoes_sumario(token, termo_busca=produto_nome, itens_por_pagina=800)
    itens_sum = (sumario or {}).get("pageResult", {}).get("data", []) or []
    for it in itens_sum:
        data = it.get("data") if isinstance(it, dict) else it
        if isinstance(data, dict):
            itens.append(data)

    # 2) Fallback produtos/query caso sumário seja pobre
    if len(itens) < 10:
        filtro_produto = {"nomeProduto": produto_nome}
        if subfamilia_id:
            filtro_produto["ultimoNivelId"] = int(subfamilia_id)
        filtro_veiculo = {"veiculoPlaca": placa} if placa else {}
        resp_q = search_service_instance.buscar_produtos(token, filtro_produto=filtro_produto,
                                                         filtro_veiculo=filtro_veiculo, itens_por_pagina=1000)
        dados_q = (resp_q or {}).get("pageResult", {}).get("data", []) or []
        for it in dados_q:
            data = it.get("data") if isinstance(it, dict) else it
            if isinstance(data, dict):
                itens.append(data)

    if not itens:
        payload = {"subprodutos": [], "marcas": []}
        _cache_set(cache_key, payload)
        return jsonify(payload), 200

    # Filtrar por família/subfamília quando fornecidos
    if familia_id:
        itens = [d for d in itens if int((d.get("familia") or {}).get("id") or -1) == int(familia_id)]
    if subfamilia_id:
        itens = [d for d in itens if int(((d.get("familia") or {}).get("subFamilia") or {}).get("id") or -1) == int(subfamilia_id)]

    subprod_cont = Counter()
    marca_cont = Counter()

    for d in itens:
        # Marca da PEÇA
        m = _nz(d.get("marca"))
        if m:
            marca_cont[m] += 1

        fam = d.get("familia") or {}
        s = fam.get("subFamilia") or {}
        sid = s.get("id")
        sdesc = _nz(s.get("descricao"))
        if sid and sdesc:
            # só conta subfamília pertencente à família selecionada (quando houver)
            if not familia_id or int(fam.get("id") or -1) == int(familia_id):
                subprod_cont[(int(sid), sdesc)] += 1

    # Conferir subprodutos contra a lista oficial da família (se familia_id veio)
    if familia_id:
        resp_gr = search_service_instance.buscar_grupos_produtos(token)
        grupos = (resp_gr or {}).get("data", []) or []
        validos = {(int(g.get("id")), _nz(g.get("descricao")))
                   for g in grupos if int(((g.get("familia") or {}).get("id")) or -1) == int(familia_id)}
        subprod_cont = Counter({k: v for k, v in subprod_cont.items() if k in validos})

    subprodutos = [{"id": sid, "nome": sdesc, "qtd": qtd} for (sid, sdesc), qtd in subprod_cont.most_common()]
    subprodutos.sort(key=lambda x: (-x["qtd"], x["nome"]))

    marcas = [{"nome": nome, "qtd": qtd} for nome, qtd in marca_cont.most_common()]
    marcas.sort(key=lambda x: (-x["qtd"], x["nome"]))

    payload = {"subprodutos": subprodutos, "marcas": marcas}
    _cache_set(cache_key, payload)
    return jsonify(payload), 200


# ======================== Busca principal ========================
@search_bp.route("/pesquisar", methods=["GET"])
@require_token
def pesquisar_produtos():
    print("\n--- NOVA REQUISIÇÃO /pesquisar ---")

    familia_id = request.args.get("familia_id")
    familia_nome = _nz(request.args.get("familia_nome"))
    marca_filtro = _nz(request.args.get("marca")).upper()  # Marca da PEÇA
    termo = _nz(request.args.get("termo")).lower()
    placa = _nz(request.args.get("placa")).upper()
    subfamilia_id = request.args.get("subfamilia_id")
    subfamilia_nome = _nz(request.args.get("subfamilia_nome"))

    pagina = int(request.args.get("pagina", 1))
    itens_por_pagina = 15

    # ---------- ORDENAR ----------
    raw_ordenar = _nz(request.args.get("ordenar_por") or request.args.get("ordenacao") or "nome").lower()
    raw_ordem = _nz(request.args.get("ordem")).lower()

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
    filtro_veiculo = {"veiculoPlaca": placa} if placa else {}

    print(f"Params: termo='{termo}', familia_id={familia_id}, subfamilia_id={subfamilia_id}, marca='{marca_filtro}', "
          f"ordenar_por='{ordenar_por}', ordem_asc={ordem_asc}, placa='{placa}'")

    # ---------- BUSCA POR TERMO ----------
    if termo:
        filtro_produto_api["nomeProduto"] = termo
        resp = search_service_instance.buscar_produtos(
            request.token, filtro_produto=filtro_produto_api, filtro_veiculo=filtro_veiculo, itens_por_pagina=500
        )
        if resp and resp.get("pageResult", {}).get("data"):
            produtos_brutos = resp["pageResult"]["data"]
            mensagem = f"Resultados para '{termo}'."
        elif placa:
            # fallback sem placa
            resp = search_service_instance.buscar_produtos(
                request.token, filtro_produto=filtro_produto_api, itens_por_pagina=500
            )
            produtos_brutos = (resp or {}).get("pageResult", {}).get("data", []) or []
            mensagem = f"Placa não encontrada. Exibindo resultados para '{termo}'."

    # ---------- BUSCA POR FAMILIA/SUB ----------
    elif familia_id or familia_nome:
        # nomeProduto é requerido pela API
        nome_base = familia_nome or termo
        filtro_produto_api = {"nomeProduto": nome_base}

        if subfamilia_id:
            filtro_produto_api["ultimoNivelId"] = int(subfamilia_id)

        resp = search_service_instance.buscar_produtos(
            request.token, filtro_produto=filtro_produto_api, filtro_veiculo=filtro_veiculo, itens_por_pagina=5000
        )
        produtos_brutos = (resp or {}).get("pageResult", {}).get("data", []) or []

    # ---------- FILTRO POR MARCA DE PEÇA (sempre depois de obter a lista) ----------
    if marca_filtro:
        filtrados = []
        for it in produtos_brutos:
            data = (it.get("data") if isinstance(it, dict) else it) or {}
            marca_item = _nz(data.get("marca")).upper()
            if marca_item == marca_filtro:
                filtrados.append(it)
        produtos_brutos = filtrados

    print(f"Encontrados {len(produtos_brutos)} produtos brutos.")

    # ---------- SCORE POR ID ----------
    score_by_id = _score_map(produtos_brutos)

    # ---------- NORMALIZAÇÃO ----------
    produtos_tratados = tratar_dados(produtos_brutos)
    for p in produtos_tratados:
        if p.get("score") is None:
            pid = p.get("id")
            if pid in score_by_id:
                p["score"] = score_by_id[pid]

    # ---------- ORDENAÇÃO ----------
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

    else:  # nome
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
