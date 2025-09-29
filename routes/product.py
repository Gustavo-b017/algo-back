# product.py
from flask import Blueprint, jsonify, request
from utils.processar_item import processar_item, _calcular_precos_simulados
from decorators.token_decorator import require_token
from utils.processar_similares import processar_similares
from services.search_service import search_service_instance

# Importe a instância do db da nova pasta
from database.__init__ import db
from database.models import Produto

product_bp = Blueprint("product", __name__)


@product_bp.route("/produto_detalhes", methods=["GET"])
@require_token
def get_produto_detalhes():
    produto_id = request.args.get("id", type=int)
    nome_produto = (request.args.get("nomeProduto") or "").strip()

    # NOVO: Adicione o codigo de referencia e marca
    codigo_referencia = request.args.get("codigoReferencia", "").strip()
    marca = request.args.get("marca", "").strip()

    if not produto_id and not nome_produto:
        return (
            jsonify({"success": False, "error": "Informe 'id' ou 'nomeProduto'."}),
            400,
        )

    # -- monta filtro, priorizando os mais precisos --
    filtro = {}
    if codigo_referencia:
        filtro["codigoReferencia"] = codigo_referencia
    if marca:
        filtro["nomeFabricante"] = marca
    if produto_id:
        filtro["id"] = produto_id
    if nome_produto:
        filtro["nomeProduto"] = nome_produto

    # chama a busca externa
    resp = search_service_instance.buscar_produtos(
        request.token, filtro_produto=filtro, itens_por_pagina=50
    )
    itens = (resp or {}).get("pageResult", {}).get("data", []) or []
    if not itens:
        return jsonify({"success": False, "error": "Produto não encontrado."}), 404

    # --- NOVO: extrator de score por ID a partir da lista "itens" (brutos) ---
    def _score_map(lista):
        """
        Aceita os dois formatos que a API pode devolver:
          1) {"score": 2.0, "data": {"id": 10915, ...}}
          2) {"id": 10915, "score": 2.0, ...}  # fallback
        Retorna: { id:int -> score: float|None }
        """
        mapa = {}
        for it in lista:
            if not isinstance(it, dict):
                continue
            d = it.get("data")
            if isinstance(d, dict) and d.get("id") is not None:
                mapa[d["id"]] = it.get("score")
            else:
                if it.get("id") is not None and "score" in it:
                    mapa[it["id"]] = it.get("score")
        return mapa

    score_by_id = _score_map(itens)

    # seleciona o item (preferindo o id)
    escolhido_data = None
    if produto_id:
        for it in itens:
            data = it.get("data", {})
            if str(data.get("id")) == str(produto_id):
                escolhido_data = data
                break
    if not escolhido_data:
        escolhido_data = itens[0].get("data", {})

    # processa para o formato consumido pelo front
    detalhes_item = processar_item(escolhido_data)

    # --- NOVO: injeta o score no item (None quando não existir) ---
    escolhido_id = detalhes_item.get("id") or escolhido_data.get("id")
    detalhes_item["score"] = score_by_id.get(escolhido_id)

    # Fallback defensivo: se por algum motivo não vierem os campos de preço, calculamos aqui
    if "preco" not in detalhes_item or "precoOriginal" not in detalhes_item:
        detalhes_item.update(_calcular_precos_simulados(escolhido_data))

    detalhes_similares = processar_similares(escolhido_data)
    return jsonify({"item": detalhes_item, "similares": detalhes_similares})



@product_bp.route("/salvar_produto", methods=["POST"])
@require_token
def salvar_produto():
    dados = request.get_json()
    if not dados or not dados.get("id_api_externa"):
        return jsonify({"success": False, "error": "Dados inválidos"}), 400

    # Captura a quantidade do corpo da requisição, com 1 como padrão
    quantidade_para_adicionar = dados.get("quantidade", 1)

    try:
        produto_existente = Produto.query.filter_by(
            id_api_externa=dados["id_api_externa"]
        ).first()

        if produto_existente:
            # Se existe, incrementa a quantidade com o valor recebido
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
            # Se não existe, cria um novo registro com a quantidade especificada
            novo_produto = Produto(
                id_api_externa=dados["id_api_externa"],
                nome=dados["nome"],
                codigo_referencia=dados["codigo_referencia"],
                url_imagem=dados.get("url_imagem"),
                preco_original=float(dados.get("preco_original", 0.0)),
                preco_final=float(dados.get("preco_final", 0.0)),
                desconto=float(dados.get("desconto", 0.0)),
                marca=dados["marca"],
                quantidade=quantidade_para_adicionar,  # Define a quantidade inicial
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
        print(f"Erro ao salvar produto: {e}")
        return (
            jsonify(
                {"success": False, "error": "Ocorreu um erro ao salvar o produto."}
            ),
            500,
        )


@product_bp.route("/carrinho", methods=["GET"])
@require_token
def get_produtos_carrinho():
    try:
        produtos = Produto.query.all()
        # Agora podemos voltar a usar o to_dict() de forma limpa!
        produtos_json = [p.to_dict() for p in produtos]
        return jsonify({"success": True, "produtos": produtos_json}), 200
    except Exception as e:
        print(f"Erro ao buscar produtos do carrinho: {e}")
        return jsonify({"success": False, "error": "Erro interno do servidor"}), 500


@product_bp.route("/carrinho/produto/remover", methods=["POST"])
@require_token
def remover_produto_carrinho():
    dados = request.get_json()
    if not dados or "id_api_externa" not in dados:
        return jsonify({"success": False, "error": "ID do produto não fornecido."}), 400

    try:
        produto_para_remover = Produto.query.filter_by(
            id_api_externa=dados["id_api_externa"]
        ).first()

        if not produto_para_remover:
            return (
                jsonify(
                    {"success": False, "error": "Produto não encontrado no carrinho."}
                ),
                404,
            )

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
@require_token
def atualizar_quantidade_produto():
    """
    Atualiza a quantidade de um produto no carrinho.
    Body JSON:
      {
        "id_api_externa": <int>,
        "quantidade": <int>   # nova quantidade absoluta
      }
    Regras:
      - Se quantidade <= 0: remove o produto do carrinho.
      - Se produto não existir: 404.
      - Retorna o produto atualizado (quando aplicável).
    """
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
        produto = Produto.query.filter_by(id_api_externa=id_api_externa).first()
        if not produto:
            return (
                jsonify(
                    {"success": False, "error": "Produto não encontrado no carrinho."}
                ),
                404,
            )

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
