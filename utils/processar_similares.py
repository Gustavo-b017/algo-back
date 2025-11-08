# utils/processar_similares.py
"""
Processamento de relações de similaridade entre produtos
----------------------------------------------------------------------
Normaliza campos de produtos “similares” e “parcialmente similares”
vindos do provedor externo para um formato padronizado consumido pelo
restante da aplicação (rotas e frontend).

Contrato (saída de `processar_similares`):
{
    "similares": [ { id, logoMarca, marca, confiavel, descontinuado, codigoReferencia }, ... ],
    "produtosParcialmenteSimilares": [ { codigoReferencia, marca, nomeProduto }, ... ],
    "produtosSistemasFilhos": [...],
    "produtosSistemasPais":  [...]
}
Observação: Não há I/O externo; apenas transformação local de dicionários.
"""


def processar_similares(produto):
    """Extrai e padroniza listas de produtos similares/parcialmente similares.

    Args:
        produto (dict): Payload bruto do provedor contendo os campos:
            - "similares": lista de itens com diversos atributos.
            - "produtosParcialmenteSimilares": lista com código/marca/nome.
            - "produtosSistemasFilhos" / "produtosSistemasPais": listas auxiliares.

    Returns:
        dict: Estrutura padronizada com as chaves:
            - "similares": lista de dicts com campos essenciais.
            - "produtosParcialmenteSimilares": lista de dicts com campos essenciais.
            - "produtosSistemasFilhos": lista conforme origem.
            - "produtosSistemasPais": lista conforme origem.
    """
    # Seleciona somente os campos relevantes de cada "similar".
    similares_data = [{
        "id": sim.get("id"),
        "logoMarca": sim.get("logoMarca"),
        "marca": sim.get("marca"),
        "confiavel": sim.get("confiavel"),
        "descontinuado": sim.get("descontinuado"),
        "codigoReferencia": sim.get("codigoReferencia")
    } for sim in produto.get("similares", [])]

    # Para “parcialmente similares”, mantemos identificação básica.
    produtos_parcialmente_similares = [{
        "codigoReferencia": ps.get("codigoReferencia"),
        "marca": ps.get("marca"),
        "nomeProduto": ps.get("nomeProduto")
    } for ps in produto.get("produtosParcialmenteSimilares", [])]

    # Retorna estrutura coerente com o consumo do frontend/rotas.
    return {
        "similares": similares_data,
        "produtosParcialmenteSimilares": produtos_parcialmente_similares,
        "produtosSistemasFilhos": produto.get("produtosSistemasFilhos", []),
        "produtosSistemasPais": produto.get("produtosSistemasPais", [])
    }
