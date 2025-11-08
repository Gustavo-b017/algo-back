# API do Mecânico — Back-end em Flask

API REST para consulta de catálogo externo, autocomplete e carrinho por usuário, com documentação via Swagger/OpenAPI.

---

## 1. Integrantes

* **Alunos:**

  * Gilson Dias Ramos Junior — RM552345
  * Gustavo Bezerra Assumção — RM553076
  * Jefferson Gabriel de Mendonça — RM553149
* **Curso:** Engenharia de Software, 2ESPA

---

## 2. Visão Geral

* Flask + Flask-SQLAlchemy (MySQL)
* Integração HTTP resiliente com catálogo externo (pool, retry/backoff)
* Autocomplete adaptativo (Trie + similaridade)
* Sessões de usuário com JWT (login/register/me)
* CORS e compressão habilitados
* Swagger UI em `/apidocs` e especificação em `/openapi.yaml`

---

## 3. Funcionalidades

* Consulta de montadoras, famílias e subfamílias
* Busca de produtos com filtros, ordenações e paginação
* Detalhes de produto com similares
* Autocomplete em tempo real conectado ao catálogo externo
* Carrinho por usuário autenticado (incluir, listar, atualizar quantidade, remover)

---

## 4. Estrutura do Projeto

```
app.py
routes/
  auth.py         # registro/login/perfil (JWT)
  product.py      # detalhes e carrinho
  search.py       # metadados, facetas, busca, autocomplete
services/
  auth_service.py # token de serviço (client credentials)
  search_service.py
utils/
  security.py     # JWT, hash de senha (Werkzeug)
  preprocess.py   # normalização de itens
  processar_item.py / processar_similares.py
  autocomplete_adaptativo.py
  sort.py
decorators/
  token_decorator.py  # injeta token de serviço para o catálogo externo
  auth_decorator.py   # exige JWT de usuário
database/
  __init__.py     # instância do db (SQLAlchemy)
  models.py       # Usuario, Produto
```

---

## 5. Requisitos para Rodar Localmente

### 5.1. Software

* Python **3.10+**
* Pip e **venv**
* **MySQL 8.x** (pode ser o do XAMPP ou servidor dedicado)
* Opcional: Git, cURL

### 5.2. Dependências Python

Instale em um ambiente virtual:

```bash
pip install --upgrade pip
pip install Flask flask-cors flask-compress Flask-SQLAlchemy mysql-connector-python \
            requests PyJWT python-dotenv flasgger pyyaml python-Levenshtein
# produção/containers (opcional):
# pip install gunicorn
```

### 5.3. Banco de Dados

1. Crie um banco (se ainda não existir), por exemplo `ancora_teste`:

```sql
CREATE DATABASE ancora_teste CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

2. Garanta um usuário com permissão de leitura/escrita nesse banco.

### 5.4. Variáveis de Ambiente (`.env` na raiz)

```ini
# Banco (Railway sobrescreve automaticamente; local usa o fallback abaixo)
DATABASE_URL=mysql+mysqlconnector://root@localhost/ancora_teste
# ou, se estiver no Railway, use:
# MYSQLHOST=...
# MYSQLUSER=...
# MYSQLPASSWORD=...
# MYSQLDATABASE=...
# MYSQLPORT=3306

# SSO / Catálogo externo
AUTH_TOKEN_URL=https://.../connect/token
AUTH_CLIENT_ID=...
AUTH_CLIENT_SECRET=...
API_BASE_URL=https://api-stg-catalogo.redeancora.com.br/superbusca/api/integracao
REQUEST_TIMEOUT_SECONDS=30

# Aplicação
SECRET_KEY=troque-em-producao
CORS_ORIGINS=http://localhost:5173,https://algo-front-kohl.vercel.app
LOG_LEVEL=INFO
FLASK_DEBUG=1
PORT=5000

# Criar tabelas (use 1 apenas na primeira execução)
CREATE_SCHEMA=0
```

---

## 6. Execução

```bash
python app.py
# ou
flask run
```

* Base: `http://localhost:5000/`
* Health: `/health`
* Swagger UI: `/apidocs`
* OpenAPI: `/openapi.yaml`

> O `app.py` carrega `openapi.yaml` (ou `openapi-oficina.yaml`) da raiz se existir. Sem o arquivo, a UI abre com um template mínimo.

---

## 7. Documentação via Swagger

* UI em `/apidocs`
* Arquivo em `/openapi.yaml`

Mantenha um `openapi.yaml` na raiz para a documentação completa dos endpoints e exemplos.

---

## 8. Autenticação

Dois tipos, com propósitos distintos:

1. **Token de serviço** (para consultar o catálogo externo)
   Fornecido internamente por `@require_token`. O cliente não envia nada.

