# utils/processar_item.py
import hashlib
import random

def _calcular_precos_simulados(produto: dict):
    """
    Gera preços determinísticos por produto.
    Usa MD5(seed) para seed do Random (estável entre execuções).
    """
    seed_str = str(produto.get("id") or produto.get("nomeProduto") or "SEM_ID")
    seed_int = int(hashlib.md5(seed_str.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed_int)

    # Escolhe uma faixa de preço base (simula diferentes categorias de item)
    faixas = [
        (79.90, 199.90),
        (200.00, 499.90),
        (500.00, 999.90),
        (1000.00, 1999.90),
    ]
    faixa = rng.choice(faixas)
    preco_base = round(rng.uniform(*faixa), 2)

    # Desconto em % (pode ser zero)
    desconto_percentual = rng.choice([0, 5, 7, 9, 12, 15])
    preco_final = round(preco_base * (1 - desconto_percentual / 100.0), 2)

    # Parcelamento padrão em 12x
    qtd_parcelas = 12
    valor_parcela = round(preco_final / qtd_parcelas, 2)

    return {
        "precoOriginal": preco_base,
        "descontoPercentual": desconto_percentual,
        "preco": preco_final,
        "parcelas": {"qtd": qtd_parcelas, "valor": valor_parcela},
    }


def processar_item(produto):
    aplicacoes = [{
        "carroceria": app.get("carroceria"),
        "cilindros": app.get("cilindros"),
        "combustivel": app.get("combustivel"),
        "fabricacaoFinal": app.get("fabricacaoFinal"),
        "fabricacaoInicial": app.get("fabricacaoInicial"),
        "hp": app.get("hp"),
        "id": app.get("id"),
        "linha": app.get("linha"),
        "modelo": app.get("modelo"),
        "montadora": app.get("montadora"),
        "versao": app.get("versao"),
        "geracao": app.get("geracao"),
        "imagem": app.get("imagem"),
        "motor": app.get("motor")
    } for app in produto.get("aplicacoes", [])]

    familia = produto.get("familia", {})
    familia_obj = {
        "descricao": familia.get("descricao"),
        "id": familia.get("id"),
        "subFamiliaDescricao": familia.get("subFamilia", {}).get("descricao")
    } if familia else {}

    precos = _calcular_precos_simulados(produto)

    return {
        "nomeProduto": produto.get("nomeProduto"),
        "id": produto.get("id"),
        "marca": produto.get("marca"),
        "codigoReferencia": produto.get("codigoReferencia"), # <--- LINHA ADICIONADA
        "imagemReal": produto.get("imagemReal"),
        "logomarca": produto.get("logoMarca"),
        "score": produto.get("score"),
        "aplicacoes": aplicacoes,
        "familia": familia_obj,
        **precos
    }