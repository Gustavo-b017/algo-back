def tratar_dados(lista):
    tratados = []
    for item in lista:
        data = item.get("data", {})
        nome = data.get("nomeProduto", "")
        marca = data.get("marca", "")
        codigo = data.get("codigoReferencia", "")
        aplicacoes = data.get("aplicacoes", [])
        if aplicacoes:
            potencia = aplicacoes[0].get("hp", "")
            ano_inicio = aplicacoes[0].get("fabricacaoInicial", "")
            ano_fim = aplicacoes[0].get("fabricacaoFinal", "")
        else:
            potencia = ""
            ano_inicio = ""
            ano_fim = ""
        tratados.append({
            "nome": nome.strip(),
            "marca": marca.strip(),
            "codigo": codigo,
            "potencia": potencia,
            "ano_inicio": ano_inicio,
            "ano_fim": ano_fim
        })
    return tratados