2. **JWT de usuário** (para rotas do carrinho e `/auth/me`)
   Obtido em `/auth/login`. Enviar em `Authorization: Bearer <jwt>`.

---

## 9. Modelos de Dados

* **Usuario**: `id, nome, email, password_hash, telefone, avatar_url, created_at, updated_at`
  Serialização segura: `to_public_dict()`.

* **Produto** (carrinho, vinculado a `usuario_id`):
  `id_api_externa, nome, codigo_referencia, url_imagem, preco_original, preco_final, desconto, marca, quantidade`
  Constraint única `(usuario_id, id_api_externa)` evita duplicatas no carrinho.
  Serialização: `to_dict()`.

---

## 10. Endpoints (Resumo)

### Base e Saúde

* `GET /` – texto simples de status
* `GET /health` – `{ "status": "ok" }`

### Autenticação de Usuário (`/auth`)

* `POST /auth/register` – `{ nome, email, senha }`
* `POST /auth/login` – `{ email, senha }` → `{ token, user }`
* `GET /auth/me` – requer JWT
* `PUT /auth/me` – requer JWT; atualiza `nome`, `telefone`, `avatar_url` e troca de senha com `{ senha_atual, nova_senha }`

### Metadados e Autocomplete (token de serviço automático)

* `GET /montadoras`
* `GET /familias`
* `GET /familias/<familia_id>/subfamilias`
* `GET /autocomplete?prefix=<termo>`

### Facetas e Busca (token de serviço)

* `GET /facetas-produto?produto_nome=...&familia_id=...&subfamilia_id=...&placa=...`
* `GET /pesquisar?...`
  Parâmetros:
  `termo`, `familia_id`, `familia_nome`, `subfamilia_id`, `placa`, `marca`
  Ordenação: `ordenar_por=nome|score|vendidos|avaliacao|preco|preco_asc|preco_desc`, `ordem=asc|desc`
  Paginação: `pagina`

### Detalhe de Produto (token de serviço)

* `GET /produto_detalhes?id=...`
  Alternativas: `nomeProduto=...` ou `codigoReferencia=...` (opcional `marca`)

### Carrinho (JWT obrigatório)

* `POST /salvar_produto` – cria ou incrementa quantidade
* `GET /carrinho` – lista itens do usuário
* `POST /carrinho/produto/remover` – `{ id_api_externa }`
* `POST /carrinho/produto/atualizar-quantidade` – `{ id_api_externa, quantidade }` (≤0 remove)

---

## 11. Padrão de Respostas e Erros

* Sucesso: `{ "success": true, ... }` ou payload específico
* 400: parâmetros/payload inválidos
* 401: autenticação de usuário ausente/expirada/inválida
* 404: rota não encontrada ou recurso inexistente
* 500: erro interno do servidor
* Falha no catálogo externo (token de serviço):
  `{ "success": false, "error": "Falha na autenticação com a API externa" }` (500)

---

## 12. Dependências

Obrigatórias no código atual:

* `Flask`, `flask-cors`, `flask-compress`
* `Flask-SQLAlchemy`, `mysql-connector-python`
* `requests`, `PyJWT`, `python-dotenv`
* `flasgger`, `pyyaml`
* `python-Levenshtein`

Produção/containers:

* `gunicorn`

Não utilizadas no código enviado:

* `cachetools`, `geopy`, `passlib[bcrypt]`

---

## 13. Boas Práticas

* Definir `SECRET_KEY` por ENV em produção e rotacionar periodicamente
* Ajustar TTL do JWT conforme o risco do domínio
* Restringir `CORS_ORIGINS` aos domínios do front-end
* Não logar tokens/senhas
* Usar `CREATE_SCHEMA=1` apenas na primeira execução
* Manter `REQUEST_TIMEOUT_SECONDS` compatível com a latência do provedor externo

---

## 14. Solução de Problemas

* **401 nas rotas do carrinho**: envie `Authorization: Bearer <jwt>` obtido em `/auth/login`.
* **Falha na autenticação externa**: revise `AUTH_TOKEN_URL`, `AUTH_CLIENT_ID`, `AUTH_CLIENT_SECRET` e conectividade.
* **Erro de driver MySQL**: verifique `mysql-connector-python` e a URL `mysql+mysqlconnector://...`.
* **Swagger incompleto**: mantenha `openapi.yaml` na raiz para a documentação completa.

---

## 15. Roadmap

* Consolidar e versionar um `openapi.yaml` completo (todas as rotas, exemplos e schemas)
* Adicionar testes automatizados (unitários e de contrato)
* Rate limiting e request ID para observabilidade
* Melhorias de segurança (validação de `iss`/`aud` no JWT, política de CORS por ambiente)
