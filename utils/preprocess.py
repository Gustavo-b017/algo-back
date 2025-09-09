# utils/preprocess.py
from utils.processar_item import _calcular_precos_simulados  # <— reusa o mesmo algoritmo

def tratar_dados(lista):
    tratados = []
    for item in lista:
        data = item.get("data", {})
        preco = _calcular_precos_simulados(data)  # seed por id/nomeProduto

        tratados.append({
            "nome": data.get("nomeProduto", "").strip(),
            "marca": data.get("marca", "").strip(),
            "codigoReferencia": data.get("codigoReferencia", "").strip(),
            "potencia": (data.get("aplicacoes") or [{}])[0].get("hp", ""),
            "ano_inicio": (data.get("aplicacoes") or [{}])[0].get("fabricacaoInicial", ""),
            "ano_fim": (data.get("aplicacoes") or [{}])[0].get("fabricacaoFinal", ""),
            "id": data.get("id", ""),
            "imagemReal": data.get("imagemReal", ""),
            # ↓ novos campos usados nos cards
            "preco": preco["preco"],
            "precoOriginal": preco["precoOriginal"],
            "descontoPercentual": preco["descontoPercentual"],
            "parcelas": preco["parcelas"],
        })
    return tratados
