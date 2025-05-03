import json
import heapq
from geopy.distance import geodesic
from pathlib import Path

ARQUIVO_JSON = Path(__file__).resolve().parents[1] / "data" / "oficinas.json"
ORIGEM_NOME = "Loja Brigadeiro"
ORIGEM_COORDS = (-23.564953, -46.647019)

def carregar_oficinas():
    with open(ARQUIVO_JSON, encoding='utf-8') as f:
        return json.load(f)

def calcular_distancia(coord1, coord2):
    return round(geodesic(coord1, coord2).km, 2)

def dijkstra(origem, destinos):
    grafo = {origem["nome"]: {}}
    todos = [origem] + destinos
    for i, origem in enumerate(todos):
        nome_origem = origem["nome"]
        if nome_origem not in grafo:
            grafo[nome_origem] = {}
        for j, destino in enumerate(todos):
            if i != j:
                nome_destino = destino["nome"]
                dist = calcular_distancia(
                    (origem["lat"], origem["lon"]),
                    (destino["lat"], destino["lon"])
                )
                grafo[nome_origem][nome_destino] = dist

    visitados = set()
    caminho = []
    atual = origem["nome"]
    total = 0

    while len(visitados) < len(destinos):
        visitados.add(atual)
        vizinhos = grafo[atual]
        nao_visitados = {k: v for k, v in vizinhos.items() if k not in visitados}
        if not nao_visitados:
            break
        proximo = min(nao_visitados, key=nao_visitados.get)
        total += nao_visitados[proximo]
        caminho.append(proximo)
        atual = proximo

    return caminho, round(total, 2)

def calcular_rota_entregas():
    oficinas = carregar_oficinas()
    origem = {"nome": ORIGEM_NOME, "lat": ORIGEM_COORDS[0], "lon": ORIGEM_COORDS[1]}
    rota, distancia_total = dijkstra(origem, oficinas)

    retorno = []
    for nome in rota:
        oficina = next((o for o in oficinas if o["nome"] == nome), None)
        if oficina:
            retorno.append({
                "nome": oficina["nome"],
                "endereco": oficina["endereco"],
                "lat": oficina["lat"],
                "lon": oficina["lon"]
            })

    return {
        "origem": {
            "nome": ORIGEM_NOME,
            "lat": ORIGEM_COORDS[0],
            "lon": ORIGEM_COORDS[1]
        },
        "rota": retorno,
        "distancia_total_km": distancia_total
    }