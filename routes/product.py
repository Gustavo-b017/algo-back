from flask import Blueprint, jsonify, request
from utils.processar_item import processar_item
from decorators.token_decorator import require_token
from utils.processar_similares import processar_similares
from services.search_service import search_service_instance

# Criamos o nosso Blueprint para as rotas de produto
product_bp = Blueprint('product', __name__)

@product_bp.route("/produto_detalhes", methods=["GET"])
@require_token
def get_produto_detalhes():
    # Parâmetros que o frontend vai enviar
    produto_id = request.args.get("id", type=int)
    nome_produto = request.args.get("nomeProduto", "").strip()

    if not produto_id or not nome_produto:
        return jsonify({"success": False, "error": "Os parâmetros 'id' e 'nomeProduto' são obrigatórios."}), 400

    # Usamos o nosso serviço para buscar o produto
    filtro_produto = {"id": produto_id, "nomeProduto": nome_produto}
    resposta_api = search_service_instance.buscar_produtos(request.token, filtro_produto=filtro_produto, itens_por_pagina=1)

    if not resposta_api or not resposta_api.get("pageResult", {}).get("data"):
        return jsonify({"success": False, "error": "Produto não encontrado."}), 404
    
    produto_bruto = resposta_api.get("pageResult", {}).get("data", [])[0].get("data")

    # Processamos e retornamos TODOS os detalhes de uma só vez
    detalhes_item = processar_item(produto_bruto)
    detalhes_similares = processar_similares(produto_bruto)

    return jsonify({
        "item": detalhes_item,
        "similares": detalhes_similares
    })