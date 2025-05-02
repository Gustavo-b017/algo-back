import heapq
import json
from geopy.distance import geodesic
from pathlib import Path

# Coordenadas FIAP Paulista
FIAP_COORDS = (-23.564372, -46.653923)
JSON_PATH = Path(__file__).resolve().parents[1] / "data" / "lojas.json"


def carregar_lojas():
    with open(JSON_PATH, encoding='utf-8') as f:
        return json.load(f)

def calcular_distancia(p1, p2):
    return round(geodesic(p1, p2).km, 2)

def construir_grafo(lojas, origem):
    grafo = {str(origem): {}}
    for loja in lojas:
        dist = calcular_distancia(origem, (loja["lat"], loja["lon"]))
        grafo[str(origem)][loja["nome"]] = dist
        grafo[loja["nome"]] = {str(origem): dist}
    return grafo

def dijkstra(grafo, inicio):
    distancias = {n: float("inf") for n in grafo}
    distancias[str(inicio)] = 0
    caminho = {}
    fila = [(0, str(inicio))]

    while fila:
        dist_atual, atual = heapq.heappop(fila)
        for vizinho, peso in grafo[atual].items():
            nova_dist = dist_atual + peso
            if nova_dist < distancias[vizinho]:
                distancias[vizinho] = nova_dist
                caminho[vizinho] = atual
                heapq.heappush(fila, (nova_dist, vizinho))

    return distancias, caminho

def obter_melhor_rota():
    lojas = carregar_lojas()
    grafo = construir_grafo(lojas, FIAP_COORDS)
    distancias, caminhos = dijkstra(grafo, FIAP_COORDS)

    # Identificar loja mais próxima
    loja_mais_proxima = min(lojas, key=lambda loja: distancias[loja["nome"]])
    nome = loja_mais_proxima["nome"]
    return {
        "loja": nome,
        "endereco": loja_mais_proxima["endereco"],
        "coordenadas": [loja_mais_proxima["lat"], loja_mais_proxima["lon"]],
        "distancia_km": distancias[nome]
    }