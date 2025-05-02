import heapq

def ordenar_produtos(arr, asc=True, key_func=lambda x: x, limite=None):
    if limite and len(arr) > 100:
        if asc:
            return heapq.nsmallest(limite, arr, key=key_func)
        else:
            return heapq.nlargest(limite, arr, key=key_func)
    return sorted(arr, key=key_func, reverse=not asc)