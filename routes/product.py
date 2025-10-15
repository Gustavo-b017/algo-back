# product.py
from flask import Blueprint, jsonify, request
from utils.processar_item import processar_item, _calcular_precos_simulados
from decorators.token_decorator import require_token
from utils.processar_similares import processar_similares
from services.search_service import search_service_instance

# Importe a instância do db da nova pasta
from database.__init__ import db
from database.models import Produto

from decorators.auth_decorator import login_required

product_bp = Blueprint("product", __name__)


@product_bp.route("/produto_detalhes", methods=["GET"])
@require_token
def get_produto_detalhes():
    # NÃO remove esses imports locais; evitam import cycles durante testes
    from utils.processar_item import processar_item, _calcular_precos_simulados
    from utils.processar_similares import processar_similares

    produto_id = request.args.get("id", type=int)
    nome_produto = (request.args.get("nomeProduto") or "").strip()
    codigo_referencia = (request.args.get("codigoReferencia") or "").strip()
    marca = (request.args.get("marca") or "").strip()

    if not produto_id and not nome_produto and not codigo_referencia:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Informe 'id', 'nomeProduto' ou 'codigoReferencia'.",
                }
            ),
            400,
        )

    svc = search_service_instance
    token = request.token

    # ---------- helpers ----------
    def _score_map(lista):
        mapa = {}
        for it in lista or []:
            if not isinstance(it, dict):
                continue
            d = it.get("data")
            if isinstance(d, dict) and d.get("id") is not None:
                mapa[d["id"]] = it.get("score")
            elif it.get("id") is not None and "score" in it:
                mapa[it["id"]] = it.get("score")
        return mapa

    def _escolher_item(itens, pid=None, cod=None, nome=None):
        """Retorna (data_escolhida, score) usando ordem de match: id -> codigo -> nome -> primeiro."""
        if not itens:
            return None, None
        s_map = _score_map(itens)
        # normaliza lista em 'datas'
        datas = [(it.get("data") if isinstance(it, dict) else it) or {} for it in itens]

        if pid is not None:
            for d in datas:
                if str(d.get("id")) == str(pid):
                    return d, s_map.get(d.get("id"))
        if cod:
            for d in datas:
                if (
                    d.get("codigoReferencia") or ""
                ).strip().upper() == cod.strip().upper():
                    return d, s_map.get(d.get("id"))
        if nome:
            nome_norm = nome.strip().lower()
            for d in datas:
                if (d.get("nomeProduto") or "").strip().lower() == nome_norm:
                    return d, s_map.get(d.get("id"))
        d = datas[0]
        return d, s_map.get(d.get("id"))

    # ---------- ordem de tentativas ----------
    # 1) código + marca (mais preciso)
    # 2) nome + marca
    # 3) id (nem sempre suportado pelo provider, mas tentamos)
    # 4) sumário (superbusca) SOMENTE se houver nome ou código
    tentativas = []

    if codigo_referencia:
        f = {"codigoReferencia": codigo_referencia}
        if marca:
            f["nomeFabricante"] = marca
        tentativas.append(("query", f))

    if nome_produto:
        f = {"nomeProduto": nome_produto}
        if marca:
            f["nomeFabricante"] = marca
        tentativas.append(("query", f))

    if produto_id:
        f = {"id": produto_id}
        if marca:
            f["nomeFabricante"] = marca
        tentativas.append(("query", f))

    termo_sumario = nome_produto or codigo_referencia
    if termo_sumario:  # NÃO tenta sumário com id puro
        tentativas.append(("sumario", {"superbusca": termo_sumario}))

    # ---------- execução ----------
    escolhido_data = None
    score_escolhido = None

    for modo, filtro in tentativas:
        if modo == "query":
            resp = svc.buscar_produtos(
                token, filtro_produto=filtro, itens_por_pagina=200
            )
            itens = (resp or {}).get("pageResult", {}).get("data", []) or []
        else:
            resp = svc.buscar_sugestoes_sumario(
                token, termo_busca=filtro["superbusca"], itens_por_pagina=200
            )
            itens = (resp or {}).get("pageResult", {}).get("data", []) or []

        if itens:
            escolhido_data, score_escolhido = _escolher_item(
                itens, pid=produto_id, cod=codigo_referencia, nome=nome_produto
            )
            if escolhido_data:
                break

    if not escolhido_data:
        return jsonify({"success": False, "error": "Produto não encontrado."}), 404

    # ---------- montagem do payload ----------
    detalhes_item = processar_item(escolhido_data)

    # garante preços se o processar_item não trouxe
    if "preco" not in detalhes_item or "precoOriginal" not in detalhes_item:
        detalhes_item.update(_calcular_precos_simulados(escolhido_data))

    # injeta score (quando vier do sumário/query)
    if detalhes_item.get("score") is None:
        detalhes_item["score"] = score_escolhido

    detalhes_similares = processar_similares(escolhido_data)
    return jsonify({"item": detalhes_item, "similares": detalhes_similares}), 200


