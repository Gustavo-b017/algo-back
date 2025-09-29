# dev_smoke.py
import os
import sys
import time
import json
import math
import requests

BASE = os.getenv("BASE_URL", "http://127.0.0.1:5000")


def get(path, **params):
    r = requests.get(f"{BASE}{path}", params=params, timeout=20)
    return r.status_code, (r.json() if r.content else None)


def post(path, payload):
    r = requests.post(
        f"{BASE}{path}",
        json=payload,
        timeout=20,
        headers={"Content-Type": "application/json"},
    )
    return r.status_code, (r.json() if r.content else None)


def assert_true(cond, msg):
    if not cond:
        print(f"[FALHA] {msg}")
        sys.exit(1)
    else:
        print(f"[OK] {msg}")


def sorted_ok(vals, asc=True):
    arr = [v for v in vals if v is not None]
    return arr == sorted(arr) if asc else arr == sorted(arr, reverse=True)


def main():
    print(f"== Smoke test em {BASE} ==")

    # 1) /health
    sc, body = get("/health")
    assert_true(sc == 200 and body.get("status") == "ok", "/health OK")

    # 2) /pesquisar com score (relevância)
    sc, body = get("/pesquisar", termo="disco", ordenar_por="score", ordem="desc")
    assert_true(
        sc == 200 and isinstance(body.get("dados"), list), "/pesquisar retornou lista"
    )
    dados = body["dados"]
    assert_true(len(dados) > 0, "há itens na pesquisa por 'disco'")
    # pelo menos um item com score numérico
    tem_score = any(isinstance(it.get("score"), (int, float)) for it in dados)
    assert_true(tem_score, "alguns itens possuem 'score' numérico")

    # 3) Ordenação por maior/menor preço
    sc, body = get("/pesquisar", termo="disco", ordenar_por="maior_preco")
    assert_true(sc == 200, "maior_preco HTTP 200")
    vals = [it.get("preco") for it in body.get("dados", [])]
    # remove None e mantém só numéricos
    vals = [v for v in vals if isinstance(v, (int, float))]
    assert_true(len(vals) >= 2, "lista suficiente para testar ordenação por preço")
    assert_true(sorted_ok(vals, asc=False), "ordenado por maior_preco (desc)")

    sc, body = get("/pesquisar", termo="disco", ordenar_por="menor_preco")
    vals = [
        it.get("preco")
        for it in body.get("dados", [])
        if isinstance(it.get("preco"), (int, float))
    ]
    assert_true(sorted_ok(vals, asc=True), "ordenado por menor_preco (asc)")

    # 4) Detalhe com score
    sc, body = get("/pesquisar", termo="disco", ordenar_por="score", ordem="desc")
    first = next((x for x in body.get("dados", []) if x.get("id")), None)
    assert_true(first is not None, "tem item com 'id' para detalhar")

    # >>> NOVO: envia também nomeProduto / codigoReferencia / marca quando existir
    params = {
        "id": first["id"],
        "nomeProduto": first.get("nome") or "",
        "codigoReferencia": first.get("codigoReferencia") or "",
        "marca": first.get("marca") or "",
    }
    sc, det = get("/produto_detalhes", **params)

    assert_true(sc == 200 and isinstance(det.get("item"), dict), "/produto_detalhes OK")
    assert_true("score" in det["item"], "detalhe contém 'score' (pode ser null)")

    # 5) Carrinho atualizar-quantidade (deve retornar 404 se não existir)
    sc, res = post(
        "/carrinho/produto/atualizar-quantidade",
        {"id_api_externa": 99999999, "quantidade": 2},
    )
    assert_true(sc in (200, 404), "rota atualizar-quantidade responde 200/404")
    if sc == 404:
        print("[OK] atualizar-quantidade retornou 404 para item inexistente (esperado)")
    else:
        print("[OK] atualizar-quantidade atualizou item existente")

    print("== Smoke test finalizado com sucesso ==")


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.RequestException as e:
        print(f"[FALHA] Erro de rede: {e}")
        sys.exit(1)
