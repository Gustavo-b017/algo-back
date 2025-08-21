import requests
from Levenshtein import distance as levenshtein_distance

session = requests.Session()

# Reintroduzimos o AutocompleteAdaptativo para gerenciar o índice em memória
from utils.autocomplete_adaptativo import AutocompleteAdaptativo
autocomplete_engine = AutocompleteAdaptativo()


def get_autocomplete_suggestions(token, prefix, placa=None):
    """
    Nova lógica de autocomplete: busca em duas APIs, trata os dados,
    indexa e retorna as sugestões mais relevantes.
    """
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    produtos_brutos = []

    # 1. FAZ A REQUISIÇÃO EM 2 APIs PARA OBTER DADOS RICOS
    
    # API 1: Busca principal (mais detalhada)
    payload_query = {"produtoFiltro": {"nomeProduto": prefix}, "pagina": 0, "itensPorPagina": 50}
    if placa:
        payload_query["veiculoFiltro"] = {"veiculoPlaca": placa}
    res_query = session.post("https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao/catalogo/produtos/query", headers=headers, json=payload_query)
    if res_query.status_code == 200:
        produtos_brutos.extend(res_query.json().get("pageResult", {}).get("data", []))

    # API 2: Superbusca (mais rápida, para termos genéricos)
    payload_super = {"superbusca": prefix, "pagina": 0, "itensPorPagina": 50}
    if placa:
        payload_super["veiculoFiltro"] = {"veiculoPlaca": placa}
    res_super = session.post("https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao/catalogo/v2/produtos/query/sumario", headers=headers, json=payload_super)
    if res_super.status_code == 200:
        produtos_brutos.extend(res_super.json().get("pageResult", {}).get("data", []))

    # 2. TRATAMENTO DE DADOS SIMPLIFICADO
    # Mantém apenas nome, código e adiciona um marcador se veio da busca com placa
    produtos_tratados = []
    ids_vistos = set()
    for item in produtos_brutos:
        data = item.get("data", {})
        produto_id = data.get("id")
        if produto_id and produto_id not in ids_vistos:
            produtos_tratados.append({
                "nome": data.get("nomeProduto", "").strip(),
                "codigoReferencia": data.get("codigoReferencia", "").strip(),
                "marca": data.get("marca", "").strip(),
                "is_specific": "veiculoFiltro" in payload_query # Marca se o resultado é específico da placa
            })
            ids_vistos.add(produto_id)

    # 3. CHAMA O AUTOCOMPLETE (agora como um motor de indexação e busca)
    autocomplete_engine.clear() # Limpa o índice antigo
    autocomplete_engine.build(produtos_tratados) # Constrói um novo índice com os dados frescos
    sugestoes = autocomplete_engine.search(prefix)
    
    # 4. ORDENAÇÃO POR RELEVÂNCIA (CLASSIFICAÇÃO)
    sugestoes_com_score = []
    for sugestao in sugestoes:
        # Encontra o produto original para checar se é específico da placa
        produto_original = next((p for p in produtos_tratados if p["nome"].lower() == sugestao.lower()), None)
        score = 0
        
        if produto_original and produto_original["is_specific"]:
            score += 100 # Prioridade máxima para produtos compatíveis com a placa

        if sugestao.lower().startswith(prefix.lower()):
            score += 10
        
        distancia = levenshtein_distance(prefix, sugestao)
        score += 1 / (distancia + 1)
        
        sugestoes_com_score.append((sugestao, score))

    sugestoes_ordenadas = sorted(sugestoes_com_score, key=lambda item: item[1], reverse=True)
    
    return [sugestao for sugestao, score in sugestoes_ordenadas]

# A função de busca principal não precisa mais existir aqui,
# pois a lógica de fallback já está no app.py e funcionando bem.
# Manter o código enxuto e focado.