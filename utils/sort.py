def ordenar_produtos(arr, asc=True, key_func=lambda x: x):
    return sorted(arr, key=key_func, reverse=not asc)