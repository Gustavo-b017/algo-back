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
            "linha": app_item.get("linha"),
            "modelo": app_item.get("modelo"),
            "montadora": app_item.get("montadora"),
            "versao": app_item.get("versao"),
            "geracao": app_item.get("geracao"),
            "motor": app_item.get("motor")
        })

    familia = produto.get("familia", {})
    familia_obj = {}
    if familia:
        familia_obj = {
            "descricao": familia.get("descricao"),
            "id": familia.get("id"),
            "subFamiliaDescricao": familia.get("subFamilia", {}).get("descricao")
        }

    return {
        "nomeProduto": produto.get("nomeProduto"),
        "id": produto.get("id"),
        "marca": produto.get("marca"),
        "imagemReal": produto.get("imagemReal"),
        "logomarca": produto.get("logoMarca"),
        "score": produto.get("score"),
        "aplicacoes": aplicacoes,
        "familia": familia_obj
    }
