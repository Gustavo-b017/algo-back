# product.py
from flask import Blueprint, jsonify, request
from utils.processar_item import processar_item, _calcular_precos_simulados
from decorators.token_decorator import require_token
from utils.processar_similares import processar_similares
from services.search_service import search_service_instance

product_bp = Blueprint('product', __name__)

@product_bp.route("/produto_detalhes", methods=["GET"])
@require_token
def get_produto_detalhes():
    produto_id = request.args.get("id", type=int)
    nome_produto = (request.args.get("nomeProduto") or "").strip()
    if not produto_id and not nome_produto:
        return jsonify({"success": False, "error": "Informe 'id' ou 'nomeProduto'."}), 400

    filtro = {}
    if produto_id: filtro["id"] = produto_id
    if nome_produto: filtro["nomeProduto"] = nome_produto

    resp = search_service_instance.buscar_produtos(request.token, filtro_produto=filtro, itens_por_pagina=50)
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
