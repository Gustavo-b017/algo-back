def tratar_dados(lista):
    return [{
        "nome": item.get("data", {}).get("nomeProduto", "").strip(),
        "marca": item.get("data", {}).get("marca", "").strip(),
        "codigoReferencia": item.get("data", {}).get("codigoReferencia", "").strip(),
        "potencia": item.get("data", {}).get("aplicacoes", [{}])[0].get("hp", "") if item.get("data", {}).get("aplicacoes") else "",
        "ano_inicio": item.get("data", {}).get("aplicacoes", [{}])[0].get("fabricacaoInicial", "") if item.get("data", {}).get("aplicacoes") else "",
        "ano_fim": item.get("data", {}).get("aplicacoes", [{}])[0].get("fabricacaoFinal", "") if item.get("data", {}).get("aplicacoes") else "",
        "id": item.get("data", {}).get("id", "")
    } for item in lista]