@product_bp.route("/salvar_produto", methods=["POST"])
@login_required  # Mude de @require_token para @login_required
def salvar_produto():
    dados = request.get_json()
    if not dados or not dados.get("id_api_externa"):
        return jsonify({"success": False, "error": "Dados inválidos"}), 400

    quantidade_para_adicionar = dados.get("quantidade", 1)
    # Pega o ID do usuário logado que o decorador injetou
    usuario_id_logado = request.current_user.id

    try:
        # Busca o produto no carrinho DO USUÁRIO ATUAL
        produto_existente = Produto.query.filter_by(
            id_api_externa=dados["id_api_externa"], usuario_id=usuario_id_logado
        ).first()

        if produto_existente:
            produto_existente.quantidade += quantidade_para_adicionar
            db.session.commit()
            return (
                jsonify(
                    {
                        "success": True,
                        "message": f"{quantidade_para_adicionar} item(ns) adicionado(s) ao carrinho!",
                    }
                ),
                200,
            )
        else:
            novo_produto = Produto(
                usuario_id=usuario_id_logado,  # Associa o produto ao usuário
                id_api_externa=dados["id_api_externa"],
                nome=dados["nome"],
                codigo_referencia=dados["codigo_referencia"],
                url_imagem=dados.get("url_imagem"),
                preco_original=float(dados.get("preco_original", 0.0)),
                preco_final=float(dados.get("preco_final", 0.0)),
                desconto=float(dados.get("desconto", 0.0)),
                marca=dados["marca"],
                quantidade=quantidade_para_adicionar,
            )
            db.session.add(novo_produto)
            db.session.commit()
            return (
                jsonify(
                    {"success": True, "message": "Produto adicionado ao carrinho!"}
                ),
                201,
            )

    except Exception as e:
        db.session.rollback()
        db.session.rollback()
        print(f"Erro ao salvar produto: {e}")
        return (
            jsonify(
                {"success": False, "error": "Ocorreu um erro ao salvar o produto."}
            ),
            500,
        )


@product_bp.route("/carrinho", methods=["GET"])
@login_required # Mude de @require_token para @login_required
def get_produtos_carrinho():
    try:
        # Busca apenas os produtos do usuário logado
        produtos = Produto.query.filter_by(usuario_id=request.current_user.id).all()
        produtos_json = [p.to_dict() for p in produtos]
        return jsonify({"success": True, "produtos": produtos_json}), 200
    except Exception as e:
        print(f"Erro ao buscar produtos do carrinho: {e}")
        return jsonify({"success": False, "error": "Erro interno do servidor"}), 500


@product_bp.route("/carrinho/produto/remover", methods=["POST"])
@login_required # Mude de @require_token para @login_required
def remover_produto_carrinho():
    dados = request.get_json()
    if not dados or "id_api_externa" not in dados:
        return jsonify({"success": False, "error": "ID do produto não fornecido."}), 400

    try:
        # Busca o produto para remover NO CARRINHO DO USUÁRIO ATUAL
        produto_para_remover = Produto.query.filter_by(
            id_api_externa=dados["id_api_externa"],
            usuario_id=request.current_user.id
        ).first()

        if not produto_para_remover:
            return jsonify({"success": False, "error": "Produto não encontrado no carrinho."}), 404
        

        db.session.delete(produto_para_remover)
        db.session.commit()

        return (
            jsonify({"success": True, "message": "Produto removido do carrinho."}),
            200,
        )
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao remover produto do carrinho: {e}")
        return jsonify({"success": False, "error": "Erro interno do servidor"}), 500


@product_bp.route("/carrinho/produto/atualizar-quantidade", methods=["POST"])
@login_required 
def atualizar_quantidade_produto():
    dados = request.get_json() or {}
    id_api_externa = dados.get("id_api_externa")
    quantidade = dados.get("quantidade")

    if id_api_externa is None:
        return jsonify({"success": False, "error": "ID do produto não fornecido."}), 400
    if quantidade is None:
        return jsonify({"success": False, "error": "Quantidade não fornecida."}), 400

    # Sanitização
    try:
        quantidade = int(quantidade)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Quantidade inválida."}), 400

    try:
        # Busca o produto para atualizar NO CARRINHO DO USUÁRIO ATUAL
        produto = Produto.query.filter_by(
            id_api_externa=dados.get("id_api_externa"),
            usuario_id=request.current_user.id
        ).first()
        
        if not produto:
            return jsonify({"success": False, "error": "Produto não encontrado no carrinho."}), 404
            

        if quantidade <= 0:
            db.session.delete(produto)
            db.session.commit()
            return (
                jsonify(
                    {
                        "success": True,
                        "message": "Produto removido do carrinho.",
                        "removido": True,
                    }
                ),
                200,
            )

        produto.quantidade = quantidade
        db.session.commit()
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Quantidade atualizada com sucesso.",
                    "produto": produto.to_dict(),
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        print(f"Erro ao atualizar quantidade: {e}")
        return jsonify({"success": False, "error": "Erro interno do servidor"}), 500
