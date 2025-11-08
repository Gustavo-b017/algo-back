# utils/preprocess.py
"""
Pré-processamento de resultados de produto
-------------------------------------------------------------------------------
Responsável por transformar a lista heterogênea retornada pelo provedor externo
(em geral uma lista de dicts com a chave "data" ou o próprio dict do item)
em um formato interno padronizado consumido pelo frontend e pelas rotas.

Dependências:
- _calcular_precos_simulados: calcula/estima preço, preço original, desconto e
  parcelamento a partir do payload bruto.
- _gerar_metricas_fake: gera métricas de apoio (avaliacao_media, avaliacoes,
  vendidos) para ordenações quando o provedor não as entrega.

Contrato (saída):
Cada item tratado conterá as chaves:
    nome, marca, codigoReferencia, potencia, ano_inicio, ano_fim, id, imagemReal,
    preco, precoOriginal, descontoPercentual, parcelas,
    score, avaliacao_media, avaliacoes, vendidos.
-------------------------------------------------------------------------------
"""

from utils.processar_item import _calcular_precos_simulados, _gerar_metricas_fake


def tratar_dados(lista):
    """Normaliza itens do catálogo para o formato interno.

    Parâmetros:
        lista (list[dict|Any]): Lista de itens no padrão do provedor.
            - Pode ser uma lista de dicts com a chave "data" (wrapper) ou
              diretamente uma lista de dicts de produto.

    Retorna:
        list[dict]: Lista de itens prontos para consumo por ordenadores/rotas,
        com campos padronizados (ver docstring do módulo).

    Observações:
        - Não lança exceções: assume chaves ausentes e usa defaults seguros.
        - Mantém `score` se vier no wrapper (quando lista contém {"data": ..., "score": ...}).
    """
    tratados = []
    for item in lista:
        # Aceita tanto o wrapper {"data": {...}} quanto o objeto direto {...}
        data = item.get("data", {}) if isinstance(item, dict) else (item or {})

        # Calcula precificação simulada (mantém contrato atual do projeto)
        preco = _calcular_precos_simulados(data)

        # Gera métricas auxiliares para ordenação/ranking (quando o provedor não fornece)
        metricas = _gerar_metricas_fake(data)

        # Monta o registro padronizado consumido pelo restante da aplicação
        tratados.append({
            # Identificação e rótulos básicos
            "nome": (data.get("nomeProduto") or "").strip(),
            "marca": (data.get("marca") or "").strip(),
            "codigoReferencia": (data.get("codigoReferencia") or "").strip(),

            # Atributos de aplicação/compatibilidade (quando presentes)
            "potencia": (data.get("aplicacoes") or [{}])[0].get("hp", ""),
            "ano_inicio": (data.get("aplicacoes") or [{}])[0].get("fabricacaoInicial", ""),
            "ano_fim": (data.get("aplicacoes") or [{}])[0].get("fabricacaoFinal", ""),

            # Identificadores e mídia
            "id": data.get("id", ""),
            "imagemReal": data.get("imagemReal", ""),

            # Precificação (simulada) — mantém chaves usadas pelo frontend
            "preco": preco["preco"],
            "precoOriginal": preco["precoOriginal"],
            "descontoPercentual": preco["descontoPercentual"],
            "parcelas": preco["parcelas"],

            # Score vindo do wrapper (se existir). Se não houver, fica None.
            "score": item.get("score") if isinstance(item, dict) else None,

            # Métricas auxiliares para ordenação
            "avaliacao_media": metricas["avaliacao_media"],
            "avaliacoes": metricas["avaliacoes"],
            "vendidos": metricas["vendidos"],
        })

    return tratados
