def processar_similares(produto):
    similares_data = []
    for sim in produto.get("similares", []):
        similares_data.append({
            "id": sim.get("id"),
            "logoMarca": sim.get("logoMarca"),
            "marca": sim.get("marca"),
            "codigoReferencia": sim.get("codigoReferencia")
        })

    produtos_parcialmente_similares = []
    for ps in produto.get("produtosParcialmenteSimilares", []):
        produtos_parcialmente_similares.append({
            "codigoReferencia": ps.get("codigoReferencia"),
            "marca": ps.get("marca"),
            "nomeProduto": ps.get("nomeProduto")
        })

    return {
        "similares": similares_data,
        "produtosParcialmenteSimilares": produtos_parcialmente_similares,
        "produtosSistemasFilhos": produto.get("produtosSistemasFilhos", []),
        "produtosSistemasPais": produto.get("produtosSistemasPais", [])
    }