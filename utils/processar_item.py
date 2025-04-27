def processar_item(produto):
    aplicacoes = []
    for app_item in produto.get("aplicacoes", []):
        aplicacoes.append({
            "carroceria": app_item.get("carroceria"),
            "cilindros": app_item.get("cilindros"),
            "combustivel": app_item.get("combustivel"),
            "fabricacaoFinal": app_item.get("fabricacaoFinal"),
            "fabricacaoInicial": app_item.get("fabricacaoInicial"),
            "hp": app_item.get("hp"),
            "id": app_item.get("id"),
            "modelo": app_item.get("modelo"),
            "montadora": app_item.get("montadora"),
            "versao": app_item.get("versao")
        })

    aplicacoes_gerais = []
    for geral in produto.get("aplicacoesGerais", []):
        aplicacoes_gerais.append({
            "codigoReferencia": geral.get("codigoReferencia"),
            "familia": geral.get("familia"),
            "descricao": geral.get("descricao"),
            "subFamilia": geral.get("subFamilia", {}).get("descricao")
        })

    return {
        "nomeProduto": produto.get("nomeProduto"),
        "marca": produto.get("marca"),
        "imagemReal": produto.get("imagemReal"),
        "logomarca": produto.get("logoMarca"),
        "score": produto.get("score"),
        "aplicacoes": aplicacoes,
        "aplicacoesGerais": aplicacoes_gerais
    }