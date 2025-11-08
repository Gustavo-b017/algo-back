# utils/sort.py
"""
Utilitário de ordenação com opção de seleção parcial
----------------------------------------------------------------------
Fornece uma função `ordenar_produtos` que:
- Para coleções grandes (len(arr) > 100) e quando `limite` é informado,
  usa heap (`heapq.nsmallest`/`nlargest`) para obter somente os N melhores,
  economizando CPU e memória em relação a ordenar tudo.
- Caso contrário, aplica `sorted` normal.

Observações:
- `sorted` é estável; as operações de `heapq` não garantem estabilidade
  entre elementos empatados pelo `key_func`.
- `key_func` deve ser uma função que receba o item e retorne a chave de ordenação.
"""

import heapq

def ordenar_produtos(arr, asc=True, key_func=lambda x: x, limite=None):
    """
    Ordena (ou seleciona parcialmente) uma coleção de itens.

    Parâmetros:
        arr (iterable): coleção de elementos a ordenar.
        asc (bool): True para ordem crescente; False para decrescente.
        key_func (callable): função chave (item -> chave de ordenação).
        limite (int|None): se informado e len(arr) > 100, retorna apenas os
            `limite` melhores via heap (nsmallest/nlargest).

    Retorna:
        list: lista ordenada (ou parcialmente selecionada).

    Comportamento:
        - Se `limite` estiver definido e houver mais de 100 itens, usa:
            * asc=True  -> heapq.nsmallest(limite, arr, key=key_func)
            * asc=False -> heapq.nlargest(limite, arr, key=key_func)
        - Caso contrário, retorna `sorted(arr, key=key_func, reverse=not asc)`.

    Nota:
        Para preservar a ordem relativa de empates, utilize um `key_func`
        que retorne tuplas (ex.: (chave, indice_original)) ou opte por `sorted`.
    """
    # Seleção parcial eficiente para coleções grandes quando o limite foi definido
    if limite and len(arr) > 100:
        if asc:
            return heapq.nsmallest(limite, arr, key=key_func)
        else:
            return heapq.nlargest(limite, arr, key=key_func)

    # Para coleções pequenas ou quando `limite` não foi definido, ordena tudo
    return sorted(arr, key=key_func, reverse=not asc)
