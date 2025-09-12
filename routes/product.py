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

    filtro = {}
    # Priorize filtros mais precisos
    if codigo_referencia:
        filtro["codigoReferencia"] = codigo_referencia
    if marca:
        filtro["nomeFabricante"] = marca
    if produto_id:
        filtro["id"] = produto_id
    if nome_produto:
        filtro["nomeProduto"] = nome_produto

    # A função buscar_produtos já lida com o dicionário de filtro,
    # então basta passar o filtro aprimorado
    resp = search_service_instance.buscar_produtos(
        request.token, filtro_produto=filtro, itens_por_pagina=50
    )
    itens = (resp or {}).get("pageResult", {}).get("data", [])
    if not itens:
        return jsonify({"success": False, "error": "Produto não encontrado."}), 404

    escolhido = None
    if produto_id:
        for it in itens:
            data = it.get("data", {})
            if str(data.get("id")) == str(produto_id):
                escolhido = data
                break
    if not escolhido:
        escolhido = itens[0].get("data", {})

    detalhes_item = processar_item(escolhido)

    # Fallback defensivo: se por algum motivo não vierem os campos de preço, calculamos aqui
    if "preco" not in detalhes_item or "precoOriginal" not in detalhes_item:
        detalhes_item.update(_calcular_precos_simulados(escolhido))

    detalhes_similares = processar_similares(escolhido)
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
        produto_existente = Produto.query.filter_by(id_api_externa=dados["id_api_externa"]).first()

        if produto_existente:
            # Se existe, incrementa a quantidade com o valor recebido
            produto_existente.quantidade += quantidade_para_adicionar
            db.session.commit()
            return jsonify({"success": True, "message": f"{quantidade_para_adicionar} item(ns) adicionado(s) ao carrinho!"}), 200
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
                quantidade=quantidade_para_adicionar # Define a quantidade inicial
            )
            db.session.add(novo_produto)
            db.session.commit()
            return jsonify({"success": True, "message": "Produto adicionado ao carrinho!"}), 201

    except Exception as e:
        db.session.rollback()
        print(f"Erro ao salvar produto: {e}")
        return jsonify({"success": False, "error": "Ocorreu um erro ao salvar o produto."}), 500


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
    if not dados or 'id_api_externa' not in dados:
        return jsonify({"success": False, "error": "ID do produto não fornecido."}), 400

    try:
        produto_para_remover = Produto.query.filter_by(id_api_externa=dados['id_api_externa']).first()
        
        if not produto_para_remover:
            return jsonify({"success": False, "error": "Produto não encontrado no carrinho."}), 404

        db.session.delete(produto_para_remover)
        db.session.commit()

        return jsonify({"success": True, "message": "Produto removido do carrinho."}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao remover produto do carrinho: {e}")
        return jsonify({"success": False, "error": "Erro interno do servidor"}), 500
