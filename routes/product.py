# product.py
from flask import Blueprint, jsonify, request
from utils.processar_item import processar_item, _calcular_precos_simulados
from decorators.token_decorator import require_token
from utils.processar_similares import processar_similares
from services.search_service import search_service_instance

# Importe a instância do db da nova pasta
from database.__init__ import db
from database.models import Produto

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

@product_bp.route("/salvar_produto", methods=["POST"])
@require_token
def salvar_produto():
    dados = request.get_json()
    if not dados:
        return jsonify({"success": False, "error": "Dados inválidos"}), 400

    try:
        # Pega as informações do JSON e garante que os campos numéricos sejam convertidos
        nome = dados.get('nome')
        codigo = dados.get('codigo_referencia')
        url_imagem = dados.get('url_imagem')
        
        # Converte para float, tratando possíveis valores nulos ou inválidos como 0.0
        preco_original = float(dados.get('preco_original', 0.0))
        preco_final = float(dados.get('preco_final', 0.0))
        desconto = float(dados.get('desconto', 0.0))
        
        # Adicione uma validação básica para os campos obrigatórios
        if not nome or not codigo:
            return jsonify({"success": False, "error": "Nome do produto ou código de referência são obrigatórios."}), 400

        # Cria uma nova instância do modelo Produto
        novo_produto = Produto(
            nome=nome,
            codigo_referencia=codigo,
            url_imagem=url_imagem,
            preco_original=preco_original,
            preco_final=preco_final,
            desconto=desconto
        )

        # Adiciona ao banco de dados e salva
        db.session.add(novo_produto)
        db.session.commit()

        return jsonify({"success": True, "message": "Produto salvo com sucesso!"}), 201
    
    except Exception as e:
        db.session.rollback()  # Desfaz a operação em caso de erro
        print(f"Erro ao salvar produto: {e}") # Adicionado para depuração
        return jsonify({"success": False, "error": str(e)}), 500

@product_bp.route("/carrinho", methods=["GET"])
@require_token
def get_produtos_carrinho():
    try:
        # Busca todos os produtos da tabela "Produto"
        produtos = Produto.query.all()
        
        # Converte os objetos do banco de dados para um formato JSON
        # O SQLAlchemy não converte para JSON automaticamente, então fazemos isso manualmente
        produtos_json = [
            {
                "id": p.id,
                "nome": p.nome,
                "codigo_referencia": p.codigo_referencia,
                "url_imagem": p.url_imagem,
                "preco_original": p.preco_original,
                "preco_final": p.preco_final,
                "desconto": p.desconto
            }
            for p in produtos
        ]
        
        return jsonify({"success": True, "produtos": produtos_json}), 200
    except Exception as e:
        print(f"Erro ao buscar produtos do carrinho: {e}")
        return jsonify({"success": False, "error": "Erro interno do servidor"}), 500
