# Documentação Final - Projeto de DYNAMIC PROGRAMMING

---

## 1. Integrantes

- **Alunos:** 
  - Felipe Casquet Ferreira -- RM553680
  - Gilson Dias Ramos Junior​ -- RM552345
  - Gustavo Bezerra Assumção -- RM553076
  - Joseh Gabriel Trimboli Agra ​-- RM553094
  - Jefferson Gabriel de Mendonça -- RM553149
  
- **Professor:** Francisco Elanio Bezerra
- **Curso:** Engenharia de Software, 2ESPA
- **Disciplina:** DYNAMIC PROGRAMMING

---

## 2. Como usar e colocar para funcionar no terminal de comandos

### Requisitos:
- Python 3 instalado
- Node.js e npm instalados

### Backend (Flask)
2. Instale dependências:
```bash
pip install -r requirements.txt
```
3. Execute o servidor:
```bash
python app.py
```
O backend será iniciado em `http://127.0.0.1:5000`

### Frontend (React)
1. Instale o Node.js e o Npm:
```
Node.js: https://nodejs.org/pt/download
versão usada: v22.12.0

npm: vem junto do node
```
```
por codigo:
# Descarregar e instalar a fnm:
winget install Schniz.fnm

# Descarregar e instalar a Node.js:
fnm install 22

# Consultar a versão da Node.js:
node -v # Deveria imprimir "v22.14.0".

# Consultar a versão da npm:
npm -v # Deveria imprimir "10.9.2".
```
2. Instale dependências:
```bash
npm install
```
3. Execute o frontend:
```bash
npm run dev
```
A aplicação abrirá normalmente em `http://localhost:5173`

*Obrigado!*

OBS:
* Mesmo se iniciar o backend, não irá modificar no front, pois a chamada ao backend é pelo site que estou hospendando
* Pórem caso queira, e so ir no front, e modificar a seguinte linha:
  * Abre SRC
  * Paginas
    * Distancia
    * Entrega
    * Home
    * Item
    * Produto
    * Sugestão
  * Deve se comentar a linha "const API_URL = import.meta.env.VITE_API_URL;" em todas as peginas listadas acima 
  * E descomentar a "const API_URL = 'http://127.0.0.1:5000';" para fazer a requisição local, porém precisará estar rodando o arquivo antes (python app.py)