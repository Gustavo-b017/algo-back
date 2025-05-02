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
        "motor": app.get("motor")
    } for app in produto.get("aplicacoes", [])]

    familia = produto.get("familia", {})
    familia_obj = {
        "descricao": familia.get("descricao"),
        "id": familia.get("id"),
        "subFamiliaDescricao": familia.get("subFamilia", {}).get("descricao")
    } if familia else {}

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