def processar_similares(produto):
    similares_data = [{
        "id": sim.get("id"),
        "logoMarca": sim.get("logoMarca"),
        "marca": sim.get("marca"),
        "confiavel": sim.get("confiavel"),
        "descontinuado": sim.get("descontinuado"),
        "codigoReferencia": sim.get("codigoReferencia")
    } for sim in produto.get("similares", [])]

    produtos_parcialmente_similares = [{
        "codigoReferencia": ps.get("codigoReferencia"),
        "marca": ps.get("marca"),
        "nomeProduto": ps.get("nomeProduto")
    } for ps in produto.get("produtosParcialmenteSimilares", [])]

    return {
        "similares": similares_data,
        "produtosParcialmenteSimilares": produtos_parcialmente_similares,
        "produtosSistemasFilhos": produto.get("produtosSistemasFilhos", []),
        "produtosSistemasPais": produto.get("produtosSistemasPais", [])
    }