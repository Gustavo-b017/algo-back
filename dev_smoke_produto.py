#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smoke test de BUSCA DE PRODUTO (baseado no dev_smoke.py):
- Autentica no SSO (client_credentials)
- Valida API local (/health e /)
- Exercita /pesquisar (com termo) e valida ordenações por preço
- Exercita /produto_detalhes para o primeiro item retornado
- Loga erros com corpo e "código de erro" (HTTP ou exceção)

Uso:
  BASE_URL=http://127.0.0.1:5000 python dev_smoke_produto.py --termo "disco"
  python dev_smoke_produto.py --termo "pastilha de freio" --itens 10
  python dev_smoke_produto.py --termo amortecedor --ordenar-por score --ordem desc

Requisitos:
  pip install requests python-dotenv (opcional, só para carregar .env)
ENVs esperadas:
  AUTH_TOKEN_URL, AUTH_CLIENT_ID, AUTH_CLIENT_SECRET
  BASE_URL (opcional; default: http://127.0.0.1:5000)
"""
import os
import sys
import json
import time
import argparse
import requests

try:
    from dotenv import load_dotenv  # opcional
    load_dotenv()
except Exception:
    pass

BASE = os.getenv("BASE_URL", "http://127.0.0.1:5000")

def _mask(s, keep=4):
    if not s:
        return ""
    s = str(s)
    if len(s) <= keep:
        return "*" * len(s)
    return s[:keep] + "*" * (len(s) - keep)

def _env(name, default=None):
    v = os.getenv(name, default)
    return v.strip() if isinstance(v, str) else v

def get(path, **params):
    try:
        r = requests.get(f"{BASE}{path}", params=params, timeout=25)
        body = None
        if r.content:
            try:
                body = r.json()
            except ValueError:
                body = r.text[:1000]
        return r.status_code, body
    except requests.exceptions.RequestException as e:
        return None, {"erro": str(e), "codigo_erro": e.__class__.__name__}

def post(path, payload):
    try:
        r = requests.post(
            f"{BASE}{path}",
            json=payload,
            timeout=30,
            headers={"Content-Type": "application/json"},
        )
        body = None
        if r.content:
            try:
                body = r.json()
            except ValueError:
                body = r.text[:1500]
        return r.status_code, body
    except requests.exceptions.RequestException as e:
        return None, {"erro": str(e), "codigo_erro": e.__class__.__name__}

def assert_true(cond, msg):
    if not cond:
        print(f"[FALHA] {msg}")
        sys.exit(2)
    else:
        print(f"[OK] {msg}")

def sorted_ok(vals, asc=True):
    arr = [v for v in vals if isinstance(v, (int, float))]
    return arr == sorted(arr) if asc else arr == sorted(arr, reverse=True)

def validar_env_auth():
    url = _env("AUTH_TOKEN_URL")
    cid = _env("AUTH_CLIENT_ID")
    csec = _env("AUTH_CLIENT_SECRET")
    issues = []
    if not url: issues.append("AUTH_TOKEN_URL ausente")
    if not cid: issues.append("AUTH_CLIENT_ID ausente")
    if not csec: issues.append("AUTH_CLIENT_SECRET ausente")
    if cid and ("\n" in cid or "\r" in cid):
        issues.append("AUTH_CLIENT_ID contém quebra de linha — precisa estar em UMA linha")
    print("== ENVs de autenticação ==")
    print(json.dumps({
        "AUTH_TOKEN_URL": url,
        "AUTH_CLIENT_ID_preview": _mask(cid, keep=8),
        "AUTH_CLIENT_SECRET_preview": _mask(csec, keep=4),
        "issues": issues,
    }, ensure_ascii=False, indent=2))
    return len(issues) == 0

def autenticar_sso(timeout=25.0):
    url = _env("AUTH_TOKEN_URL")
    cid = _env("AUTH_CLIENT_ID")
    csec = _env("AUTH_CLIENT_SECRET")
    if not (url and cid and csec):
        return {"ok": False, "erro": "Variáveis de ambiente incompletas", "codigo_erro": "EnvError"}
    data = {"grant_type": "client_credentials", "client_id": cid, "client_secret": csec}
    try:
        r = requests.post(url, data=data, headers={"Content-Type":"application/x-www-form-urlencoded"}, timeout=timeout)
        ctype = r.headers.get("content-type","")
        if not r.ok:
            corpo = r.text[:800]
            return {"ok": False, "status": r.status_code, "erro": f"SSO HTTP {r.status_code}", "corpo": corpo, "codigo_erro":"HTTPError"}
        try:
            j = r.json()
        except ValueError:
            return {"ok": False, "status": r.status_code, "erro":"SSO não retornou JSON", "corpo": r.text[:800], "codigo_erro":"JSONDecodeError"}
        token = j.get("access_token")
        if not token:
            return {"ok": False, "status": r.status_code, "erro":"JSON sem access_token", "corpo": j, "codigo_erro":"NoToken"}
        return {"ok": True, "token": token, "token_type": j.get("token_type"), "expires_in": j.get("expires_in")}
    except requests.exceptions.RequestException as e:
        return {"ok": False, "erro": str(e), "codigo_erro": e.__class__.__name__}

def main():
    parser = argparse.ArgumentParser(description="Smoke test de busca de produto via API local")
    parser.add_argument("--termo", default="disco", help="termo de busca (ex.: 'disco')")
    parser.add_argument("--itens", type=int, default=10, help="itens por página (quando suportado)")
    parser.add_argument("--ordenar-por", default="score", choices=["score","maior_preco","menor_preco"], help="campo de ordenação")
    parser.add_argument("--ordem", default="desc", choices=["asc","desc"], help="ordem de ordenação")
    parser.add_argument("--placa", default=None, help="placa do veículo (opcional, se suportado pela rota)")
    parser.add_argument("--ultimo-nivel-id", default=None, help="id da categoria/árvore (opcional)")
    args = parser.parse_args()

    print(f"== Smoke test em {BASE} ==")

    # 0) Autenticação SSO (validação independente do decorador)
    ok_env = validar_env_auth()
    if not ok_env:
        print("[FALHA] Ajuste as variáveis de ambiente acima e rode novamente.")
        sys.exit(2)

    auth = autenticar_sso()
    print("== Resultado da autenticação ==")
    print(json.dumps({k:v for k,v in auth.items() if k != "token"}, ensure_ascii=False, indent=2))
    assert_true(auth.get("ok") is True, "SSO: token obtido com sucesso")

    # 1) /health
    sc, body = get("/health")
    assert_true(sc == 200 and isinstance(body, dict) and body.get("status") == "ok", "/health OK")

    # 2) / (raiz)
    sc, body = get("/")
    assert_true(sc == 200, "rota raiz OK")

    # 3) /pesquisar com termo e ordenação pedidas
    params = {
        "termo": args.termo,
        "ordenar_por": args.ordenar_por,
        "ordem": args.ordem,
    }
    if args.placa: params["placa"] = args.placa
    if args.ultimo_nivel_id: params["ultimo_nivel_id"] = args.ultimo_nivel_id

    sc, body = get("/pesquisar", **params)
    if sc != 200:
        print("[ERRO] /pesquisar retornou erro")
        print(json.dumps({"status": sc, "body": body}, ensure_ascii=False, indent=2))
        sys.exit(2)

    assert_true(isinstance(body, dict) and isinstance(body.get("dados"), list), "/pesquisar retornou lista")
    dados = body["dados"]
    assert_true(len(dados) > 0, f"há itens na pesquisa por '{args.termo}'")
    print(f"[INFO] primeiros 1-2 itens:")
    print(json.dumps(dados[:2], ensure_ascii=False, indent=2))

    # 3.1) Teste de ordenação por preço
    sc, body = get("/pesquisar", termo=args.termo, ordenar_por="maior_preco")
    assert_true(sc == 200, "maior_preco HTTP 200")
    vals = [it.get("preco") for it in (body.get("dados") or []) if isinstance(it.get("preco"), (int, float))]
    if len(vals) >= 2:
        assert_true(sorted_ok(vals, asc=False), "ordenado por maior_preco (desc)")
    else:
        print("[AVISO] poucos itens numéricos para validar maior_preco — pulando checagem")

    sc, body = get("/pesquisar", termo=args.termo, ordenar_por="menor_preco")
    assert_true(sc == 200, "menor_preco HTTP 200")
    vals = [it.get("preco") for it in (body.get("dados") or []) if isinstance(it.get("preco"), (int, float))]
    if len(vals) >= 2:
        assert_true(sorted_ok(vals, asc=True), "ordenado por menor_preco (asc)")
    else:
        print("[AVISO] poucos itens numéricos para validar menor_preco — pulando checagem")

    # 4) Detalhar primeiro item
    sc, body = get("/pesquisar", termo=args.termo, ordenar_por="score", ordem="desc")
    first = next((x for x in (body.get("dados") or []) if x.get("id")), None)
    assert_true(first is not None, "tem item com 'id' para detalhar")

    params_det = {
        "id": first["id"],
        "nomeProduto": first.get("nome") or "",
        "codigoReferencia": first.get("codigoReferencia") or "",
        "marca": first.get("marca") or "",
    }
    sc, det = get("/produto_detalhes", **params_det)
    if sc != 200:
        print("[ERRO] /produto_detalhes retornou erro")
        print(json.dumps({"status": sc, "body": det}, ensure_ascii=False, indent=2))
        sys.exit(2)
    assert_true(isinstance(det.get("item"), dict), "/produto_detalhes OK")
    print("[INFO] detalhe (campos principais):")
    slim = {k: det["item"].get(k) for k in ("id", "nome", "preco", "marca", "score") if k in det["item"]}
    print(json.dumps(slim, ensure_ascii=False, indent=2))

    print("== Smoke test de produto finalizado com sucesso ==")

if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.RequestException as e:
        print(json.dumps({"erro": str(e), "codigo_erro": e.__class__.__name__}, ensure_ascii=False, indent=2))
        sys.exit(2)
