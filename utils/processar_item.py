# utils/processar_item.py
"""
Processamento de item de catálogo
-------------------------------------------------------------------------------
Este módulo centraliza a padronização de um produto bruto do provedor externo.

Funções:
- _calcular_precos_simulados(produto): gera preços determinísticos por item,
  a partir de uma seed baseada em ID/nome (MD5). Útil para demos e ambientes
  sem preço real.
- _gerar_metricas_fake(produto): gera, de forma determinística, métricas de
  apoio (avaliação, nº de avaliações, vendidos) para ordenação/UX.
- processar_item(produto): normaliza o payload do provedor para o formato
  esperado pelo restante da aplicação (rotas/frontend), agregando preços e
  métricas simuladas.

Observações:
- Determinístico: o uso de MD5 (parcial) como seed mantém valores estáveis
  entre execuções para o mesmo produto.
- Não há I/O externo neste módulo; tudo é cálculo local.
-------------------------------------------------------------------------------
"""

import hashlib
import random


def _calcular_precos_simulados(produto: dict):
    """
    Gera preços determinísticos por produto.
    Usa MD5(seed) para seed do Random (estável entre execuções).

    Args:
        produto (dict): Item bruto do provedor.

    Returns:
        dict: {
            "precoOriginal": float,
            "descontoPercentual": int,
            "preco": float,
            "parcelas": {"qtd": int, "valor": float}
        }
    """
    # Seed baseada em ID ou nome do produto; fallback seguro se ambos ausentes
    seed_str = str(produto.get("id") or produto.get("nomeProduto") or "SEM_ID")
    # Usa os 8 primeiros hex dígitos do MD5 (32 bits) para obter um inteiro estável
    seed_int = int(hashlib.md5(seed_str.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed_int)

    # Escolhe uma faixa de preço base (simula diferentes categorias)
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

    # Parcelamento padrão em 12x (apenas para exibição)
    qtd_parcelas = 12
    valor_parcela = round(preco_final / qtd_parcelas, 2)

    return {
        "precoOriginal": preco_base,
        "descontoPercentual": desconto_percentual,
        "preco": preco_final,
        "parcelas": {"qtd": qtd_parcelas, "valor": valor_parcela},
    }


# >>> NOVO: métricas determinísticas (estáveis por id/nome) <<<
def _gerar_metricas_fake(produto: dict):
    """
    Gera métricas de apoio determinísticas, úteis para ordenação e UX em ambientes
    sem dados reais do provedor (e.g., avaliações/volumes de venda).

    Args:
        produto (dict): Item bruto do provedor.

    Returns:
        dict: {
            "avaliacao_media": float,  # 3.2 a 5.0 (1 casa decimal)
            "avaliacoes": int,         # 5 a 480
            "vendidos": int            # 0 a 12000
        }
    """
    seed_str = str(produto.get("id") or produto.get("nomeProduto") or "SEM_ID")
    base = int(hashlib.md5(seed_str.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(base + 42)  # offset fixo para separar das faixas de preço
    return {
        "avaliacao_media": round(rng.uniform(3.2, 5.0), 1),
        "avaliacoes": rng.randint(5, 480),
        "vendidos": rng.randint(0, 12000),
    }


def processar_item(produto):
    """
    Normaliza um item bruto do provedor para o formato interno esperado.

    Agrega:
      - campos essenciais do produto (nome, marca, código, imagem, etc.);
      - lista de aplicações normalizada;
      - objeto 'familia' com subcampos mais usados;
      - preços simulados (determinísticos);
      - métricas "fake" (determinísticas) para ordenação/UX.

    Args:
        produto (dict): Item bruto retornado pelo provedor externo.

    Returns:
        dict: Payload padronizado consumido por rotas/frontend.
    """
    # Normaliza aplicações: seleciona apenas campos usados pelo frontend
    aplicacoes = [
        {
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
            "motor": app.get("motor"),
        }
        for app in produto.get("aplicacoes", [])
    ]

    # Extrai família com campos mais acessados pelo cliente
    familia = produto.get("familia", {})
    familia_obj = (
        {
            "descricao": familia.get("descricao"),
            "id": familia.get("id"),
            "subFamiliaDescricao": familia.get("subFamilia", {}).get("descricao"),
        }
        if familia
        else {}
    )

    # Precificação simulada (determinística) + métricas de apoio
    precos = _calcular_precos_simulados(produto)
    metricas = _gerar_metricas_fake(produto)   # <<< NOVO

    # Monta o payload final padronizado
    return {
        "nomeProduto": produto.get("nomeProduto"),
        "id": produto.get("id"),
        "marca": produto.get("marca"),
        "codigoReferencia": produto.get("codigoReferencia"),
        "imagemReal": produto.get("imagemReal"),
        "logomarca": produto.get("logoMarca"),
        "score": produto.get("score"),
        "aplicacoes": aplicacoes,
        "familia": familia_obj,
        **precos,
        **metricas,  # <<< NOVO
    }
