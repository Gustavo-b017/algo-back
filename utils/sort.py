def quick_sort(arr, asc=True, key_func=lambda x: x):
    if len(arr) <= 1:
        return arr
    pivot = key_func(arr[0])
    less = [x for x in arr[1:] if key_func(x) < pivot] if asc else [x for x in arr[1:] if key_func(x) > pivot]
    greater = [x for x in arr[1:] if key_func(x) >= pivot] if asc else [x for x in arr[1:] if key_func(x) <= pivot]
    return quick_sort(less, asc, key_func) + [arr[0]] + quick_sort(greater, asc, key_func)