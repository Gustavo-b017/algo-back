# utils/preprocess.py
from utils.processar_item import _calcular_precos_simulados, _gerar_metricas_fake

def tratar_dados(lista):
    tratados = []
    for item in lista:
        data = item.get("data", {}) if isinstance(item, dict) else (item or {})
        preco = _calcular_precos_simulados(data)
        metricas = _gerar_metricas_fake(data)

        tratados.append({
            "nome": (data.get("nomeProduto") or "").strip(),
            "marca": (data.get("marca") or "").strip(),
            "codigoReferencia": (data.get("codigoReferencia") or "").strip(),
            "potencia": (data.get("aplicacoes") or [{}])[0].get("hp", ""),
            "ano_inicio": (data.get("aplicacoes") or [{}])[0].get("fabricacaoInicial", ""),
            "ano_fim": (data.get("aplicacoes") or [{}])[0].get("fabricacaoFinal", ""),
            "id": data.get("id", ""),
            "imagemReal": data.get("imagemReal", ""),

            # preços simulados
            "preco": preco["preco"],
            "precoOriginal": preco["precoOriginal"],
            "descontoPercentual": preco["descontoPercentual"],
            "parcelas": preco["parcelas"],

            # NOVO: se o wrapper trouxer score, mantemos
            "score": item.get("score") if isinstance(item, dict) else None,

            # NOVO: métricas para ordenação
            "avaliacao_media": metricas["avaliacao_media"],
            "avaliacoes": metricas["avaliacoes"],
            "vendidos": metricas["vendidos"],
        })
    return tratados
