import requests
from Levenshtein import distance as levenshtein_distance

session = requests.Session()

# As outras funções como get_search_results permanecem as mesmas
def get_search_results(token, params):
    """Orquestra a busca principal de produtos com lógica de fallback."""
    termo = params.get("produto", "").lower()
    placa = params.get("placa", "")
    marca = params.get("marca", "").lower()
    ordem = params.get("ordem", "asc").lower() == "asc"
    pagina = int(params.get("pagina", 1))
    itens_por_pagina = 15
    
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    produtos_brutos = []
    mensagem_busca = ""
    tipo_mensagem = ""

    if placa:
        payload = {"produtoFiltro": {"nomeProduto": termo}, "veiculoFiltro": {"veiculoPlaca": placa}, "pagina": 0, "itensPorPagina": 500}
        res = session.post("https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao/catalogo/produtos/query", headers=headers, json=payload)
        if res.status_code == 200:
            produtos_brutos = res.json().get("pageResult", {}).get("data", [])
            if produtos_brutos:
                mensagem_busca = f"Exibindo resultados compatíveis com a placa '{placa}'."
                tipo_mensagem = "success"
    
    if not produtos_brutos:
        payload = {"produtoFiltro": {"nomeProduto": termo}, "pagina": 0, "itensPorPagina": 500}
        res = session.post("https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao/catalogo/produtos/query", headers=headers, json=payload)
        if res.status_code == 200:
            produtos_genericos = res.json().get("pageResult", {}).get("data", [])
            if placa and produtos_genericos:
                mensagem_busca = f"Não encontramos resultados para a placa '{placa}'. Exibindo resultados gerais."
                tipo_mensagem = "info"
            produtos_brutos = produtos_genericos
        else:
            raise Exception("Erro ao buscar produtos na API externa.")

    # O import de tratar_dados e ordenar_produtos deve estar aqui
    from utils.preprocess import tratar_dados
    from utils.sort import ordenar_produtos
    produtos_tratados = tratar_dados(produtos_brutos)
    
    marcas_disponiveis = sorted(set(p.get("marca", "") for p in produtos_tratados if p.get("marca")))
    resultados_filtrados = [p for p in produtos_tratados if not marca or p.get("marca", "").lower() == marca]
    resultados_ordenados = ordenar_produtos(resultados_filtrados, asc=ordem, key_func=lambda x: x.get('nome', '').lower())
    
    total_itens = len(resultados_ordenados)
    total_paginas = (total_itens + itens_por_pagina - 1) // itens_por_pagina if itens_por_pagina > 0 else 0
    inicio = (pagina - 1) * itens_por_pagina
    fim = inicio + itens_por_pagina

    return {
        "marcas": marcas_disponiveis,
        "dados": resultados_ordenados[inicio:fim],
        "pagina": pagina, "total_paginas": total_paginas, "proxima_pagina": pagina < total_paginas,
        "mensagem_busca": mensagem_busca, "tipo_mensagem": tipo_mensagem
    }


def get_autocomplete_suggestions(token, prefix, placa=None):
    """Busca sugestões em duas APIs e as ordena por relevância, priorizando a placa."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # --- 1. BUSCA GENÉRICA (SUPERBUSCA) - GARANTE QUE SEMPRE TENHAMOS SUGESTÕES ---
    sugestoes_genericas = set()
    url_super = "https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao/catalogo/v2/produtos/query/sumario"
    payload_super = {"superbusca": prefix, "pagina": 0, "itensPorPagina": 20}
    res_super = session.post(url_super, headers=headers, json=payload_super)
    if res_super.status_code == 200:
        produtos = res_super.json().get("pageResult", {}).get("data", [])
        for p in produtos:
            nome = p.get("data", {}).get("nomeProduto", "").strip()
            if nome:
                sugestoes_genericas.add(nome.lower())

    # --- 2. BUSCA ESPECIALIZADA (COM PLACA) - PARA RELEVÂNCIA MÁXIMA ---
    nomes_produtos_especificos = set()
    if placa:
        url_query = "https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao/catalogo/produtos/query"
        payload_query = {"produtoFiltro": {"nomeProduto": prefix}, "veiculoFiltro": {"veiculoPlaca": placa}, "pagina": 0, "itensPorPagina": 20}
        res_query = session.post(url_query, headers=headers, json=payload_query)
        if res_query.status_code == 200:
            produtos = res_query.json().get("pageResult", {}).get("data", [])
            for p in produtos:
                nome = p.get("data", {}).get("nomeProduto", "").strip()
                if nome:
                    nomes_produtos_especificos.add(nome.lower())
    
    # --- 3. COMBINAÇÃO E CLASSIFICAÇÃO ---
    todas_as_sugestoes = sugestoes_genericas.union(nomes_produtos_especificos)
    
    sugestoes_com_score = []
    for sugestao in todas_as_sugestoes:
        score = 0
        
        # Prioridade máxima se a sugestão veio da busca específica com placa
        if sugestao in nomes_produtos_especificos:
            score += 1000
        
        if sugestao.lower().startswith(prefix.lower()):
            score += 100
        
        distancia = levenshtein_distance(prefix, sugestao)
        score += 10 / (distancia + 1)
        
        sugestoes_com_score.append((sugestao, score))

    sugestoes_ordenadas = sorted(sugestoes_com_score, key=lambda item: item[1], reverse=True)
    
    # Remove duplicados mantendo a ordem de relevância
    sugestoes_finais = []
    vistos = set()
    for sugestao, score in sugestoes_ordenadas:
        if sugestao not in vistos:
            sugestoes_finais.append(sugestao)
            vistos.add(sugestao)

    return sugestoes_finais[:10]